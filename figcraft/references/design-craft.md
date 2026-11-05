# Design craft in FigCraft

How to make something that looks designed rather than generated, with the parameter spellings that the 0.15.0 catalog actually accepts. Every flow below was run.

## Auto layout first, coordinates only when the layout cannot express it

Give the layout in `props`, in one step:

```json
{"command":"node.create","as":"card","params":{"type":"frame","name":"Card","x":0,"y":0,"width":320,"height":96,
  "props":{"fill":"#FFFFFF","cornerRadius":14,"layout":"vertical","gap":12,"padding":[16,16,16,16],
           "mainAlign":"min","crossAlign":"min","sizingH":"fixed","sizingV":"hug"}}}
```

`layout.add {ids, direction}` is for layers that already exist — a stack of rectangles you want to
flow, a frame made without layout. **On a frame that already has auto layout it wraps that frame in
a new one** (`layout.add` on a frame with `props.layout` answered a fresh `Frame 1` around it): either
set layout in `props`, or call `layout.add` once on a plain frame, never both.

Read it back and the numbers are the design: `{"layout":{"mode":"vertical","gap":12.0,
"padding":[16,16,16,16],"crossAlign":"min","mainAlign":"min"},"sizing":{"horizontal":"fixed",
"vertical":"hug"}}`.

- `layout` is `null|horizontal|vertical|grid|{…}`; inside one `node.set` it applies **before** the keys that tune it, so `{"layout":"vertical","gap":8}` keeps the gap. Auto-layout keys next to `layout: null` are refused.
- `padding` takes a number or `[t,r,b,l]`; `gap` is the main axis, `crossGap` the other. `mainAlign`/`crossAlign` take `min|center|max`, and the auto gaps `spaceBetween|spaceAround|spaceEvenly`; `crossAlign: baseline` aligns first text baselines in a horizontal layout.
- `sizingH`/`sizingV`: `fixed` is a decision, `hug` sizes to the content, `fill` takes the parent's track. **A child cannot fill an axis its parent hugs** — hug the outer frame, fill the inner ones. On a `hug` axis the `width`/`height` you passed is only a starting box: a `120×40` button hugging its 14 px text ended up `60×17`.
- Grid layout: `layout:"grid"` plus `gridColumns`, `gridRows`, `columnTracks`/`rowTracks` (`120 | "1fr" | "auto" | {sizing, value}`), and per child `gridColumn`, `gridRow`, `gridColumnSpan`, `gridRowSpan`, `gridAlignH`/`gridAlignV`. `layout.setTrack` retunes one track.
- `absolute: true` pulls a child out of the flow and `constraints {horizontal, vertical}` then anchor it. Use it for an overlay, not as a build strategy.
- A group (`object.group`) has no auto layout, fill, stroke, radius, clipping or grids. If the thing needs layout, it needs a frame (`object.frameSelection`, `object.convertToFrame`).

`layout.suggest {id?}` is read-only and tells you the direction and gap the existing children imply — useful before tidying a scattered selection with `arrange.tidy`.

## Scales, not one-off numbers

Spacing on one scale (4/8/12/16/24/32), type on one scale, and both as **variables** so a change is one call:

```json
{"command":"variable.createCollection","as":"tokens","params":{"name":"Tokens","modes":["Light","Dark"]}},
{"command":"variable.create","params":{"collection":{"$ref":"tokens"},"name":"brand","type":"color","value":"#4F46E5"}},
{"command":"variable.create","params":{"collection":{"$ref":"tokens"},"name":"radius.card","type":"number","value":14}},
{"command":"variable.bind","params":{"ids":[{"$ref":"card"}],"field":"fills/0/color","variable":{"$step":1,"field":"id"}}},
{"command":"variable.bind","params":{"ids":[{"$ref":"card"}],"field":"cornerRadius","variable":{"$step":2,"field":"id"}}}
```

- Collection first, then variables, then bindings. `variable.create` without `collection` answers `"collection" must be a string`.
- `variable.bind` `field` values: `fill`, `stroke`, `fills/<i>/color`, `effects/<i>/radius`, `layoutGrids/<i>/size`, `width`, `height`, `cornerRadius`, `gap`, `fontSize`, `characters`, `componentProperties/<name>`; `variable: null` unbinds.
- In `props` a bound value is `{"$var":"brand"}` (id or name) — **only for `fill` and `stroke`**.
  Anything else answers `only \`fill\` and \`stroke\` take variables in props; use \`variable.bind\`
  for other fields`, so a radius or a gap goes through `variable.bind {ids, field:"cornerRadius", variable}`.
- Light/dark is `modes` on one collection, so a screen does not need a second colour system.
- `variable.export` turns them into tokens for code — see [handoff.md](handoff.md).

## Components, sets, variants (the flow that works)

