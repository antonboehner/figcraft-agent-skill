#!/usr/bin/env python3
"""figctl.py - drive a running FigCraft app through its control channel.

FigCraft started with `--control <port>` listens on 127.0.0.1:<port> only and
speaks newline-delimited JSON: one request line in, one reply line out. This is
that client, so an agent can edit the window the user is looking at without any
MCP server in the picture. `engine.execute` carries every command the app knows,
and `command.batch` carries a whole chunk of them as one undo step.

    scripts/figctl.py ping
    scripts/figctl.py inspect --outline --depth 3
    scripts/figctl.py node 12 --depth 2 --fields name,width,height
    scripts/figctl.py run chunk.json --label "Card" --agent figcraft-skill
    scripts/figctl.py batch requests.jsonl
    scripts/figctl.py render /tmp/screen.png --scale 2 --ids 12
    scripts/figctl.py call ui.set '{"rightTab":"design"}'

Exit codes: 0 = the app answered ok. 1 = the app answered ok:false (its own
error text is printed unchanged). 2 = usage error, or no app answering.

One chunk = one connection = one request. The app caps active connections at 8
and its request queue at 8, so do not run several figctl.py calls in parallel.
"""

import argparse
import json
import os
import socket
import sys

DEFAULT_PORT = int(os.environ.get("FIGCRAFT_CONTROL_PORT", "7979"))
APP_BIN = os.environ.get(
    "FIGCRAFT_APP", "/Applications/FigCraft.app/Contents/MacOS/FigCraft"
)
STEP_KEYS = {"command", "params", "as"}


def die(code, message):
    print(message, file=sys.stderr)
    sys.exit(code)


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class Control:
    """One newline-delimited JSON connection to the app."""

    def __init__(self, host, port, timeout, debug=False):
        try:
            self.sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            die(
                2,
                f"error: no FigCraft app answering on {host}:{port} ({exc}).\n"
                f"       start it:  scripts/figcraft-open.sh {port}\n"
                f"       or launch it:  {APP_BIN} --control {port}",
            )
        self.host, self.port, self.timeout, self.debug = host, port, timeout, debug
        self.lines = self.sock.makefile("rwb")
        self._id = 0

    def request(self, method, params=None, timeout_ms=None):
        self._id += 1
        req = {"id": self._id, "method": method}
        if params:
            req["params"] = params
        ms = int(timeout_ms if timeout_ms is not None else self.timeout * 1000)
        ms = max(0, min(ms, 600000))
        if ms:
            req["timeoutMs"] = ms
        if self.debug:
            print(">> " + compact(req), file=sys.stderr)
        try:
            # Read a little longer than the app is allowed to take, so the
            # app's own timeout reply (which says what happened to the request)
            # arrives instead of this client giving up first.
            self.sock.settimeout(self.timeout + 5)
            self.lines.write((compact(req) + "\n").encode("utf-8"))
            self.lines.flush()
            raw = self.lines.readline()
        except (OSError, socket.timeout) as exc:
            die(
                2,
                f"error: {method} got no reply from {self.host}:{self.port} "
                f"({exc}). The app was given {self.timeout:g}s "
                f"(timeoutMs {ms}); this client waited {self.timeout + 5:g}s.\n"
                "       a request the app never started was dropped and not applied; "
                "one it had started cannot be stopped and will take effect - "
                "read the document back before retrying.",
            )
        if not raw:
            die(2, f"error: the app closed the connection before answering {method}.")
        try:
            reply = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            die(2, f"error: unreadable reply for {method}: {exc}")
        return reply


def emit(reply, pretty, truncate):
    """Print one reply. Long reads get cut with a marker, never silently."""
    text = (
        json.dumps(reply, ensure_ascii=False, indent=2)
        if pretty
        else compact(reply)
    )
    if truncate and len(text) > truncate:
        print(text[:truncate])
        print(
            f"... reply cut at {truncate} chars - narrow the read "
            "(--fields, --outline, a smaller --depth) or pass --truncate 0",
            file=sys.stderr,
        )
    else:
        print(text)
    return reply.get("ok") is not False


