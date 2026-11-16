"""Selling commercial rights: with a 1/1 in one purchase, or later to whoever
holds it, at exactly the price set then. Removing the price, or pausing all
sales, stops both at once."""

import smartpy as sp

from tests.setup import DELAY, T0, WALLETS, at, balance, deploy, list_for_sale, payments, register

NOW = T0 + DELAY
PRICE = 2_000_000
RIGHTS_FLOOR = 4_000_000
RIGHTS = 5_000_000


def set_price(env, token_id, price=RIGHTS, sender=None, **kwargs):
    env.sale.set_commercial_price(token_id=token_id, price=sp.mutez(price),
                                  _sender=sender or env.acc.admin, _now=at(NOW), **kwargs)


def buy(env, token_id, paid, commercial=True, quantity=1, recipient=None, **kwargs):
    buyer = env.acc.buyer
    env.sale.buy(token_id=token_id, quantity=quantity, recipient=(recipient or buyer).address,
                 commercial=commercial, _sender=buyer, _amount=sp.mutez(paid), _now=at(NOW),
                 **kwargs)


def buy_rights(env, token_id, paid=RIGHTS, holder=None, **kwargs):
    env.sale.buy_commercial_rights(token_id, _sender=holder or env.acc.buyer,
                                   _amount=sp.mutez(paid), _now=at(NOW), **kwargs)


def one_of_one(env):
    art = register(env, cap=1, floor=PRICE, commercial_floor=RIGHTS_FLOOR)
    list_for_sale(env, art, price=PRICE, max_per_buy=2)
    return art


def no_tez_held(sc, env):
    for contract in (env.collection, env.sale, env.payout):
        sc.verify(contract.balance == sp.mutez(0))


@sp.add_test()
def test_commercial_price():
    sc = sp.test_scenario("commercial_price")
    env = deploy(sc)
    s, admin, guardian = env.sale, env.acc.admin, env.acc.guardian
    art = one_of_one(env)
    edition = register(env, cap=5)
    mistake = register(env, cap=1, commercial_floor=RIGHTS_FLOOR)
    env.collection.retire(mistake, _sender=admin, _now=at(NOW))

    sc.h2("Admin only, on a 1/1 that offers them, never below their floor")
    set_price(env, art, sender=env.acc.stranger, _valid=False, _exception="NOT_ADMIN")
    set_price(env, art, sender=guardian, _valid=False, _exception="NOT_ADMIN")
    set_price(env, art, _amount=sp.mutez(1), _valid=False, _exception="NO_TEZ")
    set_price(env, 99, _valid=False, _exception="UNKNOWN_TOKEN")
    set_price(env, mistake, _valid=False, _exception="RETIRED")
    set_price(env, edition, _valid=False, _exception="NO_COMMERCIAL_RIGHTS")
    set_price(env, art, price=RIGHTS_FLOOR - 1, _valid=False, _exception="BELOW_COMMERCIAL_FLOOR")
    set_price(env, art, price=0, _valid=False, _exception="BELOW_COMMERCIAL_FLOOR")
    set_price(env, art, price=RIGHTS_FLOOR)
    set_price(env, art)
    sc.verify(s.data.commercial_prices[art] == sp.mutez(RIGHTS))

    sc.h2("Removed and set again, like a listing")
    s.remove_commercial_price(art, _sender=guardian, _now=at(NOW), _valid=False,
                              _exception="NOT_ADMIN")
    s.remove_commercial_price(art, _sender=admin, _now=at(NOW), _amount=sp.mutez(1),
                              _valid=False, _exception="NO_TEZ")
    s.remove_commercial_price(art, _sender=admin, _now=at(NOW))
    sc.verify(~s.data.commercial_prices.contains(art))
    s.remove_commercial_price(art, _sender=admin, _now=at(NOW), _valid=False,
                              _exception="NO_COMMERCIAL_PRICE")
    set_price(env, art)
    sc.verify(s.data.commercial_prices[art] == sp.mutez(RIGHTS))


