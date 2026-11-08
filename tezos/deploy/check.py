"""Before deploying: a public node typechecks the code and measures its size.

    tezos/.venv/bin/python tezos/deploy/check.py --network shadownet \\
        tezos/deployments/shadownet-v1/collection

Reads <base>.json and <base>.storage.json. Read-only: nothing is signed or sent.
A whole operation must stay under the protocol's 32,768 bytes.
"""

import argparse
import json
import ssl
import urllib.request

import certifi

RPC = {"mainnet": "https://rpc.tzkt.io/mainnet", "shadownet": "https://rpc.shadownet.teztnets.com"}
CONTEXT = ssl.create_default_context(cafile=certifi.where())
NOBODY = "tz1burnburnburnburnburnburnburjAYjjX"


def call(network, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(RPC[network] + path, data=data,
                                     headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=60, context=CONTEXT) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", required=True, choices=sorted(RPC))
    parser.add_argument("base")
    args = parser.parse_args()
    with open(args.base + ".json") as a, open(args.base + ".storage.json") as b:
        code, storage = json.load(a), json.load(b)
    head = "/chains/main/blocks/head"
    call(args.network, head + "/helpers/scripts/typecheck_code",
         {"program": code, "gas": "1040000", "legacy": False})
    origination = {"kind": "origination", "source": NOBODY, "fee": "1000000", "counter": "1",
                   "gas_limit": "100000", "storage_limit": "60000", "balance": "0",
                   "script": {"code": code, "storage": storage}}
    forged = call(args.network, head + "/helpers/forge/operations",
                  {"branch": call(args.network, head + "/hash"), "contents": [origination]})
    size = len(forged) // 2
    print("typechecks; origination is %d bytes of 32768" % size)
    if size > 32768:
        raise SystemExit("too large to deploy in one operation")


if __name__ == "__main__":
    main()
