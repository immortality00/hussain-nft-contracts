"""Micheline JSON to compact Michelson text, without comments.

SmartPy's .tz output carries a stack-type comment on every line (10 MB for
the collection contract); the code itself is the same as its .json output.
This writes that .json as plain Michelson, to read. Deploy the .json, never
this text: SmartPy rewrites pasted Michelson. deploy/verify.py checks the
deployed code exactly.
"""

import json


def to_michelson(node, nested=False):
    """`nested`: the node is an argument of another primitive (needs parentheses)."""
    if isinstance(node, list):
        return "{ %s }" % "; ".join(to_michelson(item) for item in node) if node else "{}"
    if "int" in node:
        return node["int"]
    if "string" in node:
        return json.dumps(node["string"], ensure_ascii=True)
    if "bytes" in node:
        return "0x" + node["bytes"]
    args = node.get("args", [])
    text = " ".join([node["prim"]] + node.get("annots", []) + [to_michelson(a, True) for a in args])
    if nested and (args or node.get("annots")):
        return "(%s)" % text
    return text


def script_text(code):
    """A full script: sections in Michelson's order, one per line."""
    order = {"parameter": 0, "storage": 1, "code": 2, "view": 3}
    sections = sorted(code, key=lambda part: order[part["prim"]])
    return ";\n".join(to_michelson(part) for part in sections) + ";\n"


def value_text(value):
    return to_michelson(value) + "\n"
