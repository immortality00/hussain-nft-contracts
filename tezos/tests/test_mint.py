"""The collection contract enforces every edition itself, whoever the minter:
the cap, the end time, and the floor price with the payment route."""

import smartpy as sp

from tests.setup import DAY, DELAY, T0, WALLETS, at, balance, deploy, mint, payments, register

NOW = T0 + DELAY


@sp.add_test()
def test_caps():
    sc = sp.test_scenario("mint_caps")
    env = deploy(sc)
    buyer = env.acc.buyer
    one = register(env, cap=1)
    limited = register(env, cap=25)

    sc.h2("A 1/1 mints once")
    mint(env, one, 1, buyer)
    mint(env, one, 1, buyer, _valid=False, _exception="EDITION_FULL")

    sc.h2("A limited edition mints exactly up to its cap")
    mint(env, limited, 24, buyer)
    mint(env, limited, 2, buyer, _valid=False, _exception="EDITION_FULL")
    mint(env, limited, 1, buyer)
    mint(env, limited, 1, buyer, _valid=False, _exception="EDITION_FULL")
    sc.verify(env.collection.data.editions[limited].minted == 25)
    sc.verify(env.collection.data.supply[limited] == 25)
    sc.verify(balance(env.collection, buyer, limited) == 25)

    sc.h2("Burning a copy never reopens the edition")
    env.collection.burn(
        [sp.record(from_=buyer.address, token_id=limited, amount=3)],
        _sender=buyer, _now=at(NOW),
    )
    sc.verify(env.collection.data.supply[limited] == 22)
    sc.verify(env.collection.data.editions[limited].minted == 25)
    mint(env, limited, 1, buyer, _valid=False, _exception="EDITION_FULL")

    sc.h2("A batch can't pass the cap by naming the same artwork twice")
    three = register(env, cap=3)
    alice = env.acc.alice
    over = [sp.record(to_=buyer.address, token_id=three, amount=2),
            sp.record(to_=alice.address, token_id=three, amount=2)]
    env.collection.mint(over, _sender=env.acc.minter, _amount=sp.mutez(4), _now=at(NOW),
                        _valid=False, _exception="EDITION_FULL")
    sc.verify(env.collection.data.editions[three].minted == 0)
    exact = [sp.record(to_=buyer.address, token_id=three, amount=2),
             sp.record(to_=alice.address, token_id=three, amount=1)]
    env.collection.mint(exact, _sender=env.acc.minter, _amount=sp.mutez(3), _now=at(NOW))
    sc.verify(env.collection.data.editions[three].minted == 3)
    sc.verify(env.collection.data.supply[three] == 3)
    sc.verify(balance(env.collection, buyer, three) == 2)
    sc.verify(balance(env.collection, alice, three) == 1)
    mint(env, three, 1, buyer, _valid=False, _exception="EDITION_FULL")


@sp.add_test()
def test_open_edition_end():
    sc = sp.test_scenario("mint_open_edition")
    env = deploy(sc)
    end = NOW + 7 * DAY
    open_ed = register(env, cap=None, mint_end=end)

    mint(env, open_ed, 1000, env.acc.buyer, now=end - 1)
    mint(env, open_ed, 1, env.acc.buyer, now=end, _valid=False, _exception="MINTING_ENDED")
    mint(env, open_ed, 1, env.acc.buyer, now=end + 1, _valid=False, _exception="MINTING_ENDED")
    sc.verify(env.collection.data.editions[open_ed].minted == 1000)

    sc.h2("A limited edition with an end stops at whichever comes first")
    capped = register(env, cap=10, mint_end=end)
    mint(env, capped, 3, env.acc.buyer, now=end - 1)
    mint(env, capped, 1, env.acc.buyer, now=end, _valid=False, _exception="MINTING_ENDED")


FLOOR = 1_000_000


@sp.add_test()
def test_floor_on_every_mint():
    sc = sp.test_scenario("mint_floor")
    env = deploy(sc)
    c, buyer = env.collection, env.acc.buyer
    art = register(env, cap=10, floor=FLOOR)
    other = register(env, cap=10, floor=3 * FLOOR)

    sc.h2("Any minter pays at least the floor of every copy, or nothing mints")
    mint(env, art, 2, buyer, paid=2 * FLOOR - 1, _valid=False, _exception="BELOW_FLOOR")
    mint(env, art, 2, buyer, paid=0, _valid=False, _exception="BELOW_FLOOR")
    mint(env, art, 2, buyer, paid=2 * FLOOR)
    mint(env, art, 1, buyer, paid=5 * FLOOR)
    sc.verify(c.data.editions[art].minted == 3)

    sc.h2("A batch pays the floors of all its copies together")
    batch = [sp.record(to_=buyer.address, token_id=art, amount=1),
             sp.record(to_=buyer.address, token_id=other, amount=2)]
    c.mint(batch, _sender=env.acc.minter, _amount=sp.mutez(7 * FLOOR - 1), _now=at(NOW),
           _valid=False, _exception="BELOW_FLOOR")
    c.mint(batch, _sender=env.acc.minter, _amount=sp.mutez(7 * FLOOR), _now=at(NOW))
    sc.verify(c.balance == sp.mutez(0))
    sc.verify(env.payout.balance == sp.mutez(0))

    sc.h2("No copy can be minted to the collection or the payout contract")
    for contract in (c, env.payout):
        c.mint([sp.record(to_=contract.address, token_id=art, amount=1)],
               _sender=env.acc.minter, _amount=sp.mutez(FLOOR), _now=at(NOW),
               _valid=False, _exception="BAD_RECIPIENT")


@sp.add_test()
def test_who_can_mint():
    sc = sp.test_scenario("mint_callers")
    env = deploy(sc)
    art = register(env, cap=5)

    mint(env, art, 1, env.acc.buyer, sender=env.acc.admin, _valid=False, _exception="NOT_MINTER")
    mint(env, art, 1, env.acc.buyer, sender=env.acc.stranger, _valid=False, _exception="NOT_MINTER")
    mint(env, art, 0, env.acc.buyer, _valid=False, _exception="ZERO_AMOUNT")
    mint(env, 99, 1, env.acc.buyer, _valid=False, _exception="UNKNOWN_TOKEN")

    sc.h2("A removed minter can no longer mint")
    env.collection.remove_minter(env.acc.minter.address, _sender=env.acc.admin, _now=at(NOW))
    mint(env, art, 1, env.acc.buyer, _valid=False, _exception="NOT_MINTER")


@sp.add_test()
def test_minters_not_yet_confirmed():
    sc = sp.test_scenario("mint_before_confirm")
    env = deploy(sc, confirm_minter=False)
    art = register(env, cap=5, now=T0)
    env.collection.propose_minter(env.acc.minter.address, _sender=env.acc.admin, _now=at(T0))
    mint(env, art, 1, env.acc.buyer, now=T0 + 1, _valid=False, _exception="NOT_MINTER")


# Every successful mint in test_floor_on_every_mint reached the payout wallet,
# through the collection and the payout contract, overpayment included.
expected = [(2 * FLOOR, WALLETS["payout"]), (5 * FLOOR, WALLETS["payout"]),
            (7 * FLOOR, WALLETS["payout"])]
assert payments("mint_floor") == expected, payments("mint_floor")
print("payments ok")