def load_steps(path):
    """Read a chunk file: JSON array, {"commands": [...]}, or JSON lines."""
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        die(2, f"error: cannot read the chunk {path}: {exc}")
    text_strip = text.strip()
    if not text_strip:
        die(2, f"error: the chunk {path} is empty.")
    steps = None
    if text_strip[0] in "[{":
        try:
            data = json.loads(text_strip)
        except json.JSONDecodeError as exc:
            die(2, f"error: {path} is not valid JSON ({exc}). "
                   "For JSON lines, start the file with a step per line.")
        if isinstance(data, dict):
            data = data.get("commands")
        if not isinstance(data, list):
            die(2, f"error: {path} must hold a list of steps or a commands object.")
        steps = data
    else:
        steps = []
        for number, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError as exc:
                die(2, f"error: {path} line {number} is not a JSON step: {exc}")
    for number, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("command"), str):
            die(2, f"error: {path} step {number} must be an object with a 'command'.")
        extra = set(step) - STEP_KEYS
        if extra:
            die(
                2,
                f"error: {path} step {number} ({step['command']}) has step keys "
                f"{sorted(extra)}; only command, params and as are allowed.",
            )
    if not steps:
        die(2, f"error: {path} holds no steps.")
    return steps


UNTARGETABLE = {"window.list", "window.new", "window.focus", "engine.commands",
                "events.poll", "app.quit"}


def target(params, args, method=None):
    """Add the window and document the request should act on.

    Methods that take none (window.*, engine.commands, events.poll) are left
    exactly as they were written.
    """
    params = dict(params or {})
    if method in UNTARGETABLE:
        return params
    if args.window is not None:
        params["window"] = args.window
    if args.document is not None:
        params["document"] = int(args.document) if args.document.lstrip("-").isdigit() \
            else args.document
    return params


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="control port the app was started with (default 7979)")
    common.add_argument("--host", default="127.0.0.1",
                        help="the app only ever listens on loopback")
    common.add_argument("--timeout", type=float, default=60.0,
                        help="seconds the app may take over this request (1-600)")
    common.add_argument("--window", type=int,
                        help="window id to act in (0 is the main window)")
    common.add_argument("--document",
                        help="open file to act on, by id or path")
    common.add_argument("--fields",
                        help="comma separated node keys to read, nothing else")
    common.add_argument("--outline", action="store_true",
                        help="read only id, name, type, characters, visible")
    common.add_argument("--depth", type=int,
                        help="how deep to read (inspect default 3, node default 1)")
    common.add_argument("--pretty", action="store_true", help="indented JSON out")
    common.add_argument("--truncate", type=int, default=6000,
                        help="cut a reply at this many chars (0 = never)")
    common.add_argument("--debug", action="store_true",
                        help="print each request line to stderr")

    parser = argparse.ArgumentParser(
        description="Drive a FigCraft app that was started with --control <port>.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="The app is the source of truth: scripts/figctl.py call engine.commands "
               "for its full command list; for filtered lookups use "
               "figcraft-cli commands --filter TEXT.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping", parents=[common],
                   help="is an app answering, and which files does it show")
    insp = sub.add_parser("inspect", parents=[common], help="document.inspect")
    insp.add_argument("--all-pages", action="store_true",
                      help="read every page instead of summarising the others")
    node = sub.add_parser("node", parents=[common], help="node.get one layer")
    node.add_argument("id", type=int, help="layer id (from inspect or a chunk result)")
    run = sub.add_parser("run", parents=[common],
                         help="run a chunk as ONE command.batch request")
    run.add_argument("chunk", help="JSON array, commands object or JSON lines")
    run.add_argument("--label", help="undo-history label for the chunk")
    run.add_argument("--agent", help="name the edits were made under (agent)")
    run.add_argument("--on-error", choices=["continue"],
                     help="keep going past a failing step (nested batch rules)")
    batch = sub.add_parser("batch", parents=[common],
                           help="several control requests on one connection")
    batch.add_argument("requests", help="JSONL or JSON array of {method, params}")
    batch.add_argument("--keep-going", action="store_true",
                       help="do not stop at the first failed request")
    render = sub.add_parser("render", parents=[common],
                            help="ui.render: the document as a PNG file")
    render.add_argument("path", help="where the PNG goes (always a file, never inline)")
    render.add_argument("--scale", type=float, help="render scale")
    render.add_argument("--ids", help="comma separated layer ids to render")
    call = sub.add_parser("call", parents=[common],
                          help="any control method: call <method> '<json params>'")
    call.add_argument("method")
    call.add_argument("params", nargs="?", default="{}")

    return parser


