# figcraft — an Agent Skill for designing in FigCraft

![logo](assets/logo.svg)

[![Agent Skills](https://img.shields.io/badge/Agent_Skills-spec-111827)](https://agentskills.io/specification)
[![figcraft--cli](https://img.shields.io/badge/verified_against-figcraft--cli_0.15.0-4F46E5)](https://github.com/storytold/figcraft/blob/main/docs/cli.md)
[![tests](https://github.com/antonboehner/figcraft-agent-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/antonboehner/figcraft-agent-skill/actions/workflows/validate.yml)
[![MIT](https://img.shields.io/badge/license-MIT-6B7280)](LICENSE)

An [Agent Skill](https://agentskills.io/specification) that teaches a coding agent to build and edit
designs in [FigCraft](https://getartcraft.com/apps/figcraft), the Figma alternative, through its CLI —
either in the window the user is watching, or headless on `.figcraft` files. No MCP required: the
control channel and `figcraft-cli run` reach the same 635 commands.

It is written for the way agents actually fail here: a design script is **one undo step and
all-or-nothing**, so one wrong parameter name throws away thirty good steps. This skill puts a
pre-flight in front of every chunk and reads the result back afterwards.

## Install

Without git: download `figcraft-skill-v0.1.0.zip` from the [latest release](https://github.com/antonboehner/figcraft-agent-skill/releases) and unpack it straight into your skills folder — the archive already holds a folder named `figcraft`.

```bash
unzip figcraft-skill-v0.1.0.zip -d ~/.agents/skills/
```

With git:

```bash
git clone https://github.com/antonboehner/figcraft-agent-skill.git
ln -s "$PWD/figcraft-agent-skill/figcraft" ~/.agents/skills/figcraft
```

Needs `figcraft-cli` on `PATH` (0.15.0 or newer), the FigCraft app for live work, and `python3` for
the three bundled scripts.

## Live, when the user is watching

```bash
figcraft/scripts/figcraft-open.sh 7979            # attach if the port answers, else start the app
figcraft/scripts/figctl.py ping                   # which window, which document
figcraft/scripts/check_chunk.py chunk.json        # pre-flight against the installed catalog
figcraft/scripts/figctl.py run chunk.json --window 1 --label "Card + tokens" --agent my-agent
figcraft/scripts/figctl.py inspect --depth 3 --fields name,type,width,height
figcraft/scripts/figctl.py render /tmp/shot.png --window 1 --scale 2 --ids 2
```

## Headless, when nobody is watching

```bash
figcraft-cli run chunk.json --out design.figcraft --automation-write-root "$PWD/design"
figcraft-cli info design.figcraft
figcraft-cli export design.figcraft -o out --scale 2
```

## How the skill works

1. **Pick the mode and say which one you are in.** Live needs a control port; a headless `run` can
   never touch an open window, and never writes onto a file the app is showing.
2. **Look commands up filtered.** `figcraft-cli commands --filter layout` — the full catalog is 635
   commands and 183 KB, and dumping it is the cheapest way to waste a context window.
3. **Write a chunk of 5–30 steps:** one card, one header, one screen section. One chunk = one
   `command.batch` = one undo step the user can roll back.
4. **Validate before running.** `check_chunk.py` checks every command id, every parameter name,
   `props` placement, scalar-vs-list ids and batch-local `$ref` against the installed catalog, and
   returns the mistake as a sentence: *no parameter "gap" here — layer properties such as "gap"
   belong in props.gap*.
5. **Verify after running.** Structural reads always (`info`, bounded `node.get`,
   `text.missingFonts`); a rendered image when the model can look at one — and an explicit statement
   that visual confirmation was skipped when it cannot.

`references/` carries the depth, loaded only when the task needs it: `live-control`, `headless-run`,
`command-cheatsheet`, `design-craft`, `verification`, `handoff`, `beyond-design` (the map of all 61
command namespaces, including prototype flows, comments, boards, libraries, versions and branches).

## What is verified and what is claimed

Everything in the references was run against `figcraft-cli 0.15.0` and the macOS app, including the
error messages quoted there. `scripts/check_chunk.py` is not a linter written from documentation: it
parses the CLI's own catalog and its rules come from failures the app actually returned — `layout.add`
wrapping a frame that already had auto layout, a variant axis named `Button/state` rather than `state`,
`importPath` refusing slashes, a nested batch that cannot see the outer chunk's names.

`tests/` runs in CI without FigCraft: the validator is tested offline against a catalog snapshot in
`tests/fixtures/`, and `tests/packaging.py` checks the skill against the Agent Skills spec (name
matching its folder, description limits, every reference named from `SKILL.md`, body under 300 lines).

The limits are stated in the skill rather than smoothed over: a headless session cannot touch an open
window, a code connection is a name plus a template and not a live sync, `.fig`/`.penpot`/SVG
conversions come with `warnings` about what they dropped, and `pref.*`, `collab.*`, `version.*`,
`branch.*` and `plugin.*` are reachable but reach outward — into the user's app, other people, or a
server.

## Layout

```
figcraft/                  the skill itself
├── SKILL.md               decision loop, chunk policy, token rules, gotchas
├── references/            six+ one topic each, named from SKILL.md with its trigger
└── scripts/
    ├── figctl.py          NDJSON control client: ping, inspect, node, run, batch, render, call
    ├── figcraft-open.sh   check the port, otherwise start the app itself (with roots)
    └── check_chunk.py     pre-flight a chunk against the installed catalog
assets/                    logo (built in FigCraft and exported; the raw export is next to it)
tests/                     packaging checks, offline validator tests, fixtures
```

## Not affiliated

Not affiliated with FigCraft or ArtCraft. FigCraft and its CLI are their respective projects; this
repository only holds the skill, its scripts and its tests. MIT licensed.