```json
[
 {"command":"node.create","as":"a","params":{"type":"frame","name":"Button/state=Primary","x":0,"y":0,"width":120,"height":40,
    "props":{"fill":"#4F46E5","cornerRadius":10,"layout":"horizontal","mainAlign":"center","crossAlign":"center","sizingH":"hug","sizingV":"hug"},"select":false}},
 {"command":"node.create","as":"b","params":{"type":"frame","name":"Button/state=Disabled","x":150,"y":0,"width":120,"height":40,
    "props":{"fill":"#C7C9D2","cornerRadius":10,"layout":"horizontal","mainAlign":"center","crossAlign":"center","sizingH":"hug","sizingV":"hug"},"select":false}},
 {"command":"node.create","params":{"type":"text","parent":{"$ref":"a"},"text":"Continue","props":{"fontSize":14,"fill":"#FFFFFF"}}},
 {"command":"node.create","params":{"type":"text","parent":{"$ref":"b"},"text":"Continue","props":{"fontSize":14,"fill":"#374151"}}},
 {"command":"component.create","params":{"ids":[{"$ref":"a"}]}},
 {"command":"component.create","params":{"ids":[{"$ref":"b"}]}},
 {"command":"select.set","params":{"ids":[{"$ref":"a"},{"$ref":"b"}]}},
 {"command":"component.combineVariants","as":"set","params":{}},
 {"command":"component.properties","params":{"id":{"$ref":"set"}}},
 {"command":"instance.create","as":"inst","params":{"component":{"$ref":"set"},"x":0,"y":90}},
 {"command":"instance.setProperties","params":{"ids":[{"$ref":"inst"}],"properties":{"Button/state":"Disabled"}}}
]
```

What the app insisted on, verified run by run:

- **`component.create` makes one component per call.** With `ids:[a,b]` it wrapped *both* frames inside a single new component named `Frame 1`. One call per component, or check `component.list`.
- `component.combineVariants` is **selection-driven**: no `ids`, `params:{}` after a `select.set` of the main components. Non-components in the selection answer `select components only`.
- Names carry the axes: `Button/state=Primary` becomes the set `Button` with the variant property **`Button/state`** (options `Primary`, `Disabled`). `component.properties {id}` prints the exact spelling — use it, because `property:"state"` answers `unknown variant property \`state\``.
- `component.addVariant` also wants the set **selected** (`select.set` first); passing only `id` answers `select a component set or component`. It duplicates a variant and returns the new one.
- `instance.create {component}` and `node.create {parent}` take **one id**; a list answers `must be a node id`. A variant set is a valid `component` value: the instance starts on its default variant, then `instance.setProperties {properties:{"Button/state":"Disabled"}}` switches it.
- `component.list` shows the Assets-panel folders a slash name creates (`folder:["Page 1","Button"]`) — slash naming is how a file stays readable.

Text, boolean and instance-swap properties live beside the variant axes: `component.addProperty`, `component.editProperty`, `component.bindProperty`, and all of them are set through the same `instance.setProperties {properties:{…}}`. `component.playground {id, properties, path}` renders a component with given property values **without changing the document** — a cheap way to check a component looks right.

## Text that survives

- `node.create {type:"text", text:"…", props:{fontSize:14, fill:"…"}}`, then let the frame hug or set `textAutoResize` (`widthAndHeight|height|none|truncate`).
- `lineHeight` and `letterSpacing` take px or a percent string (`"150%"`, `"2%"`). `textCase`, `textDecoration*`, `paragraphSpacing`, `listStyle`, `maxLines`, `fontVariations` are all `node.set` keys.
- Range edits (`text.style`, `text.setVariations`) touch the characters a range covers, so a headline can carry two weights without two layers.
- **Check fonts before calling it done:** `text.missingFonts` → `{"families":[]}` means the type is real. A missing family draws in a fallback and quietly changes every measure.

## Reading a layer back

`node.get {id, ids?, fields?, outline?}` — `outline` still needs an `id` (the page id, or the
subtree you care about); with no `id` it answers `id must be a node id`. With the app's spellings — `name, type, x, y, width, height, absoluteBounds, sizing, layout, fills, strokes, cornerRadius, boundVariables, componentProperties, componentPropertyDefinitions, children, childCount, overrides, styles, mainComponent, mainComponentName, characters, fontSize, gridCell, flows, interactions, exports, pluginData, description, visible, locked, rotation, opacity, effects, strokes, strokeWeight, strokeAlign` (a wrong key is refused with the full list). `outline: true` gives the tree instead of the properties.

## What gives a design away

- Different gaps for similar things. Pick the scale, then `arrange.spacing` and `node.set {gap}` to enforce it.
- Text that is not bound to its frame: a `fixed` text layer inside a `hug` frame clips when the copy gets longer.
- Hex colours in twenty places instead of five variables.
- Frames placed by hand where `layout.add` + `mainAlign` would keep the alignment true after a copy change.
- One component built four times: after the second repetition, make it a component and instantiate it.
- `iPhone 15` and `MacBook Pro 14` presets are sized frames, not devices; a real device mock needs an image.
