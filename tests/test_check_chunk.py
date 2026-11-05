#!/usr/bin/env python3
"""Self-test for figcraft/scripts/check_chunk.py, offline.

Run:  python3 tests/test_check_chunk.py
No FigCraft needed: the validator reads tests/fixtures/commands.json instead of the CLI.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "figcraft", "scripts", "check_chunk.py")
CATALOG = os.path.join(ROOT, "tests", "fixtures", "commands.json")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def run(chunk_path, *extra):
    proc = subprocess.run([sys.executable, CHECK, chunk_path, "--catalog", CATALOG, *extra],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def write_chunk(name, text):
    path = os.path.join(tempfile.mkdtemp(), name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


failures = []


def expect(label, condition, detail=""):
    if condition:
        print(f"ok   {label}")
    else:
        print(f"FAIL {label} {detail}")
        failures.append(label)


code, out, err = run(os.path.join(FIXTURES, "good_chunk.json"))
expect("a verified chunk passes", code == 0 and "ok," in out, f"(exit {code}: {err})")

code, out, err = run(os.path.join(FIXTURES, "bad_chunk.json"))
expect("a broken chunk is refused", code == 1, f"(exit {code})")
for wanted in ['belong in props.gap', '"parent" takes one id',
               'missing required parameter collection', 'unknown command "node.creat"',
               "names no earlier step"]:
    expect(f"the message names it: {wanted}", wanted in err, f"(stderr: {err[:200]})")

forward = write_chunk("forward.json", json.dumps([
    {"command":"node.create","as":"b","params":{"type":"text","parent":{"$ref":"a"},"text":"x"}},
    {"command":"node.create","as":"a","params":{"type":"frame","name":"A"}}]))
code, out, err = run(forward)
expect("a reference to a later step is refused", code == 1 and "no earlier step" in err, err[:200])

foreign = write_chunk("foreign.json", json.dumps([
    {"command":"node.set","params":{"ids":[{"$ref":"card"}],"name":"x"}}]))
code, out, err = run(foreign)
expect("batch-local references are enforced", code == 1 and "batch-local" in err, err[:200])

jsonl = write_chunk("steps.jsonl", "\n".join([
    json.dumps({"command":"node.create","as":"f","params":{"type":"frame","name":"F"}}),
    json.dumps({"command":"layout.add","params":{"ids":[{"$ref":"f"}],"direction":"vertical"}})]))
code, out, err = run(jsonl)
expect("JSON lines scripts are accepted", code == 0, err[:200])

wrapped = write_chunk("wrapped.json", json.dumps({"commands": [
    {"command":"node.create","params":{"type":"frame","name":"W"}}]}))
code, out, err = run(wrapped)
expect("the {\"commands\": [...]} wrapper is accepted", code == 0, err[:200])

nested = write_chunk("nested.json", json.dumps([
    {"command":"command.batch","params":{"label":"inner","commands":[
        {"command":"node.create","as":"x","params":{"type":"frame","name":"A"}},
        {"command":"node.create","as":"y","params":{"type":"frame","name":"B","parent":{"$ref":"x"}}}]}},
    {"command":"node.create","as":"x","params":{"type":"frame","name":"outer"}}]))
code, out, err = run(nested)
expect("a nested batch gets its own reference scope", code == 0, err[:200])

badkey = write_chunk("badkey.json", json.dumps([
    {"command":"node.create","params":{"type":"frame","name":"K"},"parameter":{}}]))
code, out, err = run(badkey)
expect("only command/params/as are legal step keys", code == 1 and "command" in err and "params" in err, err[:200])

code, out, err = run(os.path.join(FIXTURES, "good_chunk.json"), "--catalog", "/nope/missing.json")
expect("a missing catalog file fails loudly", code == 2 and "cannot be read" in err, err[:200])

if failures:
    print(f"\n{len(failures)} check(s) failed.")
    sys.exit(1)
print("\nall check_chunk self-tests passed.")
