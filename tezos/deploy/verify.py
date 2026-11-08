"""Check that a deployed contract is exactly what this source builds.

    tezos/.venv/bin/python tezos/deploy/verify.py --network shadownet \\
        --address KT1... --compiled tezos/deployments/shadownet-v1/collection.json

Two checks against TzKT:
- the code on chain equals <name>.json;
- the storage it was deployed with equals <name>.storage.json exactly: every
  field, and every entry of every big map (so no pre-set minter, balance,
  vote or contract metadata could hide in it). The admin and the guardian
  must also be two different wallets.

Anyone can run it: check out the deployment's tag, install the pinned
SmartPy and run deploy/build.py with the addresses in that deployment's
<name>.storage.json.
"""

import argparse
import hashlib
import json
import ssl
import sys
import urllib.request
from datetime import datetime, timezone

import certifi

TZKT = {"mainnet": "https://api.tzkt.io", "shadownet": "https://api.shadownet.tzkt.io"}
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
WALLET_PREFIX = {0: "06a19f", 1: "06a1a1", 2: "06a1a4", 3: "06a1a6"}  # tz1 tz2 tz3 tz4
CONTRACT_PREFIX = "025a79"  # KT1


def fetch(network, path):
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(TZKT[network] + path, timeout=30, context=context) as response:
        return json.load(response)


def base58check(prefix_hex, payload):
    data = bytes.fromhex(prefix_hex) + payload
    data += hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    number, out = int.from_bytes(data, "big"), ""
    while number:
        number, rest = divmod(number, 58)
        out = ALPHABET[rest] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out


def address_text(node, kind):
    """An address or key hash as tz1/KT1 text, whether written as text or bytes."""
    if "string" in node:
        return node["string"]
    raw = bytes.fromhex(node["bytes"])
    if kind == "key_hash":
        return base58check(WALLET_PREFIX[raw[0]], raw[1:21])
    if raw[0] == 0:
        return base58check(WALLET_PREFIX[raw[1]], raw[2:22])
    return base58check(CONTRACT_PREFIX, raw[1:21])


def binary(t):
    """A pair type with more than two arguments, as right-nested pairs."""
    if t["prim"] == "pair" and len(t["args"]) > 2:
        return dict(t, args=[t["args"][0], {"prim": "pair", "args": t["args"][1:]}])
    return t


def split(v):
    """The two halves of a pair value, however it is written."""
    if isinstance(v, list):
        return v[0], (v[1] if len(v) == 2 else v[1:])
    if len(v["args"]) == 2:
        return v["args"]
    return v["args"][0], {"prim": "Pair", "args": v["args"][1:]}


def name(t):
    return t.get("annots", ["?"])[0].lstrip("%")


def fields(t):
    """The names of the top-level fields of a record type, in order."""
    t = binary(t)
    left, right = t["args"]
    head = fields(left) if left["prim"] == "pair" and "annots" not in left else [name(left)]
    if binary(right)["prim"] == "pair" and "annots" not in right:
        return head + fields(right)
    return head + [name(right)]


def canon(t, v, big_map):
    """`v` of type `t` in one comparable form; big_map(ptr, key_type, value_type)
    returns a big map's entries when `v` holds a pointer instead of entries.
    A record's fields come out as one flat list, in order."""
    t = binary(t)
    prim = t["prim"]
    if prim == "pair":
        left, right = split(v)
        out = canon(t["args"][0], left, big_map)
        out = out if t["args"][0]["prim"] == "pair" and "annots" not in t["args"][0] else [out]
        rest = canon(t["args"][1], right, big_map)
        nested = binary(t["args"][1])["prim"] == "pair" and "annots" not in t["args"][1]
        return out + rest if nested else out + [rest]
    if prim in ("address", "key_hash", "contract"):
        return address_text(v, prim)
    if prim == "timestamp":
        if "int" in v:
            return int(v["int"])
        text = v["string"].replace("Z", "+00:00")
        return int(datetime.fromisoformat(text).astimezone(timezone.utc).timestamp())
    if prim in ("nat", "int", "mutez"):
        return int(v["int"])
    if prim == "string":
        return v["string"]
    if prim == "bytes":
        return v["bytes"].lower()
    if prim in ("bool", "unit"):
        return v["prim"]
    if prim == "option":
        return None if v["prim"] == "None" else ["Some", canon(t["args"][0], v["args"][0], big_map)]
    if prim in ("list", "set"):
        return [canon(t["args"][0], x, big_map) for x in v]
    if prim in ("map", "big_map"):
        if isinstance(v, dict) and "int" in v:
            return big_map(int(v["int"]), t["args"][0], t["args"][1])
        return sorted(json.dumps([canon(t["args"][0], e["args"][0], big_map),
                                  canon(t["args"][1], e["args"][1], big_map)]) for e in v)
    if prim == "or":
        side = 0 if v["prim"] == "Left" else 1
        return [v["prim"], canon(t["args"][side], v["args"][0], big_map)]
    raise SystemExit("verify.py can't compare a %s in storage yet" % prim)


def normalized(code):
    """Michelson sections sorted (SmartPy writes storage first, TzKT parameter first)."""
    def key(section):
        label = section["args"][0].get("string", "") if section["prim"] == "view" else ""
        return (section["prim"], label)
    return json.dumps(sorted(code, key=key), sort_keys=True, separators=(",", ":"))


def compare_storage(network, address, storage_type, expected_storage):
    """The names of the fields whose starting value differs, and the expected values."""
    level = fetch(network, "/v1/operations/originations?originatedContract=%s&select=level"
                  % address)[0]

    def remote_big_map(ptr, key_type, value_type):
        keys = fetch(network, "/v1/bigmaps/%d/historical_keys/%d?micheline=3&limit=10000"
                     % (ptr, level))
        return sorted(json.dumps([canon(key_type, json.loads(k["key"]), None),
                                  canon(value_type, json.loads(k["value"]), None)])
                      for k in keys if k["active"])

    raw = fetch(network, "/v1/contracts/%s/storage/raw?level=%d" % (address, level))
    deployed = canon(storage_type, raw, remote_big_map)
    expected = canon(storage_type, expected_storage, None)
    names = fields(storage_type)
    assert len(names) == len(deployed) == len(expected), (names, len(deployed), len(expected))
    differs = [n for n, got, want in zip(names, deployed, expected) if got != want]
    return differs, dict(zip(names, expected))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", required=True, choices=sorted(TZKT))
    parser.add_argument("--address", required=True)
    parser.add_argument("--compiled", required=True)
    args = parser.parse_args()
    with open(args.compiled) as handle:
        code = json.load(handle)
    with open(args.compiled.replace(".json", ".storage.json")) as handle:
        expected_storage = json.load(handle)
    storage_type = [s for s in code if s["prim"] == "storage"][0]["args"][0]

    problems = []
    remote_code = fetch(args.network, "/v1/contracts/%s/code?format=0" % args.address)
    if normalized(code) != normalized(remote_code):
        problems.append("the code differs")
    differs, values = compare_storage(args.network, args.address, storage_type, expected_storage)
    problems += ["its starting %s differs" % n for n in differs]
    if values.get("administrator") == values.get("guardian"):
        problems.append("its admin and guardian are the same wallet")

    if problems:
        print("DIFFERENT: %s: %s" % (args.address, "; ".join(problems)))
        sys.exit(1)
    print("same: %s runs %s, with exactly its starting storage" % (args.address, args.compiled))


if __name__ == "__main__":
    main()
