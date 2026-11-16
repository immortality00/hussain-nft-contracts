"""OpenTezos flaw 1: rights follow the direct caller (sender), never the source.

If the admin is tricked into calling a malicious contract, that contract
must not be able to act as the admin (or the guardian) on any contract. If
a copy's holder is tricked into it, the contract can't buy the commercial
rights in the holder's place.
"""

import smartpy as sp

from tests.setup import DELAY, T0, at, deploy, list_for_sale, register


@sp.module
def attacker():
    class Proxy(sp.Contract):
        """Forwards a call to an admin entry point, as itself."""

        def __init__(self, collection, sale):
            self.data.collection = sp.cast(collection, sp.address)
            self.data.sale = sp.cast(sale, sp.address)

        @sp.entrypoint
        def take_collection(self):
            target = sp.contract(sp.address, self.data.collection, entrypoint="propose_admin")
            sp.transfer(sp.self_address, sp.mutez(0), target.unwrap_some())

        @sp.entrypoint
        def add_self_as_minter(self):
            target = sp.contract(sp.address, self.data.collection, entrypoint="propose_minter")
            sp.transfer(sp.self_address, sp.mutez(0), target.unwrap_some())

        @sp.entrypoint
        def pause_sales(self):
            target = sp.contract(sp.bool, self.data.sale, entrypoint="set_paused")
            sp.transfer(True, sp.mutez(0), target.unwrap_some())

        @sp.entrypoint
        def buy_rights_for(self, token_id):
            sp.cast(token_id, sp.nat)
            target = sp.contract(sp.nat, self.data.sale, entrypoint="buy_commercial_rights")
            sp.transfer(token_id, sp.amount, target.unwrap_some())


@sp.add_test()
def test_sender_not_source():
    sc = sp.test_scenario("flaw_sender", [attacker])
    env = deploy(sc)
    proxy = attacker.Proxy(env.collection.address, env.sale.address)
    sc += proxy
    now = at(T0 + DELAY)

    for call in (proxy.take_collection, proxy.add_self_as_minter, proxy.pause_sales):
        call(_sender=env.acc.admin, _now=now, _valid=False, _exception="NOT_ADMIN_OR_GUARDIAN")
    sc.verify(env.collection.data.admin_votes.by_admin == None)
    sc.verify(~env.collection.data.minter_votes.contains(proxy.address))
    sc.verify(~env.sale.data.paused)

    sc.h2("The holder, tricked into calling it: the rights are never added for the proxy")
    art = register(env, cap=1, commercial_floor=2)
    list_for_sale(env, art, price=1)
    buyer = env.acc.buyer
    env.sale.buy(token_id=art, quantity=1, recipient=buyer.address, commercial=False,
                 _sender=buyer, _amount=sp.mutez(1), _now=now)
    env.sale.set_commercial_price(token_id=art, price=sp.mutez(2), _sender=env.acc.admin, _now=now)
    proxy.buy_rights_for(art, _sender=buyer, _amount=sp.mutez(2), _now=now,
                         _valid=False, _exception="NOT_HOLDER")
    sc.verify(~env.collection.data.editions[art].commercial)
