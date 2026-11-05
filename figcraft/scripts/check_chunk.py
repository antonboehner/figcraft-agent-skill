#!/usr/bin/env python3
"""check_chunk.py - check a FigCraft chunk BEFORE it runs.

A chunk is one undo step and all-or-nothing: one mistyped parameter throws away
every step in it. This pre-flight reads the installed CLI's own command catalog
and reports what would fail, in the CLI's own words plus the corrections FigCraft
actually means.

    scripts/check_chunk.py chunk.json
    scripts/check_chunk.py chunk.json --cli /opt/homebrew/bin/figcraft-cli

Exit codes: 0 the chunk would run, 1 the chunk would be rejected, 2 bad arguments.

It is a pre-flight, not an authority: the installed CLI stays the source of
truth, and a rejection always names the parameters that command documents.
"""

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

PINNED_VERSION = "0.15.0"
STEP_KEYS = {"command", "params", "as"}
ALWAYS_TAKEN = {"ids", "id"}


def die(code, message):
    print(message, file=sys.stderr)
    sys.exit(code)


def run_cli(cli, args):
    try:
        out = subprocess.run([cli] + args, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        die(2, f"error: could not run '{cli} {' '.join(args)}': {exc}")
    if out.returncode != 0:
        die(2, f"error: {cli} {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def cli_version(cli):
    try:
        return run_cli(cli, ["--version"]).strip().split()[-1]
    except SystemExit:
        raise
    except Exception:
        return "unknown"


def load_catalog(cli, catalog_file=None):
    """{command id: params doc string}, cached per CLI version.

    With `catalog_file`, the catalog comes from that file instead of the CLI: either
    the raw `commands --json` list (optionally `{"version": …, "commands": […]}`) or
    an already flattened `{id: params doc}` map. That is how the repo's tests run
    without FigCraft installed.
    """
    if catalog_file:
        try:
            with open(catalog_file, encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as exc:
            die(2, f"error: catalog file {catalog_file} cannot be read: {exc}")
        except json.JSONDecodeError as exc:
            die(2, f"error: catalog file {catalog_file} is not readable JSON: {exc}")
        version, entries = "unknown", None
        if isinstance(data, dict):
            version = str(data.get("version", "unknown"))
            entries = data.get("commands") or data.get("catalog")
            if entries is None:                      # a flat {id: params doc} map
                catalog = {k: v for k, v in data.items()
                           if k != "version" and isinstance(v, str)}
                if not catalog:
                    die(2, f"error: catalog file {catalog_file} contains no commands.")
                return version, catalog
        else:
            entries = data
        catalog = {e["id"]: (e.get("params") or "")
                   for e in entries or [] if isinstance(e, dict) and e.get("id")}
        if not catalog:
            die(2, f"error: catalog file {catalog_file} contains no commands.")
        return version, catalog

    version = cli_version(cli)
    safe = re.sub(r"[^0-9A-Za-z.-]", "_", version)
    cache = os.path.join(tempfile.gettempdir(), f"figcraft-commands-{safe}.json")
    if os.path.isfile(cache) and time.time() - os.path.getmtime(cache) < 3600:
        try:
            with open(cache, encoding="utf-8") as handle:
                return version, json.load(handle)
        except (OSError, json.JSONDecodeError):
            pass
    raw = run_cli(cli, ["commands", "--json"])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        die(2, f"error: {cli} commands --json is not readable JSON: {exc}")
    catalog = {}
    for entry in data:
        if isinstance(entry, dict) and entry.get("id"):
            catalog[entry["id"]] = entry.get("params") or ""
    if not catalog:
        die(2, f"error: {cli} commands --json returned no commands.")
    try:
        with open(cache, "w", encoding="utf-8") as handle:
            json.dump(catalog, handle)
    except OSError:
        pass
    return version, catalog


def depth_split(text, sep=","):
    """Split on sep, ignoring separators inside (), [] {} or "quotes".

    Apostrophes are prose here ("a vector's SVG path data"), so only " quotes.
    """
    parts, buf, depth, quote = [], "", 0, None
    for ch in text:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
            continue
        if ch == '"':
            quote = ch
            buf += ch
            continue
        if ch in "([{":
            depth += 1
            buf += ch
            continue
        if ch in ")]}":
            depth -= 1
            buf += ch
            continue
        if ch == sep and depth == 0:
            parts.append(buf)
            buf = ""
            continue
        buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def outer_object(text):
    """The params of a doc that starts with `{`: its contents, prose after it dropped."""
    if not text.startswith("{"):
        return text
    depth = 0
    for index, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[1:index]
    return text[1:]


KEY_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_]*)(\??)\s*(?P<after>$|\(|\[|:|\{|\||/)"
)


def documented_keys(params_doc):
    """(parameter names, required-name groups) read out of a prose params doc.

    A name written without `?` is required. Names offered as alternatives in one
    entry (`path | data (…)`, `value (default mode) | values {…}`) form one group:
    the command needs one of them.
    """
    if not params_doc:
        return set(), []
    raw = params_doc.split("→")[0].strip()
    braced = raw.startswith("{")
    text = outer_object(raw)
    keys = set()
    groups = []
    for token in depth_split(text):
        token = token.strip()
        if not token:
            continue
        match = KEY_RE.match(token)
        if not match:
            continue
        name, optional = match.group(1), match.group(2)
        keys.add(name)
        if match.group("after") == ":":
            if not optional:
                groups.append({name})
            continue
        group = {name}
        # alternatives come as `text? | characters?` and aliases as
        # `strokeCap / startCap / endCap` - both are separate accepted names.
        parts = []
        for chunk in depth_split(token, sep="|"):
            parts.extend(depth_split(chunk, sep="/"))
        for piece in parts[1:]:
            alt = KEY_RE.match(piece.strip())
            if alt:
                keys.add(alt.group(1))
                group.add(alt.group(1))
        if not optional and braced:
            groups.append(group)
    # A doc that is a bare list of names (node.set, node.get) is a menu of
    # interchangeable properties, not a list of required parameters.
    return keys, (groups if braced else [])


def load_chunk(path):
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError as exc:
        die(2, f"error: cannot read {path}: {exc}")
    if not text:
        die(2, f"error: {path} is empty.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as whole_error:
        data = None
        for number, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                data = (data if isinstance(data, list) else [])
                data.append(json.loads(line))
            except json.JSONDecodeError:
                data = None
                break
        if data is None:
            die(2, f"error: {path} is neither one JSON script nor JSON lines: {whole_error}")
    if isinstance(data, dict):
        data = data.get("commands")
    if not isinstance(data, list):
        die(2, f"error: {path} must hold a list of steps or a commands object.")
    return data


def walk_refs(value, where, declared, step_index, errors):
    """$ref and $step are batch-local: only an earlier step of this batch."""
    if isinstance(value, dict):
        if "$ref" in value or "$step" in value:
            if "$ref" in value:
                name = value["$ref"]
                if name not in declared:
                    errors.append(
                        f"{where}: $ref \"{name}\" names no earlier step of this batch "
                        f"(known: {sorted(declared) or 'none yet'}). "
                        "References are batch-local - a layer from an earlier chunk "
                        "must be given by its id."
                    )
            if "$step" in value:
                index = value["$step"]
                if not isinstance(index, int) or index < 0 or index >= step_index:
                    errors.append(
                        f"{where}: $step {index} names no earlier step "
                        f"(steps here so far: {step_index})"
                    )
            extra = set(value) - {"$ref", "$step", "field"}
            if extra:
                errors.append(f"{where}: a reference takes only $ref, $step and field, "
                              f"got {sorted(extra)}")
            return
        for key, child in value.items():
            walk_refs(child, f"{where}.{key}", declared, step_index, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_refs(child, f"{where}[{index}]", declared, step_index, errors)


def validate(steps, catalog, layer_keys, path, prefix=""):
    errors = []
    declared = set()
    counted = 0
    for index, step in enumerate(steps):
        where = f"{prefix}step {index}"
        if not isinstance(step, dict) or not isinstance(step.get("command"), str):
            errors.append(f"{where}: a step must be an object with a 'command'.")
            continue
        command = step["command"]
        counted += 1
        extra_keys = set(step) - STEP_KEYS
        if extra_keys:
            errors.append(f"{where} ({command}): step keys {sorted(extra_keys)} are not "
                          "allowed; only command, params and as.")
        entry = catalog.get(command)
        if entry is None:
            close = difflib.get_close_matches(command, catalog, n=4, cutoff=0.4)
            errors.append(f"{where}: unknown command \"{command}\". "
                          f"Closest real ids: {close or 'none'}. "
                          f"Look it up: <cli> commands --filter \"{command.split('.')[0]}\"")
            continue
        entry_keys, required_groups = documented_keys(entry)
        allowed = entry_keys | ALWAYS_TAKEN
        if command in {"node.set", "node.get", "document.inspect", "ui.render"}:
            required_groups = []      # these read/apply whatever they are given
        params = step.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            errors.append(f"{where} ({command}): params must be an object.")
            params = {}
        for group in required_groups:
            if not (group & set(params)):
                named = " or ".join(sorted(group))
                errors.append(f"{where} ({command}): missing required parameter "
                              f"{named} (documented: {', '.join(sorted(allowed)[:16])})")
        for key in sorted(params):
            if key in allowed:
                continue
            if key in layer_keys:
                errors.append(f"{where} ({command}): no parameter \"{key}\" here - "
                              f"{command} takes {sorted(allowed)}; layer properties such "
                              f"as \"{key}\" belong in props.{key}")
            else:
                shown = ", ".join(sorted(allowed)[:16])
                errors.append(f"{where} ({command}): no parameter \"{key}\" "
                              f"(documented: {shown})")
        if "parent" in params and isinstance(params["parent"], list):
            errors.append(f"{where} ({command}): \"parent\" takes one id, not a list; "
                          "lists are for ids.")
        if "$ref" in params or "$step" in params:
            errors.append(f"{where} ({command}): a reference is an object such as "
                          "{\"$ref\": \"name\"}, not a key on params.")
        if command == "command.batch":
            # The inner batch is its own reference scope: the app answers
            # `$ref "card" names no step` for an outer name seen from inside.
            inner = params.get("commands")
            walk_refs({k: v for k, v in params.items() if k != "commands"},
                      f"{where}.params", declared, index, errors)
            if not isinstance(inner, list) or not inner:
                errors.append(f"{where} (command.batch): needs a non-empty commands list.")
            else:
                inner_errors, _ = validate(inner, catalog, layer_keys, path,
                                           prefix=f"{where}.batch ")
                errors.extend(inner_errors)
        else:
            walk_refs(params, f"{where}.params", declared, index, errors)
        if "as" in step:
            name = step["as"]
            if not isinstance(name, str) or not name:
                errors.append(f"{where}: as must be a non-empty name.")
            elif name in declared:
                errors.append(f"{where}: as \"{name}\" is used twice in this batch.")
            else:
                declared.add(name)
    return errors, counted


def main():
    parser = argparse.ArgumentParser(
        description="Check a FigCraft chunk against the installed CLI before running it.")
    parser.add_argument("chunk", help="JSON array, commands object or JSON lines")
    parser.add_argument("--cli", default=os.environ.get("FIGCRAFT_CLI", "figcraft-cli"),
                        help="the CLI whose catalog to check against")
    parser.add_argument("--catalog", default=os.environ.get("FIGCRAFT_CATALOG"),
                        help="read the command catalog from this JSON file instead of running the CLI")
    parser.add_argument("--pinned-version", default=PINNED_VERSION,
                        help=f"the version this skill was verified on (default {PINNED_VERSION})")
    args = parser.parse_args()

    version, catalog = load_catalog(args.cli, args.catalog)
    if version not in ("unknown", args.pinned_version):
        print(f"note: the installed CLI is {version}, this skill was verified on "
              f"{args.pinned_version}. Trust the installed CLI's own "
              f"'commands --filter' output over any cheat sheet.", file=sys.stderr)

    layer_keys, _ = documented_keys(catalog.get("node.set", ""))
    if not layer_keys:
        print("note: the catalog has no node.set entry; the props hint is off.",
              file=sys.stderr)

    steps = load_chunk(args.chunk)
    errors, counted = validate(steps, catalog, layer_keys, args.chunk)
    if errors:
        for line in errors:
            print(f"error: {line}", file=sys.stderr)
        print(f"\n{args.chunk}: {len(errors)} problem(s) in {counted} step(s) - "
              "fix the chunk before running it. One bad parameter discards the "
              "whole chunk.", file=sys.stderr)
        sys.exit(1)
    commands = sorted({s["command"] for s in steps if isinstance(s, dict) and s.get("command")})
    print(f"{args.chunk}: ok, {counted} step(s), {len(commands)} command(s): "
          + ", ".join(commands))


if __name__ == "__main__":
    main()
