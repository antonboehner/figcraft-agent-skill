# Headless authoring

Read this when nobody is watching the canvas, or when the work is a file operation: bulk build, conversion, export, a render for a preview, a CI run.

`figcraft-cli run` opens its own session — **it cannot reach a window the user has open, and it has no attach option.** Its result is a file.

## Script formats

All three are accepted: a JSON array, an object holding `commands`, or JSON lines.

```bash
figcraft-cli run chunk.json                              # new empty document
figcraft-cli run chunk.json --in design.figcraft --out design.figcraft
figcraft-cli run chunk.jsonl --out design.svg            # --out format comes from the extension
figcraft-cli run chunk.json --out design.figcraft --automation-write-root "$PWD/design"
```

A step has exactly three legal keys — `command`, `params`, `as`:

```jsonl
{"command":"node.create","as":"screen","params":{"type":"frame","name":"Home","width":393,"height":852,"props":{"fill":"#F6F7FB"}}}
{"command":"layout.add","params":{"ids":[{"$ref":"screen"}],"direction":"vertical"}}
{"command":"node.set","params":{"ids":[{"$ref":"screen"}],"gap":16,"padding":[20,20,20,20],"sizingV":"hug"}}
```

Run `scripts/check_chunk.py chunk.json` first; it costs one call and prevents the one-typo-loses-everything failure.

## What a run prints

One JSON line per step, in order, after the whole script is through:

```json
{"command":"node.create","ok":true,"result":{"id":2},"step":0}
{"command":"layout.add","ok":true,"result":{"ids":[2]},"step":1}
{"command":"node.set","ok":true,"result":{"ok":true},"step":2}
```

Creation steps return `{"id":N}` (`node.create`, `frame.create`, `variable.create`, …), list steps return `{"ids":[…]}`, plain edits return `{"ok":true}`. Use those results as the ids your next chunk addresses.

Ids ascend from 2 — the page is 1 — **unless a step created many layers at once.** A starter template is one step that lands 186 layers: after `file.newFromTemplate {template:"dashboard"}` the next `node.create` is id 187. Never assume an id; read it out of the result line.

## Failure semantics: all-or-nothing

```json
{"command":"node.create","error":"invalid parameters for `node.create`: step 3: 187 can't contain layers","ok":false,"rolledBack":true,"step":3}
```

Exit 1, nothing written (`--out` skipped), the document back where it was. To let one risky step fail without killing the chunk, wrap it in a nested batch:

```json
{"command":"command.batch","params":{"label":"probe","onError":"continue","commands":[{"command":"node.set","params":{"ids":[99999],"props":{"name":"ghost"}}}]}}
```

It answers one result per inner step and the outer script stays atomic:

```json
{"command":"command.batch","ok":true,"result":[{"id":2},{"id":3},{"ok":true}],"step":0}
```

**A nested batch is its own reference scope.** Names declared outside it are invisible inside —
`$ref "card" names no step (no step has an `as` name)` is what the app answers when an inner step
reaches for an outer name. Name the inner steps with their own `as`, or pass ids.

## References between steps

```json
{"command":"node.set","params":{"ids":[{"$ref":"badge"}],"name":"Badge"}}
{"command":"node.set","params":{"ids":[{"$step":1,"field":"id"}],"name":"Badge"}}
{"command":"node.get","as":"tree","params":{"id":{"$ref":"row"},"fields":["id","children"]}}
{"command":"node.set","params":{"ids":[{"$ref":"tree","field":"children/0/id"}]}}
```

- `as` names a step, `$ref` reads it, `$step` is positional, `field` digs into that result with a
  `/`-path — and the path only exists if that result holds it. `step 0 ("row")'s result has no
  ids/0` is the app saying the step returned `{"id":…}`, not `{"ids":[…]}`. To reach children, read
  them with a `node.get` step first.
- **Batch-local.** A chunk cannot reference a name an earlier chunk declared — pass the id from the
  earlier chunk's result line instead.
- A parent must be a container. `{"$ref":"badge"}` pointing at a rectangle answers `187 can't contain
  layers`.

## Templates

```bash
echo '[{"command":"template.list"}]' > tl.json && figcraft-cli run tl.json
```

```json
{"id":"mobile-app","kind":"app","name":"Mobile app","size":"390 × 844","description":"Four screens …"}
```

`file.newFromTemplate {template:"mobile-app"}` gives structure and a look to start from — screens, components, a prototype flow. It is a starting point, not the user's design language: read `info` afterwards and change the tokens before building on it.

## File access and reproducibility

- `--automation-read-root DIR` / `--automation-write-root DIR` (repeatable, the folder must exist;
  a read-only run cannot write at all). A root that does not exist is caught before any work
  starts: `error: --automation-write-root /tmp/does-not-exist-xyz: No such file or directory`.
  `scripts/figcraft-open.sh` takes the same flags for the app launch and checks the folders first, so
  a mistyped root fails in the shell rather than after a window appeared.
- A refusal names the folders that may be written: `automation path rejected: /tmp is outside the
  folders that may be written: /private/tmp/…/out`. Change the target; do not retry at another path.
  The same guard holds on the live side for an app launched with roots — see
  [live-control.md](live-control.md).
- `--no-system-fonts` (or `FIGCRAFT_NO_SYSTEM_FONTS=1`) draws with the built-in fonts only, so a render matches on every machine. Without it, installed fonts are indexed the first time text is laid out (~60 ms warm).
- `figcraft-cli info file.figcraft` is the cheap summary — node, style, variable and image counts, top-level frames, and `missing font` lines.

## Formats that go in and out

```bash
figcraft-cli info design.figcraft
figcraft-cli run chunk.json --out design.svg          # or .png .jpg .webp .pdf .fig .penpot .json
figcraft-cli convert design.figcraft design.penpot
figcraft-cli export design.figcraft -o expdir --scale 2      # one file per top-level frame
figcraft-cli render design.figcraft -o preview.png --scale 2 # the whole page with its background
```

Foreign formats are read directly: `.penpot`, `.fig`, `.sketch`, REST file JSON and `.svg` open with `warnings` for whatever was left out; an image opens as an image layer. `.fig`, `.penpot` and SVG do not round-trip every feature — report the `note:` lines the command prints.

## Where headless work must not land

Never `--out` (or `convert`, or `export -o`) onto a document the user has open in the app: the app's own save clobbers it, and the canvas never sees the change. Save under a new name and tell them where it is, or do the edits live.
