"""Write the exact code and starting storage to deploy, for one network.

Deploy in this order (each needs the addresses of the ones before):

    tezos/.venv/bin/python tezos/deploy/build.py payout --network shadownet \\
        --admin tz1... --guardian tz1... --wallet tz1...
    tezos/.venv/bin/python tezos/deploy/build.py collection --network shadownet \\
        --admin tz1... --guardian tz1... --payout KT1...
    tezos/.venv/bin/python tezos/deploy/build.py sale --network shadownet \\
        --admin tz1... --guardian tz1... --collection KT1...

--wallet is the payout wallet; --payout is the payout contract.
Writes tezos/deployments/<network>-<version>/<name>.tz and <name>.storage.tz
(plus .json). Paste those two .tz files into SmartPy's deploy page
(smartpy.io/origination) and sign with the admin wallet.
"""

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
# SmartPy's compiler writes scenario output relative to the directory it
# starts in, which is fixed when smartpy is first imported.
os.makedirs(BUILD, exist_ok=True)
os.chdir(BUILD)
sys.path.insert(0, HERE)

import smartpy as sp  # noqa: E402

from contracts.collection import collection  # noqa: E402
from contracts.payout import payout  # noqa: E402
from contracts.sale import sale  # noqa: E402
from deploy.metadata import collection_metadata, on_chain, plain_metadata  # noqa: E402
from deploy.michelson import script_text, value_text  # noqa: E402

NAMES = {
    "shadownet": (
        "Hussain.Art (Shadownet test)",
        "Test deployment of Hussain Marzooq's collection contracts.",
    ),
}


NEEDS = {"payout": ["wallet"], "collection": ["payout"], "sale": ["collection"]}
WALLET, CONTRACT = ("tz1", "tz2", "tz3"), ("KT1",)


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", choices=sorted(NEEDS))
    parser.add_argument("--network", required=True, choices=sorted(NAMES))
    parser.add_argument("--version", default="v1")
    parser.add_argument("--admin", required=True)
    parser.add_argument("--guardian", required=True)
    parser.add_argument("--wallet")
    parser.add_argument("--collection")
    parser.add_argument("--payout")
    args = parser.parse_args()
    for name in NEEDS[args.contract]:
        if not getattr(args, name):
            parser.error("the %s contract needs --%s" % (args.contract, name))
    kinds = {"admin": WALLET, "guardian": WALLET, "wallet": WALLET,
             "collection": CONTRACT, "payout": CONTRACT}
    for name, prefixes in kinds.items():
        value = getattr(args, name)
        if value and not value.startswith(prefixes):
            parser.error("--%s must start with %s" % (name, " or ".join(prefixes)))
    if args.admin == args.guardian:
        parser.error("the admin and the guardian must be two different wallets")
    return args


def originate(args):
    name, description = NAMES[args.network]
    scenario = "deploy_%s_%s" % (args.network, args.contract)
    sc = sp.test_scenario(scenario)
    admin, guardian = sp.address(args.admin), sp.address(args.guardian)
    if args.contract == "collection":
        sc += collection.Collection(
            admin, guardian, sp.address(args.payout),
            on_chain(collection_metadata(name, description)),
        )
    elif args.contract == "payout":
        sc += payout.Payout(
            admin, guardian, sp.key_hash(args.wallet),
            on_chain(plain_metadata(name + " payout",
                                    "Passes every sale and royalty on to the payout wallet.")),
        )
    else:
        sc += sale.Sale(
            admin, guardian, sp.address(args.collection),
            on_chain(plain_metadata(name + " sale", "Fixed-price sales of the collection.")),
        )
    return scenario


def main():
    args = arguments()
    scenario = originate(args)
    out = os.path.join(HERE, "deployments", "%s-%s" % (args.network, args.version))
    os.makedirs(out, exist_ok=True)
    for kind, target, to_text in [("contract", "", script_text), ("storage", ".storage", value_text)]:
        source = os.path.join(BUILD, scenario, "step_001_cont_0_%s.json" % kind)
        base = os.path.join(out, args.contract + target)
        shutil.copyfile(source, base + ".json")
        with open(source) as handle, open(base + ".tz", "w") as text:
            text.write(to_text(json.load(handle)))
    print("wrote", os.path.relpath(out, HERE))


if __name__ == "__main__":
    main()
