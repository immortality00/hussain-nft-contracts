"""The compact Michelson written for deployment parses back to the exact compiled code.

A small Micheline reader (tokens, sequences, primitive applications), used
only here, reads deploy/michelson.py's output; the result must equal
SmartPy's JSON for all three contracts and their starting storage.
"""

import glob
import json
import os
import re

from deploy.michelson import script_text, value_text

TOKEN = re.compile(r'\s*(?:(\")((?:[^"\\]|\\.)*)\"|(0x[0-9a-fA-F]*)|(-?\d+)|([(){};])|([^\s(){};"]+))')


def tokens(text):
    position, out = 0, []
    while position < len(text.rstrip()):
        match = TOKEN.match(text, position)
        quote, string, hexa, number, punct, word = match.groups()
        out.append(("string", json.loads('"%s"' % string)) if quote else ("bytes", hexa[2:]) if hexa
                   else ("int", number) if number else ("punct", punct) if punct else ("word", word))
        position = match.end()
    return out


def parse(items, i=0, nested=False):
    kind, value = items[i]
    if kind in ("string", "bytes", "int"):
        return {kind: value}, i + 1
    if value == "{":
        seq, i = [], i + 1
        while items[i] != ("punct", "}"):
            node, i = parse(items, i)
            seq.append(node)
            i += 1 if items[i] == ("punct", ";") else 0
        return seq, i + 1
    if value == "(":
        node, i = parse(items, i + 1)
        return node, i + 1
    node, i = {"prim": value}, i + 1
    while i < len(items) and items[i][0] == "word" and items[i][1][0] in "%@:":
        node.setdefault("annots", []).append(items[i][1])
        i += 1
    if not nested:
        while i < len(items) and items[i] not in (("punct", ";"), ("punct", "}"), ("punct", ")")):
            arg, i = parse(items, i, nested=True)
            node.setdefault("args", []).append(arg)
    return node, i


def read_script(text):
    items, sections, i = tokens(text), [], 0
    while i < len(items):
        node, i = parse(items, i)
        sections.append(node)
        i += 1
    return sections


def same(code, sections):
    key = lambda s: (s["prim"], s["args"][0].get("string", "") if s["prim"] == "view" else "")
    return sorted(code, key=key) == sorted(sections, key=key)


def main():
    files = glob.glob(os.path.join("interface", "step_*_cont_*_contract.json"))
    assert len(files) == 3, "run test_interface.py first: %s" % files
    for path in files:
        with open(path) as handle:
            code = json.load(handle)
        assert same(code, read_script(script_text(code))), path
        with open(path.replace("_contract.json", "_storage.json")) as handle:
            storage = json.load(handle)
        assert parse(tokens(value_text(storage)))[0] == storage, path
    print("michelson round trip ok")


main()