def main():
    args = build_parser().parse_args()
    if not 1 <= args.timeout <= 600:
        die(2, "error: --timeout must be between 1 and 600 seconds.")
    ctl = Control(args.host, args.port, args.timeout, args.debug)

    fields = [f.strip() for f in args.fields.split(",")] if args.fields else None

    def output(reply):
        if not emit(reply, args.pretty, args.truncate):
            sys.exit(1)

    if args.cmd == "ping":
        output(ctl.request("window.list"))
    elif args.cmd == "inspect":
        params = {"depth": args.depth if args.depth is not None else 3}
        if fields:
            params["fields"] = fields
        if args.outline:
            params["outline"] = True
        if args.all_pages:
            params["allPages"] = True
        output(ctl.request("document.inspect", target(params, args)))
    elif args.cmd == "node":
        params = {"id": args.id, "depth": args.depth if args.depth is not None else 1}
        if fields:
            params["fields"] = fields
        if args.outline:
            params["outline"] = True
        output(ctl.request("node.get", target(params, args)))
    elif args.cmd == "run":
        steps = load_steps(args.chunk)
        batch_params = {"commands": steps}
        if args.label:
            batch_params["label"] = args.label
        if args.on_error:
            batch_params["onError"] = args.on_error
        execute_params = target({"command": "command.batch", "params": batch_params}, args)
        if args.agent:
            execute_params["agent"] = args.agent
        output(ctl.request("engine.execute", execute_params,
                           timeout_ms=int(args.timeout * 1000)))
    elif args.cmd == "batch":
        try:
            with open(args.requests, encoding="utf-8") as handle:
                text = handle.read().strip()
        except OSError as exc:
            die(2, f"error: cannot read {args.requests}: {exc}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = []
            for number, line in enumerate(text.splitlines(), start=1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    die(2, f"error: {args.requests} line {number} is not a JSON "
                           f"request: {exc}")
        if not isinstance(data, list):
            data = [data]
        failed = 0
        for item in data:
            method = item.get("method") if isinstance(item, dict) else None
            if not method:
                die(2, "error: every entry needs a 'method'.")
            reply = ctl.request(method, target(item.get("params") or {}, args, method),
                                timeout_ms=int(args.timeout * 1000))
            emit(reply, args.pretty, args.truncate)
            if reply.get("ok") is False:
                failed += 1
                if not args.keep_going:
                    sys.exit(1)
        if failed:
            sys.exit(1)
    elif args.cmd == "render":
        params = {"path": args.path}
        if args.scale is not None:
            params["scale"] = args.scale
        if args.ids:
            params["ids"] = [int(i) for i in args.ids.split(",") if i.strip()]
        output(ctl.request("ui.render", target(params, args)))
    elif args.cmd == "call":
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as exc:
            die(2, f"error: params are not JSON: {exc}")
        output(ctl.request(args.method, target(params, args, args.method)))


if __name__ == "__main__":
    main()
