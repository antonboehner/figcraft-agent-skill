---
name: figcraft
description: >-
  Design and edit in FigCraft (the Figma alternative) through its CLI and its
  control channel: build screens, components and design tokens either in the
  user's open FigCraft window over the control port or headless on .figcraft
  files; batch design edits as validated JSON scripts; inspect and verify what
  was built; export png/jpg/svg/webp/pdf or convert to .figcraft/.fig/.penpot;
  export design tokens and publish code connections. Use when working with
  FigCraft, figcraft-cli, figcraft-cli run scripts, .figcraft files, or when
  the user asks to design or change a UI screen, mockup, wireframe, component
  set, auto layout or design tokens in FigCraft — including driving the open
  FigCraft window so the user watches the canvas change.
compatibility: >-
  Requires figcraft-cli on PATH (verified on 0.15.0), the FigCraft desktop app
  at /Applications/FigCraft.app (not on PATH), python3 for the bundled scripts,
  and loopback TCP access to the app's control port. macOS paths shown; the
  CLI flags are the same on Linux.
license: MIT
metadata:
  author: anton
  version: "0.1.0"
  verified-with: "figcraft-cli 0.15.0 + FigCraft.app (macOS)"
  tags: "figcraft,design,ui,cli,figma,design-tokens,code-connect"
---

# FigCraft

FigCraft is the Figma alternative. `figcraft-cli` is on `PATH` (verified on 0.15.0); the app is
`/Applications/FigCraft.app/Contents/MacOS/FigCraft` and is **not** on `PATH`. The installed CLI is
the source of truth: `figcraft-cli --help` and `figcraft-cli commands --filter TEXT` outrank every
cheat sheet, including this one.

## 1. Pick the mode, then say which one you are in

| Situation | Mode | How |
|---|---|---|
| The user is at the FigCraft window and wants to watch the canvas change | **live** | app started with `--control <port>`, driven by `scripts/figctl.py` |
| Nobody is watching: bulk build, conversion, export, CI, a file the app is not showing | **headless** | `figcraft-cli run chunk.json --in a.figcraft --out a.figcraft` |
| Some harness already has a FigCraft MCP server configured | name it, do not build on it | the control channel reaches the same methods without MCP |

- **Headless `run` cannot reach an open window** — it has no attach option. If the user expects to
  see the design appear, use the live channel.
