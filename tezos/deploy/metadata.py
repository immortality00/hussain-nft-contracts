"""The contracts' own TZIP-16 metadata, stored on-chain and fixed at deployment.

There is no entry point to change it: TZIP-12 tells indexers to prefer views
named in this metadata over the stored token metadata, so editable contract
metadata could change how every artwork's metadata is shown.
"""

import json

import smartpy as sp

SMARTPY_VERSION = "0.25.1"
REPO = "https://github.com/immortality00/hussain-nft-contracts"


def utf8(text):
    """UTF-8 bytes of `text`, as SmartPy bytes."""
    return sp.bytes("0x" + text.encode("utf-8").hex())


def _common(name, description, interfaces):
    return {
        "name": name,
        "description": description,
        "version": "1.0.0",
        "homepage": "https://hussain.art",
        "authors": ["Hussain Marzooq <https://hussain.art>"],
        "license": {"name": "MIT"},
        "interfaces": interfaces,
        "source": {"tools": ["SmartPy " + SMARTPY_VERSION], "location": REPO},
    }


def collection_metadata(name, description):
    content = _common(name, description, ["TZIP-012", "TZIP-016", "TZIP-021"])
    content["permissions"] = {
        "operator": "owner-or-operator-transfer",
        "receiver": "owner-no-hook",
        "sender": "owner-no-hook",
    }
    return content


def plain_metadata(name, description):
    """The sale and payout contracts' metadata: no tokens, no views."""
    return _common(name, description, ["TZIP-016"])


def on_chain(content):
    """The metadata big map holding `content` itself (TZIP-16 tezos-storage)."""
    text = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    return sp.big_map({"": utf8("tezos-storage:content"), "content": utf8(text)})
