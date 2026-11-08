"""Buying: exact price, sale window, quantity limit, pauses, and payment forwarded."""

import smartpy as sp

from tests.setup import DAY, DELAY, T0, WALLETS, at, balance, deploy, list_for_sale, payments, register

NOW = T0 + DELAY
PRICE = 2_500_000


def buy(env, token_id, quantity, paid, now=NOW, buyer=None, recipient=None, **kwargs):
    buyer = buyer or env.acc.buyer
    env.sale.buy(
        token_id=token_id,
        quantity=quantity,
        recipient=(recipient or buyer).address,
        _sender=buyer,
        _amount=sp.mutez(paid),
        _now=at(now),
        **kwargs,
    )


@sp.add_test()
def test_buy():
    sc = sp.test_scenario("sale_buy")
    env = deploy(sc)
    art = register(env, cap=25)
    list_for_sale(env, art, price=PRICE, max_per_buy=3)

    sc.h2("Exact amount only")
    buy(env, art, 2, 2 * PRICE)
    buy(env, art, 2, 2 * PRICE - 1, _valid=False, _exception="WRONG_AMOUNT")
    buy(env, art, 2, 2 * PRICE + 1, _valid=False, _exception="WRONG_AMOUNT")
    buy(env, art, 1, 0, _valid=False, _exception="WRONG_AMOUNT")
    sc.verify(balance(env.collection, env.acc.buyer, art) == 2)
    sc.verify(env.sale.balance == sp.mutez(0))

    sc.h2("Quantity limit per purchase")
    buy(env, art, 0, 0, _valid=False, _exception="BAD_QUANTITY")
    buy(env, art, 4, 4 * PRICE, _valid=False, _exception="BAD_QUANTITY")
    buy(env, art, 3, 3 * PRICE)

    sc.h2("A gift: someone else receives the copy, the buyer's choice")
    buy(env, art, 1, PRICE, recipient=env.acc.alice)
    sc.verify(balance(env.collection, env.acc.alice, art) == 1)
    sc.verify(balance(env.collection, env.acc.buyer, art) == 5)

    sc.h2("The edition cap is the collection contract's, not the sale's")
    for _ in range(6):
        buy(env, art, 3, 3 * PRICE)
    buy(env, art, 2, 2 * PRICE, _valid=False, _exception="EDITION_FULL")
    buy(env, art, 1, PRICE)
    buy(env, art, 1, PRICE, _valid=False, _exception="EDITION_FULL")
    sc.verify(env.collection.data.editions[art].minted == 25)
    sc.verify(env.sale.balance == sp.mutez(0))
    sc.verify(env.payout.balance == sp.mutez(0))
    sc.verify(env.collection.balance == sp.mutez(0))
    buy(env, 99, 1, PRICE, _valid=False, _exception="NO_SALE")


@sp.add_test()
def test_recipient():
    sc = sp.test_scenario("sale_recipient")
    env = deploy(sc)
    art = register(env, cap=5)
    list_for_sale(env, art, price=PRICE)
    for contract in (env.collection, env.sale, env.payout):
        env.sale.buy(token_id=art, quantity=1, recipient=contract.address, _sender=env.acc.buyer,
                     _amount=sp.mutez(PRICE), _now=at(NOW), _valid=False,
                     _exception="BAD_RECIPIENT")
    sc.verify(env.collection.data.editions[art].minted == 0)


@sp.add_test()
def test_window_and_pauses():
    sc = sp.test_scenario("sale_window")
    env = deploy(sc)
    art = register(env, cap=100)
    start, end = NOW + DAY, NOW + 3 * DAY
    list_for_sale(env, art, price=PRICE, start=start, end=end)

    buy(env, art, 1, PRICE, now=start - 1, _valid=False, _exception="NOT_STARTED")
    buy(env, art, 1, PRICE, now=start)
    buy(env, art, 1, PRICE, now=end - 1)
    buy(env, art, 1, PRICE, now=end, _valid=False, _exception="SALE_ENDED")

    sc.h2("Pausing one artwork, then everything")
    list_for_sale(env, art, price=PRICE)
    env.sale.set_sale_paused(token_id=art, paused=True, _sender=env.acc.admin, _now=at(NOW))
    buy(env, art, 1, PRICE, _valid=False, _exception="SALE_PAUSED")
    list_for_sale(env, art, price=PRICE)
    buy(env, art, 1, PRICE, _valid=False, _exception="SALE_PAUSED")
    env.sale.set_sale_paused(token_id=art, paused=False, _sender=env.acc.admin, _now=at(NOW))
    buy(env, art, 1, PRICE)
    env.sale.set_paused(True, _sender=env.acc.admin, _now=at(NOW))
    buy(env, art, 1, PRICE, _valid=False, _exception="SALES_PAUSED")
    env.sale.set_paused(False, _sender=env.acc.admin, _now=at(NOW))
    buy(env, art, 1, PRICE)

    sc.h2("A price change while a buyer signs makes the purchase fail, never overcharge")
    list_for_sale(env, art, price=PRICE * 2)
    buy(env, art, 1, PRICE, _valid=False, _exception="WRONG_AMOUNT")

    sc.h2("Removing a listing stops sales at once; relisting starts them again")
    env.sale.remove_sale(art, _sender=env.acc.admin, _now=at(NOW))
    buy(env, art, 1, PRICE * 2, _valid=False, _exception="NO_SALE")
    list_for_sale(env, art, price=PRICE)
    buy(env, art, 1, PRICE)


@sp.add_test()
def test_open_edition_sale():
    sc = sp.test_scenario("sale_open_edition")
    env = deploy(sc)
    end = NOW + 2 * DAY
    art = register(env, cap=None, mint_end=end)
    list_for_sale(env, art, price=PRICE, max_per_buy=10)
    buy(env, art, 10, 10 * PRICE, now=end - 1)
    buy(env, art, 1, PRICE, now=end, _valid=False, _exception="MINTING_ENDED")


# Every successful purchase in test_buy reached the payout wallet, through
# the payout contract, in full: 2, 3, 1, then 3 six times, then 1 copy.
quantities = [2, 3, 1, 3, 3, 3, 3, 3, 3, 1]
expected = [(q * PRICE, WALLETS["payout"]) for q in quantities]
assert payments("sale_buy") == expected, payments("sale_buy")
print("payments ok")