- FigCraft's MCP server is only a wrapper over these same methods
  (`figcraft-cli mcp --attach 7979`, a bare port meaning `127.0.0.1:7979`; headless MCP takes the
  automation roots, `--attach` refuses them and inherits the app's). If a harness has one, name it
  and work through the control channel anyway — nothing here needs MCP.
- **Never `--out` onto a file the app is showing.** The app's own save clobbers the script's output,
  and writing the open file is not a way to edit the canvas.

Live access needs a control port; `7979` is the convention:

```bash
scripts/figcraft-open.sh 7979      # attach if something answers, otherwise start the app itself
scripts/figctl.py ping             # which app answers, and which files it shows
```

`figcraft-open.sh` checks the port first and launches nothing when it is already answering. An app the
user started **without** `--control` has no control port at all, so there is nothing to edit through:
start it with the port (or ask them to) instead of writing to their file. When the session will read
or write files, launch with roots —
`scripts/figcraft-open.sh 7979 --read-root "$PWD/design" --write-root "$PWD/out"` — and ask before
restarting an app that is already open, because that closes whatever the user has in it.

## 2. The loop, one chunk at a time

```bash
figcraft-cli commands --filter layout                       # 1 look names up, one term per call
cat > chunk.json <<'JSON'                                   # 2 write 5-30 steps, one reviewable unit
[{"command":"node.create","as":"card","params":{"type":"frame","name":"Card","width":320,"height":96,
  "props":{"fill":"#FFFFFF","cornerRadius":14,"layout":"vertical","gap":12,"padding":[16,16,16,16]}}},
 {"command":"node.create","params":{"type":"text","parent":{"$ref":"card"},"text":"Title",
  "props":{"fontSize":22,"fill":"#111827","sizingH":"fill"}}}]
JSON
scripts/check_chunk.py chunk.json                           # 3 pre-flight, fix before running
scripts/figctl.py run chunk.json --window 1 --label "Card"  # 4a live: one request, one undo step
figcraft-cli run chunk.json --in design.figcraft --out design.figcraft   # 4b headless
scripts/figctl.py inspect --depth 3 --fields name,type,width,height      # 5 read back, bounded
scripts/figctl.py render /tmp/figcraft-shot.png --scale 2                # 6 render, then look at it
```

**`scripts/check_chunk.py` before every chunk.** A chunk is one undo step and all-or-nothing: one
wrong parameter name discards every step in it, writes nothing, and rolls the document back. The
pre-flight costs one call and returns the mistake as a sentence:
`step 0 (node.create): no parameter "gap" here — layer properties such as "gap" belong in props.gap`.

## 3. Chunk size: 5–30 steps, one judgement unit

A chunk is what a person can look at and say yes or no to: a card, a header, one screen section,
one component with its variants.

| Chunk | Verdict |
|---|---|
| one `node.set` per call, 12 calls in a row | wrong: round-trip waste, and the undo history becomes unusable |
| the whole app, 90 steps, 6 screens | wrong: one typo throws it all away, and you cannot review it |
| a card with its text and button, 8–20 steps | right |
| a screen that needs 45 steps | split it by section, verify in between |

- One chunk = one batch request = one undo step in the user's history. Give it a `--label`.
- Inside the chunk, name steps with `"as":"name"` and target them with `{"$ref":"name"}`.
  **References are batch-local.** A layer made by an earlier chunk must be given by its id —
  `$ref "screen" names no step` is the app telling you this.
- A step that may fail and should not kill the chunk goes in a nested `command.batch` with
  `"onError":"continue"`; it returns one result per inner step while the outer chunk stays atomic.
  **Its references are its own**: names from the outer chunk are invisible inside it, so give the
  inner steps their own `as` names or pass ids.

## 4. Four token rules

| Rule | The expensive alternative it replaces |
|---|---|
| Look commands up filtered, one term per call: `figcraft-cli commands --filter layout` | the full catalog is 635 commands / 183 KB |
| Read bounded: `inspect --outline --depth 3` or `--fields name,type,width,height`, `node --fields …` | a whole-document dump of every page with every property |
| Images always land on a file path (`render /tmp/x.png`, `ui.render {path}`) | an inline base64 picture inside the reply |
| Chunk steps into one script | dozens of single-call round trips for one visual unit |

`figctl.py` cuts a reply at 6000 characters and says so on stderr. Narrow the read instead of
raising `--truncate`.

## 5. File safety

- **Headless writes are confined, and that is enforced.** `--automation-read-root DIR
  --automation-write-root DIR` (repeatable, the folder must exist, a read-only run cannot write at
  all). A refusal names the folders: `automation path rejected: /tmp is outside the folders that may
  be written: /private/tmp/…/out`. Retarget the path; do not retry somewhere else.
- **An app you started is confined too; an app the user started is not.** With roots on the launch
  (`scripts/figcraft-open.sh 7979 --read-root "$PWD/design" --write-root "$PWD/out"`) the app refuses
  live writes *and* reads outside them — `automation path rejected: /tmp/…/outside.png is outside the
  folders that may be written: /private/tmp/…/out`, and the same for `file.open` under the read root.
  An app the user opened themselves has no roots: `file.export`, `file.saveAs` and `file.open` wrote
  and read `/tmp` paths without complaint. Ask before restarting their app with roots; if they
  decline, the confinement is your own path discipline.
- **Never write onto a file the app is showing.** `--out` (or `connect publish`, which saves in
  place) onto an open document loses to the app's own save. Update it live, or save headlessly under
  a new name and tell the user where it is.
- A live `file.open {path}` adds a tab to the user's app, and `file.close {index, force}` closes it
  again — clean up what your own test opened.

## 6. Gotchas verified on figcraft-cli 0.15.0

- `node.create` takes only `type, x, y, width, height, parent, index, name, text, characters, path,
  points, closed, props, select`. **`layout`, `gap`, `padding`, `sizingH/V`, `cornerRadius`, `fills`
  and every other property go inside `props`.** Step keys are only `command`, `params`, `as`.
- `parent` is **one id**, not a list; lists are for `ids`. Same for `instance.create {component}` and
  `node.get {id}`. `{"$ref":"card"}` is a value, not a key.
- `layout.add` is for layers that have no auto layout yet. On a frame that already has `props.layout`
  it **wraps that frame in a new frame**: set the layout in `props`, or call `layout.add` once.
- In `props`, `{"$var":"token"}` works for `fill` and `stroke` only. A radius, gap or width is bound
  with `variable.bind {ids, field, variable}`.
- Variables need their collection first: `variable.createCollection {name}` →
  `variable.create {collection, name, type, value}` → `variable.bind {ids, field, variable}`.
- `component.create` makes **one** component per call — `ids:[a,b]` put both frames inside one new
  component. `component.combineVariants` and `component.addVariant` work off the **selection**, and
  the axis is named by the label (`Button/state=Primary` → property `Button/state`), which
  `component.properties {id}` prints exactly.
- Layer ids ascend from 2 (page is 1): a later chunk can address the ids an earlier chunk returned.
- Control **methods** are not commands: `file.open` is a command, so it goes
  `call engine.execute '{"command":"file.open","params":{…}}'`, and `call file.open …` answers
  `unknown method`.
- `document` targeting wants an **id from `doc.list`** (a number) or a file path — a file *name* is
  refused. `window` goes inside `params`.
- Read fields are spelled the app's way: `fills` (not `fill`), `sizing`, `boundVariables`,
  `gridCell`, `absoluteBounds`, `characters`. A wrong key is refused with the full list.
- `node.set … description` answers "description applies to components". Not every property fits
  every layer type.
- A hidden or minimised window still answers edits but wakes at most ten times a second,
  `window.new` refuses it outright, and a request can be **dropped without being applied** —
  the reply says so: `timed out … before the app started this request … it was not applied`.
  Read the document back before retrying; a request already started keeps running.
- Missing fonts draw in a fallback and quietly ruin type-sensitive screens: check
  `text.missingFonts` and `info`'s `missing font` lines.
- `--format svg`, `.fig` and `.penpot` do not round-trip every feature; the commands print `note:`
  lines. Read them to the user.

## 7. Design defaults

- Build with **auto layout**, not absolute positions: `layout`, `gap`, `padding`, `mainAlign`,
  `crossAlign`, `sizingH`/`sizingV`. Children of an auto-layout frame are placed by the layout.
- `hug` for content-sized frames, `fill` for children that take the parent's width, `fixed` when a
  size is the design decision. A child cannot fill an axis its parent hugs.
- One scale for spacing (4/8/12/16/24/32) and one type scale, as **variables**: tokens in the file
  beat hex codes scattered across layers, and `variable.export` turns them into css, tailwind, dart
  or json.
- Repeat a thing more than twice → make it a component; states → variants. Details and the exact
  parameter spellings: [references/design-craft.md](references/design-craft.md).

## 8. Verify before you hand anything over

Two tiers, and you may not claim the one you did not run.

1. **Structural, always:** `figcraft-cli info file.figcraft`, `figctl.py inspect --depth 4 --fields
   name,type,width,height,x,y`, `node <id> --fields name,width,height,layout`, `text.missingFonts`.
   Check layer counts, sizes, that a hugging frame actually hugs, that text is inside its parent.
2. **Visual, when you can see images:** render to a file and look at it. If your model has no image
   input, say in plain words that visual confirmation was not done.

The checklist and the concrete defect list: [references/verification.md](references/verification.md).

## 9. References — read the one whose trigger fits

| Read this | When |
|---|---|
| [references/live-control.md](references/live-control.md) | the user is watching the window; anything about `figctl.py`, ports, windows, `timeoutMs`, sockets |
| [references/headless-run.md](references/headless-run.md) | `figcraft-cli run`, script formats, `$ref`/`$step`, `--in`/`--out`, templates, roots |
| [references/command-cheatsheet.md](references/command-cheatsheet.md) | you need exact parameter spellings for the common design commands |
| [references/design-craft.md](references/design-craft.md) | auto layout, sizing, components and variants, variables, spacing and type scales |
| [references/verification.md](references/verification.md) | after every chunk, and before calling work finished |
| [references/handoff.md](references/handoff.md) | export, print, convert, token export, code connections |
| [references/beyond-design.md](references/beyond-design.md) | the task is not a design edit: prototype flows, comments, boards, libraries, versions and branches, plugins, preferences, collaboration |

The cheat sheet is a curated subset. The catalog holds 635 commands in 61 namespaces and all of them
reach the same document — `commands --filter <area>` plus the pre-flight is the way into any of them.

## 10. Do not

- Do not invent command ids or parameter names. Filter the live catalog; run the pre-flight.
- Do not promise live two-way sync with code. A code connection stores a name, an import path and a
  template; an export is a one-shot copy.
- Do not flatten a UI into one image unless that image is the deliverable.
- Do not treat an iPhone or MacBook frame preset as a device — it is a sized frame.
- Do not present unverified design work as finished.
