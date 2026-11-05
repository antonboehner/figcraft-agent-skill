#!/usr/bin/env python3
"""Packaging checks for the figcraft skill (Agent Skills spec).

Run:  python3 tests/packaging.py
Exits 1 with a list of problems, 0 when the skill is packaged correctly.
"""
import os
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None


def read_frontmatter(block):
    """Parse the frontmatter. pyyaml when installed, otherwise the subset SKILL.md uses."""
    if yaml:
        return yaml.safe_load(block) or {}
    meta, key, folded, nested = {}, None, None, {}
    for line in block.splitlines():
        top = re.match(r"^([a-z][a-z-]*):\s*(.*)$", line)
        if top and not line.startswith(" "):
            if folded is not None:
                meta[key] = " ".join(folded)
                folded = None
            key, value = top.group(1), top.group(2).strip()
            if value in (">-", ">"):
                folded = []
            elif value:
                meta[key] = value.strip('"')
            else:
                nested = {}
                meta[key] = nested
                key = None
        elif folded is not None and line.strip():
            folded.append(line.strip())
        elif key is None and line.startswith("  "):
            pair = re.match(r"^\s+([a-z][a-z-]*):\s*(.*)$", line)
            if pair:
                nested[pair.group(1)] = pair.group(2).strip().strip('"')
    if folded is not None:
        meta[key] = " ".join(folded)
    return meta


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "figcraft")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
MAX_BODY_LINES = 300
problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


if not os.path.isfile(SKILL):
    print(f"no skill at {SKILL}")
    raise SystemExit(1)

text = open(SKILL, encoding="utf-8").read()
parts = text.split("---\n")
check(len(parts) >= 3, "SKILL.md needs YAML frontmatter between two --- lines")
meta = read_frontmatter(parts[1]) if len(parts) >= 3 else {}

name = meta.get("name", "")
check(isinstance(name, str) and name, "frontmatter needs a name")
check(len(name) <= 64, f"name is longer than 64 characters ({len(name)})")
check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name or "") is not None,
      f"name {name!r} must be lowercase letters, digits and hyphens only")
check(name == os.path.basename(SKILL_DIR),
      f"name {name!r} must match its folder {os.path.basename(SKILL_DIR)!r}")

description = meta.get("description", "")
check(isinstance(description, str) and description.strip(), "frontmatter needs a description")
check(len(description or "") <= 1024, f"description is longer than 1024 characters ({len(description or '')})")
check(len((description or "").split()) >= 12, "description is too thin to trigger reliably")

compatibility = meta.get("compatibility", "")
check(len(compatibility or "") <= 500, f"compatibility is longer than 500 characters ({len(compatibility or '')})")

metadata = meta.get("metadata", {})
check(isinstance(metadata, dict), "metadata must be a mapping")
check(all(isinstance(k, str) and isinstance(v, str) for k, v in (metadata or {}).items()),
      "metadata must map strings to strings")

body = "---\n".join(parts[2:])
check(len(body.splitlines()) <= MAX_BODY_LINES,
      f"SKILL.md body is {len(body.splitlines())} lines; keep it under {MAX_BODY_LINES} and move detail into references/")
check(len(body.split()) * 1.4 < 5000, "SKILL.md body is over ~5000 tokens; move detail into references/")

linked = set(re.findall(r"\]\((references/[^)#]+)\)", text))
for target in sorted(linked):
    check(os.path.isfile(os.path.join(SKILL_DIR, target)), f"SKILL.md links to a missing file: {target}")
if os.path.isdir(os.path.join(SKILL_DIR, "references")):
    for name_in_dir in sorted(os.listdir(os.path.join(SKILL_DIR, "references"))):
        if name_in_dir.endswith(".md"):
            check(f"references/{name_in_dir}" in linked,
                  f"references/{name_in_dir} is never named from SKILL.md - it would never be loaded")

for ref_dir in ("references", "scripts"):
    base = os.path.join(SKILL_DIR, ref_dir)
    if not os.path.isdir(base):
        continue
    for entry in sorted(os.listdir(base)):
        if not entry.endswith(".md"):
            continue
        inner = open(os.path.join(base, entry), encoding="utf-8").read()
        for link in re.findall(r"\]\(([^)]+\.md)\)", inner):
            if link.startswith("http"):
                continue
            resolved = os.path.normpath(os.path.join(SKILL_DIR, ref_dir, link))
            check(os.path.isfile(resolved), f"{ref_dir}/{entry} links to a missing file: {link}")
            check(os.path.dirname(resolved) == os.path.join(SKILL_DIR, "references"),
                  f"{ref_dir}/{entry} links outside references/ - keep the chain one level deep: {link}")

for script in re.findall(r"scripts/([A-Za-z0-9_.-]+\.(?:py|sh))", text):
    path = os.path.join(SKILL_DIR, "scripts", script)
    check(os.path.isfile(path), f"SKILL.md names scripts/{script}, which is not there")
    if os.path.isfile(path):
        check(os.access(path, os.X_OK), f"scripts/{script} is not executable")

print(f"skill: {name}  body: {len(body.splitlines())} lines  references linked: {len(linked)}")
if problems:
    for problem in problems:
        print(f"problem: {problem}")
    raise SystemExit(1)
print("packaging is clean.")
