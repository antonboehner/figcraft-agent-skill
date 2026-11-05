# Command cheat sheet

Curated ids and the parameters that actually exist, copied from the installed catalog. **The installed CLI outranks this file:** when they disagree, `figcraft-cli commands --filter "<area>"` is right and this page is stale. Verified on **figcraft-cli 0.15.0** (635 commands).

`*` after an id in `commands` output means undoable. Design actions are commands: headless they are steps in a script, live they go inside `engine.execute`.

Look things up filtered, never all at once:

```bash
figcraft-cli commands --filter layout                # one term per call - "layout|variable" finds nothing
figcraft-cli commands --filter "node.set"            # one command, full parameter doc
figcraft-cli commands --json | head -1               # NEVER the whole 183 KB dump

The filter matches ids, menu labels **and parameter text**, so `--filter layout` also finds
`node.set` and `grid.add`. One term per call; `--filter "layout|variable"` finds nothing.
```

## Create and structure

| Command | Parameters | Notes |
|---|---|---|
| `node.create` | `{type, x?, y?, width?, height?, parent?, index?, name?, text?, characters?, path?, points?, closed?, props?, select?}` | `type`: `rectangle\|ellipse\|polygon\|star\|line\|arrow\|vector\|text\|frame\|section\|component\|slice`. Every property goes in `props` (they are `node.set` keys). `x`/`y` are relative to the parent frame. |
| `frame.create` | `{preset?, x?, y?, width?, height?, parent?, index?, name?, props?, select?}` | a preset without `x`/`y` lands to the right of the page's frames |
| `frame.presets` | `{}` | the named device/frame sizes |
| `text.create` | `{…}` | text with its own range parameters; for plain text `node.create {type:"text"}` is shorter |
| `object.group` / `object.ungroup` | `{ids?}` | a group has no auto layout, fill, stroke, radius, clipping or grids |
| `object.frameSelection` / `object.removeFrame` | `{ids?}` | frame the selection / drop the frame keeping its children |
| `object.convertToGroup` / `object.convertToFrame` / `object.convertToSection` | `{ids?}` | in place, layers stay put |
| `node.reparent` | `{ids?, parent?, index?}` | move layers into another container |
| `node.reorder` | `{ids?, …}` | stacking order |
| `bool.union` / `bool.subtract` / `bool.intersect` / `bool.exclude` | `{ids?}` | boolean groups |
| `file.newFromTemplate` | `{template, …}` | see [headless-run.md](headless-run.md); one step, ~190 layers, ids jump |

## Auto layout and sizing

| Command | Parameters | Notes |
|---|---|---|
| `layout.add` | `{ids?, direction? (horizontal\|vertical\|grid)}` | `direction: grid` gives a 2×2 grid of equal tracks |
| `layout.remove` / `layout.removeAll` | `{ids?}` / `{}` | removed layers keep their size as `fixed` |
| `layout.suggest` | `{id?}` | read-only: what direction and gap the children suggest |
| `layout.setTrack` | `{id?, …}` | grid track sizes |
| `node.set` | the layer property menu | auto layout lives here: `layout, gap, crossGap, padding, paddingTop/Right/Bottom/Left, mainAlign, crossAlign, contentAlign, wrap, strokesIncluded, sizingH, sizingV, minWidth/maxWidth/minHeight/maxHeight, absolute, constraints, gridColumns, gridRows, columnTracks, rowTracks, gridColumn, gridRow, gridColumnSpan, gridRowSpan` |
| `frame.swapOrientation` | `{ids?}` | flip the layout direction |

Inside one `node.set`, `layout` applies before the keys that tune it, so `{"layout":"vertical","gap":8}` keeps the gap. Auto-layout keys beside `layout: null` are refused.

## Paint, stroke, effects, grids

| Command | Parameters | Notes |
|---|---|---|
| `node.set` | `fill`, `fills`, `stroke`, `strokes`, `strokeWeight`, `strokeAlign`, `strokeSides`, `cornerRadius`, `cornerSmoothing`, `effects`, `opacity`, `blend`, `grids` | `fill`/`stroke` also take `"none"`, `null`, or `{"$var":"brand"}`. Gradients are paint objects: `{"type":"linearGradient","stops":["#hex","#hex"],"from?":[x,y],"to?":[x,y]}` |
| `fill.add` / `fill.set` / `fill.remove` / `fill.move` | `{ids?, …}` | fill list edits, order included |
| `stroke.add` / `stroke.set` / `stroke.widthProfile` / `stroke.brush` | `{ids?, …}` | per-side weights via `strokeTopWeight` … `strokeLeftWeight` |
| `effect.add` / `effect.set` / `effect.remove` | `{ids?, …}` | shadows and blurs |
| `grid.add` / `grid.remove` | `{ids?, …}` | layout grids on a frame |

## Text

