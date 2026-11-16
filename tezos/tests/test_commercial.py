"""Commercial rights on the collection: offered only by a 1/1 registered with a
commercial floor, added by a minter only for the copy's holder and for at
least that floor (sent on to the payout wallet), set once, never cleared,
and following the token to every new owner."""

import smartpy as sp

from tests.setup import (
    DELAY, T0, WALLETS, at, balance, deploy, ipfs, mint, payments, register, some,
)

NOW = T0 + DELAY
FLOOR = 1_000_000
RIGHTS_FLOOR = 4_000_000


@sp.module
def bundle():
    mint_request: type = sp.record(
        to_=sp.address, token_id=sp.nat, amount=sp.nat
    ).layout(("to_", ("token_id", "amount")))
    mark_request: type = sp.record(token_id=sp.nat, holder=sp.address).layout(
        ("token_id", "holder")
    )

    class MintThenRights(sp.Contract):
        """A test minter: mints one copy, then asks for the commercial rights
        mark for `holder`, in the same operation."""

        def __init__(self, collection):
            self.data.collection = sp.cast(collection, sp.address)

        @sp.entrypoint
        def go(self, token_id, to_, holder, price, rights):
            sp.cast(token_id, sp.nat)
            sp.cast(price, sp.mutez)
            sp.cast(rights, sp.mutez)
            mint = sp.contract(sp.list[mint_request], self.data.collection,
                               entrypoint="mint").unwrap_some()
            sp.transfer([sp.record(to_=to_, token_id=token_id, amount=1)], price, mint)
            add = sp.contract(mark_request, self.data.collection,
                              entrypoint="add_commercial_rights").unwrap_some()
            sp.transfer(sp.record(token_id=token_id, holder=holder), rights, add)


def add_rights(env, token_id, holder, paid=RIGHTS_FLOOR, sender=None, **kwargs):
    env.collection.add_commercial_rights(
        sp.record(token_id=token_id, holder=holder.address),
        _sender=sender or env.acc.minter, _amount=sp.mutez(paid), _now=at(NOW), **kwargs,
    )


def marked(env, token_id):
    return env.collection.onchain_views.has_commercial_rights(token_id)


@sp.add_test()
def test_register_commercial_floor():
    sc = sp.test_scenario("commercial_register")
    env = deploy(sc)
    c = env.collection

    def try_register(cap, rights_floor, mint_end=None, **kwargs):
        c.register(metadata_uri=ipfs(99), cap=some(cap), floor=sp.mutez(1),
                   mint_end=some(None if mint_end is None else at(mint_end)),
                   commercial_floor=sp.Some(sp.mutez(rights_floor)),
                   _sender=env.acc.admin, _now=at(NOW), **kwargs)

    sc.h2("Only a 1/1 offers commercial rights, never for nothing")
    try_register(5, RIGHTS_FLOOR, _valid=False, _exception="NOT_SINGLE")
    try_register(None, RIGHTS_FLOOR, mint_end=NOW + 10, _valid=False, _exception="NOT_SINGLE")
    try_register(1, 0, _valid=False, _exception="FLOOR_ZERO")
    try_register(1, RIGHTS_FLOOR, mint_end=NOW + 10)
    sc.verify(c.data.editions[0].commercial_floor == sp.Some(sp.mutez(RIGHTS_FLOOR)))
    sc.verify(~c.data.editions[0].commercial)
    sc.verify(c.data.editions[0].cap == sp.Some(1))

    sc.h2("Without a commercial floor, they are never offered")
    env.next_id = 1  # token 0 was registered above, outside the helper
    plain = register(env, cap=1)
    sc.verify(c.data.editions[plain].commercial_floor == None)


