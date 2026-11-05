# The live control channel

Read this when the user is looking at the FigCraft window and the edits must appear there.

An app started with `--control <port>` listens on `127.0.0.1:<port>` only. Each connection carries newline-delimited JSON: **one request line in, one reply line out, in order.** `scripts/figctl.py` is that client; everything below was run against a live app on port 7979.

```bash
scripts/figctl.py ping                                   # is an app answering, and what it shows
scripts/figctl.py inspect --outline --depth 3            # bounded tree
scripts/figctl.py node 8 --depth 1 --fields name,gridCell
scripts/figctl.py run chunk.json --window 1 --label "Card" --agent figcraft-skill
scripts/figctl.py batch requests.jsonl --window 1
scripts/figctl.py render /tmp/screen.png --window 1 --scale 2 --ids 2
scripts/figctl.py call engine.commands '{}' --truncate 300
scripts/figctl.py call engine.execute '{"command":"doc.list"}'
```

Exit codes: `0` the app answered ok · `1` the app answered `ok:false` (its own error text is printed unchanged) · `2` usage error or no app answering. `--debug` prints the request line, which is how you check what was actually sent.

## Methods, not commands

`method` is the control channel's own vocabulary (`engine.execute`, `document.inspect`, `node.get`, `ui.render`, `ui.inspect`, `window.list`, `window.new`, `window.focus`, `events.poll`, `app.quit`). Design actions are **commands** and go inside `engine.execute`:

```bash
# right: file.open is a command
scripts/figctl.py call engine.execute '{"command":"file.open","params":{"path":"/tmp/a.figcraft"}}'
# wrong: {"error":"unknown method `file.open`"}
scripts/figctl.py call file.open '{"path":"/tmp/a.figcraft"}'
```

## Targeting a window or a file

- `window` goes **inside `params`**, next to the command's own parameters: `{"command":"node.set","params":{…},"window":1}`. `0` is the main window. Without it the request goes to the window last in front.
- `document` takes an **id from `doc.list`** (a number, not a string) or an open file's **path** — a file *name* is refused: `no open document "Untitled"`.
- `figctl.py --window 1` / `--document 2` add these for you; `window.list`, `engine.commands` and `events.poll` are left alone because they take neither.

## Chunk = one request

`run` sends the whole chunk as one `engine.execute` carrying `command.batch`, so it is **one undo step** in the user's history and the label shows up there:

```json
{"id":1,"ok":true,"result":[{"id":2},{"ids":[2]},{"ok":true},{"id":3}]}
```

One result object per step, in step order. Creation steps return `{"id":N}`, `layout.add` returns `{"ids":[N]}`, plain edits return `{"ok":true}`.

**`as` / `$ref` / `$step` are batch-local.** A chunk cannot name-reference a layer an earlier chunk created — `{"$ref":"screen"}` answers `$ref "screen" names no step`. Carry the real ids from the previous chunk's result or from `inspect`.

## Limits that bite

- **8 active connections, 8 queued requests.** One `figctl.py` call per chunk; never run them in parallel.
- **A request can be dropped without being applied.** The reply says so exactly: `timed out after 60 s before the app started this request (it was busy, or its window isn't drawing): it was not applied`. Read the document back before retrying — a request the app *had* started keeps running and cannot be stopped.
- `--timeout SECONDS` (1–600) becomes the request's own `timeoutMs`; the client then waits 5 s longer so the app's informative timeout reply arrives first. Cap is 600000 ms.
- A **minimised or hidden window** answers state edits (`engine.execute`, `document.inspect`, `node.get`, `ui.render`) but wakes at most ten times a second, and `window.new` refuses outright: `window 0 is minimised or hidden`. `ui.screenshot` and `ui.input` need a drawn frame. If the user's window is hidden, ask them to show FigCraft before canvas-level interaction.
- `ui.render` is the image path to prefer: it draws the document without the window and writes a file. Never request an image without a `path` — the reply would carry base64 into your context.
- Replies are cut at 6000 characters by default with a marker on stderr. Narrow the read (`--fields`, `--outline`, smaller `--depth`) instead of raising `--truncate`.

## Reads: what is worth a round trip

```bash
scripts/figctl.py inspect --depth 3 --outline           # names, types, structure, childCount
scripts/figctl.py inspect --depth 4 --fields name,type,width,height,x,y
scripts/figctl.py node 6 --fields name,boundVariables,layout
scripts/figctl.py call engine.execute '{"command":"text.missingFonts"}'
scripts/figctl.py call engine.execute '{"command":"doc.list"}'
```

`fields` names top-level node keys exactly as the app spells them, and `outline` is either-or with `fields`. A wrong key is refused with the full valid list — that list is long, so read it once and remember the traps: `fills` (not `fill`), `sizing`, `boundVariables`, `gridCell`, `absoluteBounds`, `characters`.

## Files from the live side

`file.export`, `file.saveAs`, `file.open` and `file.close` are **commands**, so they go inside
`engine.execute` (`call file.open '{…}'` is refused with `unknown method`):

```bash
scripts/figctl.py call engine.execute '{"command":"file.export","params":{"ids":[13],"format":"png","path":"/tmp/…/frame.png","scale":2}}' --window 1
scripts/figctl.py call engine.execute '{"command":"file.open","params":{"path":"/tmp/…/design.figcraft"}}' --window 1
scripts/figctl.py call engine.execute '{"command":"file.close","params":{"index":2,"force":true}}' --window 1
scripts/figctl.py call engine.execute '{"command":"edit.undo"}' --window 1        # {"undone":true}
```

Whether those writes are confined depends on **who started the app**:

- Started here with roots (`scripts/figcraft-open.sh 7979 --read-root … --write-root …`): every live
  read and write outside them is refused, and the message names the folders —
  `automation path rejected: /tmp/…/outside.png is outside the folders that may be written:
  /private/tmp/…/out`, and `… is outside the folders that may be read: /private/tmp/…` for
  `file.open`. A path inside one succeeds. `/tmp` is reported as its `/private/tmp` twin.
- Started by the user, no roots: `file.export`, `file.saveAs` and `file.open` wrote and read `/tmp`
  paths without complaint. There the discipline is yours — name project paths, not scratch paths.

Ask before restarting an app the user already has open: roots matter, but so does their unsaved work.
`file.open` adds a tab to their app, and closing the last document of a window closes that window —
afterwards the app answers `no window 1`. Close what your own test opened, and check `doc.list` before
assuming which documents are open.

`ui.render` writes a file path and works on a parked window. `ui.screenshot` is the app's own view
and **needs the window on screen**: on a covered or minimised window it blocks until it times out
with `timed out waiting for the UI: screenshots and input need the FigCraft window on screen (is it
minimised or covered?)`, so give it a short `--timeout 15` and prefer `ui.render`.

## Attribution

`--agent NAME` (or `"agent"` beside `command` in `engine.execute` params) runs the command as an agent rather than as the user: comments it leaves are signed `<agent> (agent)`, and the document reports the calls as agent-made.

## Emergency path, no Python

```bash
exec 3<>/dev/tcp/127.0.0.1/7979
echo '{"id":1,"method":"window.list"}' >&3
read -r reply <&3 && echo "$reply"
echo '{"id":2,"method":"engine.execute","params":{"command":"node.set","params":{"ids":[6],"props":{"name":"Continue"}},"window":1}}' >&3
read -r reply <&3 && echo "$reply"
exec 3<&-
```

Match every reply to its request id, one `read` per request. This has no timeout handling: prefer `scripts/figctl.py`.
