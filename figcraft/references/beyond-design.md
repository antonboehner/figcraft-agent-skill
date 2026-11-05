# Beyond the design edit: the rest of FigCraft

The cheat sheet covers the ~120 commands design work actually needs. The installed catalog has
**635 commands in 61 namespaces**, and every one of them is reachable: headless as a step in a
script, live inside `engine.execute`. So "can it do that too?" is almost always *yes, via the
catalog* — this page is the map, not a permission list.

```bash
figcraft-cli commands --filter collab        # read the real parameters before touching any of these
```

## The map (verified on 0.15.0, counts from the live catalog)

| Area | Namespaces (commands) |
|---|---|
| Building and editing layers | `text` 58, `object` 28, `edit` 16, `node` 6, `shape` 6, `frame` 3, `section` 1, `bool` 5, `layers` 1, `arrange` 10, `align` 6, `distribute` 2, `transform` 9 |
| Vectors and paint | `vector` 42, `shapeBuilder` 4, `fill` 7, `stroke` 8, `effect` 6, `paint` 1, `image` 7, `guide` 5 |
| Layout and structure | `layout` 5, `grid` 3, `page` 8, `doc` 5, `window` 2, `template` 1 |
| Design systems | `variable` 19, `style` 10, `component` 21, `instance` 8, `library` 19, `libraries` 2, `codeConnect` 4, `data` 1 |
| Selection and view | `select` 21, `selection` 6, `view` 49 |
| Text and fonts | `text` 58, `font` 2 |
| Prototyping | `proto` 21 (flows, interactions, actions, conditional blocks, `proto.evaluate`, preview and presentation) |
| Dev handoff | `inspect` 5, `dev` 4, `devMode` 3, `devResource` 4, `annotation` 8, `measure` 2, `export` 3, `file` 24 |
| Team and file life | `collab` 21 (host/join/share a live session, peers, follow, cursor chat, spotlight, online files), `version` 8, `branch` 7, `comment` 15 |
| Boards and workshops | `board` 21 (stickies, connectors, stamps, ink, tables, timer, voting), `widget` 6 |
| Tools and app | `tool` 29, `pref` 17, `plugin` 11, `plugins` 2, `app` 2, `command` 1, `help` 4 |

Everything in the design references lives in the first four rows; the rest is what makes FigCraft a
collaborative app rather than a drawing library.

## Reaching them

Same three steps as always — `commands --filter <area>`, a chunk, `scripts/check_chunk.py`, then run.
A prototype flow, a comment thread and a version snapshot are ordinary chunks:

```jsonl
{"command":"proto.flow.add","params":{"start":2,"name":"Onboarding"}}
{"command":"proto.interaction.add","params":{"id":2,"trigger":{"type":"onClick"},"action":{"type":"navigate","dest":3},"transition":{"type":"dissolve","durationMs":200}}}
{"command":"comment.add","params":{"x":20,"y":20,"text":"Radius sitzt 2 px zu hoch.","anchor":2}}
{"command":"comment.list"}
{"command":"proto.evaluate","params":{"expression":"1 + 1"}}
{"command":"version.autosave"}
```

Run through that set on this machine, so the shapes above are the ones the app accepted:

```json
{"command":"proto.flow.add","ok":true,"result":{"name":"Onboarding","start":2}}
{"command":"comment.add","ok":true,"result":{"id":1,"link":"figcraft://comment/1"}}
{"command":"proto.evaluate","ok":true,"result":{"text":"1 + 1","type":"number","value":{"type":"number","value":2.0}}}
{"command":"version.autosave","ok":true,"result":{"saved":true,"version":{"auto":true,"id":"1a1ac19b8e4","name":"Autosave"}}}
```

The traps that sentence came from: `comment.add` wants **`x`, `y` and `text`** (with `anchor` for the
node it pins to), not a node id; `proto.interaction.add` requires **`action`** even for a plain click
navigate (`{"type":"navigate","dest":3}`); `proto.evaluate` computes prototype expressions
(`"count + 1"`, `"mode(Theme) == 'Dark'"`) without touching the document; `version.autosave` takes no
parameters and answers the version it wrote. `commands --filter proto.interaction` shows the whole
trigger/action menu (`onClick|onHover|afterDelay|keyPress`, `openOverlay`, `setVariable`,
`conditional` blocks, transitions and easings).

## What needs a second look before you run it

Not forbidden — just not reversible in the way a chunk is.

- **`pref.*` (17)** changes *the user's app*: interface scale, autosave, reduce motion, language, the
  sharing server. Read the current value first with `command.batch` + `--onError continue` if you must
  touch one, and put it back.
- **`collab.*` (21)** reaches outward: `collab.host`, `collab.share` (a join code), `collab.publish`,
  `collab.removePerson`, `collab.report`. These involve other people and a server. Do not start,
  share or publish anything without the user asking for it.
- **`version.restore`, `version.delete`, `branch.merge`, `branch.archive`** rewrite history that the
  user may be depending on. `version.autosave` before, and say what you did.
- **`plugin.run`, `plugin.import`, `plugin.directory.install`** execute third-party code, and
  `figcraft-cli plugin publish` pushes it to a server. Only with an explicit request.
- **`library.publish`, `library.publishToServer`, `library.acceptUpdates`** change what other files
  see. Same rule.
- **`tool.*` (29)** picks interactive tools (`pen`, `pencil`, `marker`, `eraser`) and `tool.place`
  places with them. Building geometry with `node.create` / `vector.*` is precise; driving a pencil
  tool through `ui.pointer` is not. Prefer the former.
- **`proto.present`, `proto.preview`, `widget.click`, `app.*`** open windows or click UI: they change
  what the user is looking at mid-session.
- **`collab.*`, `library.*`, `plugin.directory.*`, `pref.publishServer`** need a FigCraft server and
  an account; without one they fail, and the failure names what is missing.

## What FigCraft's CLI genuinely cannot do

- **Touch an open window from a headless run.** `figcraft-cli run` has no attach option; live work
  means the control port.
- **Keep design and code in step.** A code connection is a name, an import path and a template;
  exports are one-shot copies.
- **Round-trip foreign formats losslessly.** `.fig`, `.penpot` and SVG import and export with
  `warnings` for what was dropped — read them to the user.
- **Draw like a hand.** Vectors are built from coordinates (`node.create {type:"vector"}`,
  `vector.*`, `path`, `points`), which is exact but not sketchy.
- **Server-side administration.** `figcraft-server` itself is not a CLI target; the commands talk to
  it as a client.
