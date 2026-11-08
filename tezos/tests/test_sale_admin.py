"""Setting up sales: who can, the floor price, removing listings, pausing."""

import smartpy as sp

from tests.setup import DELAY, T0, at, deploy, list_for_sale, register

NOW = T0 + DELAY
FLOOR = 3_000_000


def set_sale(env, token_id, price=FLOOR, start=NOW, end=None, max_per_buy=1, sender=None,
             **kwargs):
    env.sale.set_sale(
        token_id=token_id, price=sp.mutez(price), start=at(start),
        end=None if end is None else sp.Some(at(end)), max_per_buy=max_per_buy,
        _sender=sender or env.acc.admin, _now=at(NOW), **kwargs,
    )


@sp.add_test()
def test_set_sale():
    sc = sp.test_scenario("sale_admin")
    env = deploy(sc)
    s, admin, guardian, stranger = env.sale, env.acc.admin, env.acc.guardian, env.acc.stranger
    art = register(env, cap=5, floor=FLOOR)
    mistake = register(env, cap=5)
    env.collection.retire(mistake, _sender=admin, _now=at(NOW))

    set_sale(env, art, sender=stranger, _valid=False, _exception="NOT_ADMIN")
    set_sale(env, art, sender=guardian, _valid=False, _exception="NOT_ADMIN")
    set_sale(env, art, _amount=sp.mutez(1), _valid=False, _exception="NO_TEZ")
    set_sale(env, art, max_per_buy=0, _valid=False, _exception="MAX_ZERO")
    set_sale(env, art, end=NOW, _valid=False, _exception="END_BEFORE_START")
    set_sale(env, 99, _valid=False, _exception="UNKNOWN_TOKEN")
    set_sale(env, mistake, _valid=False, _exception="RETIRED")

    sc.h2("Never below the artwork's floor; at or above it, at once")
    set_sale(env, art, price=FLOOR - 1, _valid=False, _exception="BELOW_FLOOR")
    set_sale(env, art, price=0, _valid=False, _exception="BELOW_FLOOR")
    set_sale(env, art, price=FLOOR, end=NOW + 10, max_per_buy=2)
    listing = s.data.sales[art]
    sc.verify(listing.price == sp.mutez(FLOOR))
    sc.verify(listing.end == sp.Some(at(NOW + 10)))
    sc.verify(listing.max_per_buy == 2)
    sc.verify(~listing.paused)
    set_sale(env, art, price=FLOOR * 4)
    sc.verify(s.data.sales[art].price == sp.mutez(FLOOR * 4))

    sc.h2("Pausing and removing one listing are admin only")
    s.set_sale_paused(token_id=art, paused=True, _sender=guardian, _now=at(NOW),
                      _valid=False, _exception="NOT_ADMIN")
    s.set_sale_paused(token_id=99, paused=True, _sender=admin, _now=at(NOW),
                      _valid=False, _exception="NO_SALE")
    s.remove_sale(art, _sender=guardian, _now=at(NOW), _valid=False, _exception="NOT_ADMIN")
    s.remove_sale(99, _sender=admin, _now=at(NOW), _valid=False, _exception="NO_SALE")
    s.remove_sale(art, _sender=admin, _now=at(NOW), _amount=sp.mutez(1), _valid=False, _exception="NO_TEZ")

    sc.h2("Updating a listing keeps its pause; removing it and listing again starts fresh")
    s.set_sale_paused(token_id=art, paused=True, _sender=admin, _now=at(NOW))
    list_for_sale(env, art, price=FLOOR * 2)
    sc.verify(s.data.sales[art].paused)
    s.remove_sale(art, _sender=admin, _now=at(NOW))
    sc.verify(~s.data.sales.contains(art))
    s.remove_sale(art, _sender=admin, _now=at(NOW), _valid=False, _exception="NO_SALE")
    list_for_sale(env, art, price=FLOOR)
    sc.verify(~s.data.sales[art].paused)

    sc.h2("Either wallet stops all sales; only the admin starts them again")
    s.set_paused(True, _sender=stranger, _now=at(NOW), _valid=False, _exception="NOT_ADMIN_OR_GUARDIAN")
    s.set_paused(True, _sender=guardian, _now=at(NOW))
    sc.verify(s.data.paused)
    s.set_paused(False, _sender=guardian, _now=at(NOW), _valid=False, _exception="NOT_ADMIN")
    s.set_paused(False, _sender=admin, _now=at(NOW))
    sc.verify(~s.data.paused)
    s.set_paused(True, _sender=admin, _now=at(NOW))
    sc.verify(s.data.paused)