| Command | Parameters | Notes |
|---|---|---|
| `text.set` | `{…}` | set characters on text layers |
| `text.style` | `{…}` | style a character range |
| `text.missingFonts` | `{}` | **run this before trusting a design**: `{"families":[]}` is clean |
| `text.refit` / `text.fit` | `{ids?}` | fit text to its box / to available fonts |
| `text.fonts` / `text.loadFont` / `font.download` | `{…}` | what is installed, load a font file, fetch a missing one |
| `node.set` | `characters, fontFamily, fontStyle, fontSize, lineHeight, letterSpacing, textAlign, textAutoResize, textCase, maxLines, fontVariations, features` | `lineHeight`/`letterSpacing` take px or `"150%"` / `"2%"` |

## Variables (tokens) and styles

| Command | Parameters | Notes |
|---|---|---|
| `variable.createCollection` | `{name, modes?}` | **always first** |
| `variable.addMode` / `variable.setMode` | `{…}` | light/dark as modes of one collection |
| `variable.create` | `{collection, name, type (color\|number\|string\|boolean), value \| values, description?}` | a value may be `{"alias": variable}` or `{"mix":{"from":…,"to":…,"t":0.5}}` |
| `variable.set` / `variable.update` | `{variable, mode?, value}` | |
| `variable.bind` | `{ids?, field, variable}` | `field`: `fill`, `stroke`, `fills/<i>/color`, `effects/<i>/radius`, `layoutGrids/<i>/size`, `width`, `height`, `cornerRadius`, `gap`, `fontSize`, `characters`, `componentProperties/<name>`; `variable: null` unbinds |
| `variable.list` / `variable.export` / `variable.import` | see [handoff.md](handoff.md) | tokens out to json / css / tailwind / dart |
| `style.create` / `style.apply` / `style.update` / `style.detach` / `style.list` | `{…}` | editing a styled list unlinks the style on purpose, so a later `style.update` does not overwrite the edit |

## Components, sets, instances

| Command | Parameters | Notes |
|---|---|---|
| `component.create` / `component.createMultiple` | `{ids?}` | |
| `component.addVariant` / `component.combineVariants` | `{…}` | a variant set is one component with axes |
| `instance.create` / `instance.place` | `{…}` | an instance of a main component |
| `instance.setProperties` / `component.properties` / `component.list` | `{…}` | variant and text/boolean properties |
| `component.detach` / `component.resetInstance` / `component.goToMain` | `{ids?}` | detach drops the link, reset brings it back |
| `instance.swap` | `{…}` | swap one instance for another component |

## Selection, find, arrange

| Command | Parameters | Notes |
|---|---|---|
| `select.set` / `select.add` / `select.remove` | `{ids?}` | "the selection" means ids left out |
| `node.find` | `{…}` | search by name, type or properties |
| `select.byName` / `select.matching` / `select.sameFill` / `select.sameFont` | `{…}` | selection by pattern instead of ids |
| `align.left` / `align.hcenter` / `align.right` / `align.top` / `align.vcenter` / `align.bottom` | `{ids?}` | |
| `distribute.horizontal` / `distribute.vertical` | `{ids?}` | |
| `arrange.tidy` / `arrange.spacing` / `arrange.packH` / `arrange.packV` / `arrange.front` / `arrange.back` | `{ids?}` | tidy a scattered selection, set or read gaps |
| `transform.moveTo` / `transform.resize` / `transform.rotate` / `transform.scale` | `{ids?, …}` | absolute moves and sizes; prefer auto layout for anything that must survive a resize |

## View, pages, documents, inspection

| Command | Parameters | Notes |
|---|---|---|
| `view.zoomFit` / `view.zoom100` / `view.set` / `view.get` | `{…}` | after a chunk, `view.zoomFit` puts the work in front of the user |
| `page.list` / `page.select` / `page.add` / `page.rename` | `{…}` | |
| `doc.list` / `doc.switch` / `doc.nextTab` | `{…}` | `doc.list` is where a `document` id for targeting comes from |
| `file.open` / `file.save` / `file.saveAs` / `file.import` | `{…}` | `file.open {path}` also takes `data` + `name` for bytes |
| `inspect.properties` / `inspect.code` / `inspect.assets` | `{…}` | `inspect.code` with `language: swiftui\|react\|vue\|tailwind\|compose\|flutter\|leptos\|arkui` generates a source shell |
| `file.export` / `file.exportLayers` / `file.exportSvg` / `file.exportFramesPdf` | see [handoff.md](handoff.md) | the in-app export commands |

## Reading a node (the read side)

`node.get {id?, ids?, fields?, outline?}` — **no `depth` on the command** (the control method `node.get` has one). Valid `fields` are the app's spellings: `fills` (not `fill`), `sizing`, `boundVariables`, `gridCell`, `absoluteBounds`, `characters`, `layout`, `overrides`, `styles`, `componentProperties`. A wrong key is refused with the complete valid list — read it once, then stop guessing.
