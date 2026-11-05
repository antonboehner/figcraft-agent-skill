# Handoff: export, conversion, tokens, code connections

Everything here is a one-shot copy. A code connection stores names and a template; it does not keep
the design and the code in sync while either changes.

## Files out of the CLI

```bash
figcraft-cli export design.figcraft -o expdir --scale 2      # one file per top-level frame
figcraft-cli render design.figcraft -o preview.png --scale 2 --no-system-fonts
figcraft-cli convert design.figcraft design.penpot
figcraft-cli info design.figcraft
```

Give a headless write a root, or it refuses: `--automation-write-root "$PWD/out"`. An app **you**
started with roots refuses live exports outside them too; an app the user started themselves has no
roots and writes wherever their own permissions allow — so on the live side, naming a project path is
the safety measure.

## Export as commands (live or inside a script)

| Command | Shape |
|---|---|
| `file.export` | `{ids?, format? (png\|jpg\|svg\|pdf\|webp\|xml\|fig\|penpot), scale? \| size? (2x\|512w\|512h\|{by, value}), path?, bleed?, cropMarks?, bleedMarks?, cmyk?, contentsOnly?, includeBoundingBox?, svgOutlineText?, svgSimplifyStroke?, svgIdAttribute?, vdCompat?}` |
| `file.exportLayers` | `{ids?, assets?, dir?, zip?}` — every layer once per **export setting**, named `<layer><suffix>.<format>`; a slash in the layer name makes folders |
| `file.exportSvg` | `file.export`'s SVG options, selection only |
| `file.exportFramesPdf` | `{path?, page?}` — every top-level frame, one PDF page each, in reading order |
| `export.add` / `export.update` / `export.remove` | `{ids?, setting? {size, suffix?, format?, bleed?, cropMarks?, bleedMarks?, cmyk?, vdCompat?}}` — the settings a layer carries in the file |
| `inspect.assets` | `{ids?}` → `{assets:[{id,name,kind: export\|icon\|image, exports}]}` — see what a handoff would produce, then run `file.exportLayers {assets:true}` |

PDF print options are strings with units: `bleed:"3mm"`, `"0.125in"`, `"9pt"`, together with
`cropMarks:true`, `bleedMarks:true`, `cmyk:true`. `xml` is an Android Vector Drawable and answers
`warnings` for what it approximated; `vdCompat` picks `bestEffort|exact|ignore`.

A verified run of `export.add` + `file.export {pdf}` + `file.exportLayers {assets:true, dir:…}`:

```json
{"command":"file.exportLayers","ok":true,"result":{"files":[{"bytes":3426,"id":7,"name":"Button@2x.png","path":"/tmp/…/assets/Button@2x.png"}],"skipped":0}}
```

Without `path` / `dir`, bytes come back as base64 `data` — **which lands in your context.** Always
name a path (or `dir`) when you export.

Formats that leave the file: `format:"fig"` (marked experimental, returns `warnings` for what was
dropped) and `format:"penpot"` (a Penpot 2.x archive). `figcraft-cli convert` opens `.penpot`, `.fig`,
`.sketch`, REST file JSON and `.svg` in the other direction, also with `warnings`. Report those notes
to the user — a conversion that lost their gradients is not a silent detail.

## Design tokens out

```json
{"command":"variable.export","params":{"format":"css","path":"/tmp/…/tokens.css"}}
```

`format` is `json | css | tailwind | dart`, each with `path?` (without one it returns `text`). The css
one writes a block per mode, so light and dark arrive as one stylesheet:

```css
/* Tokens · Light */
:root {
  --brand: #4F46E5;
  --radius-card: 14px;
}
/* Tokens · Dark */
[data-tokens="Dark"] {
  --brand: #4F46E5;
  --radius-card: 14px;
}
```

`variable.import` brings tokens back in. Tailwind arrives as an `@theme static` block, dart as
constants — the mapping of a variable name to a token name is the app's (`radius.card` →
`--radius-card`), so name variables the way you want them to read in code.

## Code connections

```json
[
 {"command":"codeConnect.set","params":{"id":6,"language":"swiftui","importPath":"Components.Button","name":"Button","template":"Button(title: \"{label}\")"}},
 {"command":"codeConnect.export","params":{"path":"/tmp/…/figcraft.connect.json"}},
 {"command":"inspect.code","params":{"id":6,"language":"swiftui"}}
]
```

```json
{"command":"codeConnect.set","ok":true,"result":{"code":"import Components.Button\n\nButton(title: \"{label}\")\n","component":6,"language":"swiftui","unknown":["label"]}}
{"command":"codeConnect.export","ok":true,"result":{"links":1,"path":"/tmp/…/figcraft.connect.json"}}
{"command":"inspect.code","ok":true,"result":{"code":"import Components.Button\n\nButton(title: \"{label}\")\n","connected":true,"language":"swiftui"}}
```

- `language`: `react|leptos|vue|swiftui|compose|arkui|flutter`.
- `importPath` is a **module or package name** — letters, digits, `_` and `.`. A path with slashes is
  refused: `importPath: a module or package name (letters, digits, _ and .), up to 300 characters`.
- In `template`, `{property}` is a component property and `{property ? "a" : "b"}` picks between
  values; any other `{…}` stays literal and is reported in `unknown` (that `["label"]` above is the
  connection saying the property does not exist).
- `codeConnect.import` reads the mappings back in; `codeConnect.remove` drops one link.
- `inspect.componentCode {id, language}` gives the component, its properties and the connected snippet.
- `component.playground {id, properties, language, path}` renders the component with those property
  values as a PNG and returns its code — **nothing in the document changes**, so it is the safe way to
  check a component before a handoff.

To publish a repository's mappings into a design file:

```bash
figcraft-cli connect publish design.figcraft --mappings figcraft.connect.json --dry-run
# 1 component link(s) from figcraft.connect.json would be published to design.figcraft (dry run: not saved)
figcraft-cli connect publish design.figcraft          # published 1 component link(s) …
```

`connect publish` **saves the file in place**: never run it on a document the user has open. Entries
that do not fit (unknown component, bad template) are reported and skipped rather than failing the run.

## Failing scripts and files already written

A script that fails rolls its **document** changes back and writes no `--out` — but a step that
already exported a file leaves that file on disk (the PDF and `Button@2x.png` above survived the
rollback of the steps after them). When a handoff script fails, delete or overwrite its outputs
before running it again.

## Print and PDF

`file.export {format:"pdf", bleed:"3mm", cropMarks:true, cmyk:true}` or `file.exportFramesPdf` for a
frame-per-page document. `includeBoundingBox:true` cuts off shadows and outside strokes — leave it
out unless the bounding box is the print spec.

`figcraft-cli plugin publish` sends a plugin folder to a figcraft-server's plugin directory; it is a
server operation, not part of a design handoff.
