"""Shared test setup: accounts, times, and the three contracts deployed together."""

import os
import re
from types import SimpleNamespace

import smartpy as sp

from contracts.collection import collection
from contracts.payout import payout
from contracts.sale import sale
from deploy.metadata import collection_metadata, on_chain, plain_metadata, utf8

T0 = 1_000_000
DELAY = 172_800
DAY = 86_400
WEEK = 7 * DAY
CID = "bafkreicrvkn7d4pfmx4yrui27dnccrefuyxzc4heautht4qmizzgu2vnoy"

# SmartPy derives test accounts from their names, so these never change
# (test_payout.py checks them). Used to read payments from scenario logs.
WALLETS = {
    "payout": "tz1P7bfnTFQsk1fFEiZKsf6LHf8FHVefBr5Z",
    "alice": "tz1h4EsGunH2Ue1T2uNs8mfKZ8XZoQji3HcK",
    "bob": "tz1hJgZdhnRGvg5XD6pYxRCsbWh4jg5HQ476",
}


def at(seconds):
    return sp.timestamp(seconds)


def ipfs(n=0):
    """A distinct IPFS metadata link for artwork n."""
    return utf8("ipfs://%s/%d" % (CID, n))


def accounts():
    # "minter" is a wallet added as a second minter, so tests can mint directly.
    names = ["admin", "guardian", "payout", "buyer", "alice", "bob", "stranger",
             "new_admin", "new_guardian", "minter"]
    return SimpleNamespace(**{n: sp.test_account(n) for n in names})


def deploy(sc, confirm_minter=True):
    """The three contracts; the sale contract and the test minter wallet added
    as minters by both wallets' votes."""
    acc = accounts()
    p = payout.Payout(
        acc.admin.address, acc.guardian.address, acc.payout.public_key_hash,
        on_chain(plain_metadata("Test payout", "Test payout contract")),
    )
    sc += p
    c = collection.Collection(
        acc.admin.address, acc.guardian.address, p.address,
        on_chain(collection_metadata("Test", "Test collection")),
    )
    sc += c
    s = sale.Sale(
        acc.admin.address, acc.guardian.address, c.address,
        on_chain(plain_metadata("Test sale", "Test sale contract")),
    )
    sc += s
    if confirm_minter:
        for minter in (s.address, acc.minter.address):
            c.propose_minter(minter, _sender=acc.admin, _now=at(T0))
            c.propose_minter(minter, _sender=acc.guardian, _now=at(T0))
    return SimpleNamespace(acc=acc, collection=c, payout=p, sale=s, next_id=0)


def mint(env, token_id, amount, to, paid=None, now=T0 + DELAY, sender=None, **kwargs):
    """Mint directly as the test minter wallet, paying `paid` mutez (default: one
    mutez a copy, the default floor)."""
    env.collection.mint(
        [sp.record(to_=to.address, token_id=token_id, amount=amount)],
        _sender=sender or env.acc.minter,
        _amount=sp.mutez(amount if paid is None else paid),
        _now=at(now),
        **kwargs,
    )


def some(value):
    return None if value is None else sp.Some(value)


def register(env, cap=None, mint_end=None, floor=1, now=T0 + DELAY):
    """Register an artwork (mint_end in seconds, floor in mutez); returns its token id."""
    env.collection.register(
        metadata_uri=ipfs(env.next_id),
        cap=some(cap),
        mint_end=some(None if mint_end is None else at(mint_end)),
        floor=sp.mutez(floor),
        _sender=env.acc.admin,
        _now=at(now),
    )
    env.next_id += 1
    return env.next_id - 1


def list_for_sale(env, token_id, price=1_000_000, start=T0, end=None, max_per_buy=5,
                  now=T0 + DELAY):
    env.sale.set_sale(
        token_id=token_id,
        price=sp.mutez(price),
        start=at(start),
        end=some(None if end is None else at(end)),
        max_per_buy=max_per_buy,
        _sender=env.acc.admin,
        _now=at(now),
    )


def balance(c, owner, token_id):
    return c.data.ledger.get((owner.address, token_id), default_value=sp.nat(0))


def payments(scenario):
    """Every payment that reached a wallet in a finished scenario, in order:
    (mutez, wallet address). Only a wallet counts: SmartPy's log also lists
    the outputs of an operation that later fails, but a payment to a wallet
    is always the last step of a purchase, so it is logged only if the whole
    purchase went through."""
    out, block = [], None
    with open(os.path.join(scenario, "log.txt")) as log:
        for line in log:
            text = line.strip()
            if text == "+ Transfer":
                block = {}
            elif block is not None and text.startswith(("params:", "amount:", "to:")):
                key, value = text.split(":", 1)
                block[key] = value.strip()
                if key == "to":
                    address = re.search(r"sp\.address\('([^']+)'\)", value).group(1)
                    if block["params"] == "()" and address.startswith("tz"):
                        unit, number = re.fullmatch(r"sp\.(tez|mutez)\((\d+)\)", block["amount"]).groups()
                        out.append((int(number) * (1_000_000 if unit == "tez" else 1), address))
                    block = None
    return out
