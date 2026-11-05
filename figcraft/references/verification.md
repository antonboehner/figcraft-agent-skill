# Verification

Nothing counts as done until the structure has been read back. Visual confirmation is a second tier
and you only claim the tier you actually ran.

## Tier 1: structural, always run this

```bash
figcraft-cli info design.figcraft                      # counts, top-level frames, missing fonts
scripts/figctl.py inspect --depth 4 --fields name,type,width,height,x,y     # live: the tree
scripts/figctl.py inspect --outline                                     # live: shape without values
scripts/figctl.py node 3 --depth 1 --fields name,width,height,sizing,boundVariables
scripts/figctl.py call engine.execute '{"command":"text.missingFonts"}' --window 1
```

Headless equivalents, in a script of their own (`--out` left out, so nothing is written):

```jsonl
{"command":"node.get","params":{"id":1,"outline":true}}
{"command":"node.get","params":{"id":2,"fields":["name","width","height","sizing","layout","cornerRadius","boundVariables","childCount"]}}
{"command":"text.missingFonts"}
{"command":"component.properties","params":{"id":6}}
{"command":"inspect.properties","params":{"id":2}}
{"command":"view.get"}
```

What those returned on a verified run (the shape to expect):

```json
{"boundVariables":{"cornerRadius":"VariableID:2","fills/0/color":"VariableID:1"},
 "children":[{"height":27.0,"id":3,"name":"Willkommen zurück","sizing":{"horizontal":"fill","vertical":"hug"},"width":288.0}],
 "cornerRadius":14.0,"height":59.0,"id":2,"name":"Card","sizing":{"horizontal":"fixed","vertical":"hug"},"width":320.0}
{"families":[]}
{"component":2,"conflicts":[],"properties":[{"default":"Primary","name":"Button/state","options":["Primary","Disabled"],"type":"variant"}],"set":4}
```

`inspect.properties {id}` answers the Dev Mode panel — labelled rows (`Width 353`, `Radius 14`,
`Direction vertical`) — which is the fastest way to check one layer the way a developer reads it.

## The defects worth looking for

| Look at | What it means when it is wrong |
|---|---|
| a frame with `sizing: hug` that is `0.0×0.0` | nothing inside it. A hug frame with no content is empty, and so is every instance of that component |
| a child `width` equal to the parent's `width` while the parent has `padding` | the padding is not being applied, or the child is `absolute` |
| a `fill` child inside a parent that hugs that axis | it cannot fill: hug the parent or make the child `fixed`/`hug` |
| text width vs. its frame's inner width | text 288 wide inside a 320 frame with 16 padding is right; 320 inside 320 will clip |
| `boundVariables` empty on colors you meant to be tokens | the values were written as hex, `variable.bind` never ran |
| `text.missingFonts` → `{"families":["…"]}` | the type is drawing in a fallback and every measure in the design is a lie |
| `component.properties` → `conflicts` non-empty | a variant property is bound inconsistently across the set |
| an unexpected extra frame at the top level | `layout.add` was called on a frame that already had `props.layout` and wrapped it |
| a name you set that did not stick | the property went to the wrong layer, or the id you addressed is a different node — `node.get` the id you used |

`arrange.tidy`, `align.*` and `distribute.*` act on the **selection**, so check them with
`inspect.properties` after `select.set` — that is where the numbers live.

## Tier 2: visual, when you can look

```bash
scripts/figctl.py render /tmp/figcraft-shot.png --window 1 --scale 2 --ids 2   # live, one layer or the page
figcraft-cli render design.figcraft -o preview.png --scale 2 --no-system-fonts  # headless, same on every machine
```

`ui.render` writes a **file path** and answers `{"bytes":27209,"format":"png","path":"…"}` — never
inline. It also works on a window that is parked.

`ui.screenshot` is the app's own view (window chrome and overlays), and it **needs the window on
screen**: on a hidden or covered window it blocks until it times out with `timed out waiting for the
UI: screenshots and input need the FigCraft window on screen (is it minimised or covered?)`. Use
`ui.render` unless the chrome itself is the subject, and give such calls a short `--timeout 15`.

**If your model has no image input, say so out loud** — e.g. "the structure is verified; visual
confirmation was not done, this model cannot see images." Do not describe a design you only read as
numbers. (This skill was built on such a model: `read_image` answered `model "splash" does not declare
image input`, so tier 1 was the tier that carried the work.)

## Undo, because verification sometimes finds a mistake

```bash
scripts/figctl.py call engine.execute '{"command":"edit.undo"}' --window 1        # {"undone":true}
scripts/figctl.py call engine.execute '{"command":"edit.redo"}' --window 1
```

A chunk is one undo step, which is the point: rolling back a chunk is one call and leaves the rest
of the user's history alone. `edit.undo` live was checked against a rename and the old name came back.
Never roll back more than the steps you made: the user's own edits sit in the same history.

## What to report

Say which tier ran and what it showed: the layer count, the sizes that matter, `families:[]`, the
variables that are bound. If a step failed, report the app's sentence, not a paraphrase — the exact
text is what tells the next person which parameter was wrong.