@sp.add_test()
def test_buy_with_rights():
    sc = sp.test_scenario("commercial_buy")
    env = deploy(sc)
    c, s, alice = env.collection, env.sale, env.acc.alice
    art = one_of_one(env)
    buy(env, art, PRICE + RIGHTS, _valid=False, _exception="NO_COMMERCIAL_PRICE")
    set_price(env, art)

    sc.h2("Exactly the copy's price plus the rights' price, for one copy")
    for paid in (PRICE, RIGHTS, PRICE + RIGHTS - 1, PRICE + RIGHTS + 1, 0):
        buy(env, art, paid, _valid=False, _exception="WRONG_AMOUNT")
    buy(env, art, 2 * PRICE + RIGHTS, quantity=2, _valid=False, _exception="BAD_QUANTITY")

    sc.h2("Pausing the listing, or all sales, stops it")
    s.set_sale_paused(token_id=art, paused=True, _sender=env.acc.admin, _now=at(NOW))
    buy(env, art, PRICE + RIGHTS, _valid=False, _exception="SALE_PAUSED")
    s.set_sale_paused(token_id=art, paused=False, _sender=env.acc.admin, _now=at(NOW))
    s.set_paused(True, _sender=env.acc.guardian, _now=at(NOW))
    buy(env, art, PRICE + RIGHTS, _valid=False, _exception="SALES_PAUSED")
    s.set_paused(False, _sender=env.acc.admin, _now=at(NOW))

    sc.h2("One purchase: the copy and the mark, to the recipient")
    buy(env, art, PRICE + RIGHTS, recipient=alice)
    sc.verify(balance(c, alice, art) == 1)
    sc.verify(c.data.editions[art].commercial)
    sc.verify(~s.data.commercial_prices.contains(art))
    no_tez_held(sc, env)
    set_price(env, art, _valid=False, _exception="HAS_COMMERCIAL_RIGHTS")

    sc.h2("An edition never sells them; a copy without them still sells")
    edition = register(env, cap=5)
    list_for_sale(env, edition, price=PRICE)
    buy(env, edition, PRICE + RIGHTS, _valid=False, _exception="NO_COMMERCIAL_PRICE")
    buy(env, edition, PRICE, commercial=False)


@sp.add_test()
def test_buy_rights_later():
    sc = sp.test_scenario("commercial_later")
    env = deploy(sc)
    c, s, buyer, bob = env.collection, env.sale, env.acc.buyer, env.acc.bob
    art = one_of_one(env)
    buy(env, art, PRICE, commercial=False)
    buy_rights(env, art, _valid=False, _exception="NO_COMMERCIAL_PRICE")
    set_price(env, art)

    sc.h2("Only the holder, at exactly the price set, while sales are on")
    buy_rights(env, art, holder=bob, _valid=False, _exception="NOT_HOLDER")
    for paid in (RIGHTS - 1, RIGHTS + 1, 0):
        buy_rights(env, art, paid=paid, _valid=False, _exception="WRONG_AMOUNT")
    s.set_paused(True, _sender=env.acc.guardian, _now=at(NOW))
    buy_rights(env, art, _valid=False, _exception="SALES_PAUSED")
    s.set_paused(False, _sender=env.acc.admin, _now=at(NOW))

    sc.h2("A later owner buys them at the price current then, listing or not")
    s.remove_sale(art, _sender=env.acc.admin, _now=at(NOW))
    c.transfer([sp.record(from_=buyer.address, txs=[
        sp.record(to_=bob.address, token_id=art, amount=1)])], _sender=buyer, _now=at(NOW))
    set_price(env, art, price=2 * RIGHTS)
    buy_rights(env, art, paid=2 * RIGHTS, _valid=False, _exception="NOT_HOLDER")
    buy_rights(env, art, holder=bob, _valid=False, _exception="WRONG_AMOUNT")
    buy_rights(env, art, paid=2 * RIGHTS, holder=bob)
    sc.verify(c.data.editions[art].commercial)
    sc.verify(~s.data.commercial_prices.contains(art))
    buy_rights(env, art, paid=2 * RIGHTS, holder=bob, _valid=False,
               _exception="NO_COMMERCIAL_PRICE")

    sc.h2("Removing the price stops it at once (an artwork reported stolen)")
    other = one_of_one(env)
    buy(env, other, PRICE, commercial=False)
    set_price(env, other)
    s.remove_commercial_price(other, _sender=env.acc.admin, _now=at(NOW))
    buy_rights(env, other, _valid=False, _exception="NO_COMMERCIAL_PRICE")
    no_tez_held(sc, env)


# Every successful purchase reached the payout wallet in full: the copy and
# its rights as two payments, in that order.
for scenario, amounts in [("commercial_buy", [PRICE, RIGHTS, PRICE]),
                          ("commercial_later", [PRICE, 2 * RIGHTS, PRICE])]:
    expected = [(amount, WALLETS["payout"]) for amount in amounts]
    assert payments(scenario) == expected, (scenario, payments(scenario))
print("payments ok")