@sp.add_test()
def test_commercial_rights():
    sc = sp.test_scenario("commercial_collection")
    env = deploy(sc)
    c, buyer, alice, bob = env.collection, env.acc.buyer, env.acc.alice, env.acc.bob
    art = register(env, cap=1, floor=FLOOR, commercial_floor=RIGHTS_FLOOR)
    plain = register(env, cap=1)
    edition = register(env, cap=5)

    sc.h2("Never before the copy exists, and never for anyone but its holder")
    add_rights(env, art, buyer, _valid=False, _exception="NOT_HOLDER")
    mint(env, art, 1, buyer, paid=FLOOR)
    add_rights(env, art, alice, _valid=False, _exception="NOT_HOLDER")

    sc.h2("Only a minter adds the mark, paying at least the commercial floor")
    add_rights(env, art, buyer, sender=env.acc.admin, _valid=False, _exception="NOT_MINTER")
    add_rights(env, art, buyer, sender=buyer, _valid=False, _exception="NOT_MINTER")
    add_rights(env, art, buyer, paid=RIGHTS_FLOOR - 1, _valid=False,
               _exception="BELOW_COMMERCIAL_FLOOR")
    add_rights(env, art, buyer, paid=0, _valid=False, _exception="BELOW_COMMERCIAL_FLOOR")
    add_rights(env, 99, buyer, _valid=False, _exception="UNKNOWN_TOKEN")
    sc.verify(~marked(env, art))
    add_rights(env, art, buyer)
    sc.verify(c.data.editions[art].commercial)
    sc.verify(marked(env, art))
    sc.verify(c.balance == sp.mutez(0))
    sc.verify(env.payout.balance == sp.mutez(0))

    sc.h2("Set once: never again, and nothing clears it")
    add_rights(env, art, buyer, _valid=False, _exception="HAS_COMMERCIAL_RIGHTS")

    sc.h2("An artwork registered without a commercial floor never has them")
    mint(env, plain, 1, buyer)
    add_rights(env, plain, buyer, _valid=False, _exception="NO_COMMERCIAL_RIGHTS")
    mint(env, edition, 2, buyer)
    add_rights(env, edition, buyer, _valid=False, _exception="NO_COMMERCIAL_RIGHTS")

    sc.h2("The mark belongs to the token: it follows the copy, and burning keeps it")
    c.transfer([sp.record(from_=buyer.address, txs=[
        sp.record(to_=bob.address, token_id=art, amount=1)])], _sender=buyer, _now=at(NOW))
    sc.verify(balance(c, bob, art) == 1)
    sc.verify(balance(c, buyer, art) == 0)
    sc.verify(marked(env, art))
    c.burn([sp.record(from_=bob.address, token_id=art, amount=1)], _sender=bob, _now=at(NOW))
    sc.verify(c.data.editions[art].commercial)
    sc.verify(~marked(env, plain))
    sc.verify(~marked(env, 99))


@sp.add_test()
def test_rollback_after_mint():
    sc = sp.test_scenario("commercial_rollback", [bundle])
    env = deploy(sc)
    c, buyer, alice = env.collection, env.acc.buyer, env.acc.alice
    b = bundle.MintThenRights(c.address)
    sc += b
    for wallet in (env.acc.admin, env.acc.guardian):
        c.propose_minter(b.address, _sender=wallet, _now=at(NOW))
    art = register(env, cap=1, floor=FLOOR, commercial_floor=RIGHTS_FLOOR)

    def go(holder, **kwargs):
        b.go(token_id=art, to_=buyer.address, holder=holder.address, price=sp.mutez(FLOOR),
             rights=sp.mutez(RIGHTS_FLOOR), _sender=buyer,
             _amount=sp.mutez(FLOOR + RIGHTS_FLOOR), _now=at(NOW), **kwargs)

    sc.h2("A mark refused after the copy was minted undoes the whole operation, its payment too")
    go(alice, _valid=False, _exception="NOT_HOLDER")
    sc.verify(c.data.editions[art].minted == 0)
    sc.verify(balance(c, buyer, art) == 0)
    go(buyer)
    sc.verify(c.data.editions[art].commercial)


# The copy (its floor), the rights (their floor), then the plain 1/1 and the
# edition's two copies (one mutez each): all reached the payout wallet. In the
# rollback scenario, only the purchase that went through is counted.
payout = WALLETS["payout"]
for scenario, amounts in [("commercial_collection", [FLOOR, RIGHTS_FLOOR, 1, 2]),
                          ("commercial_rollback", [FLOOR, RIGHTS_FLOOR])]:
    expected = [(amount, payout) for amount in amounts]
    assert payments(scenario) == expected, (scenario, payments(scenario))
print("payments ok")
