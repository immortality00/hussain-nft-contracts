"""FA2 behaviour from the library, and tez refused on every entry point.

Only buy and mint (the price, passed straight on) and the payout contract's
default take tez; every other entry point of the three contracts refuses it.
"""

import smartpy as sp
from smartpy.templates import fa2_lib

from deploy.metadata import utf8
from tests.setup import DELAY, T0, at, balance, deploy, ipfs, mint, register

NOW = T0 + DELAY
TEZ = sp.mutez(1)


@sp.module
def receiver():
    import t

    class Receiver(sp.Contract):
        """A contract that takes balance_of answers (and can hold tokens)."""

        def __init__(self):
            self.data.last = sp.cast([], sp.list[t.balance_of_response])

        @sp.entrypoint
        def receive(self, answers):
            sp.cast(answers, sp.list[t.balance_of_response])
            self.data.last = answers


t = fa2_lib.t


def minted_env(sc):
    env = deploy(sc)
    art = register(env, cap=10)
    mint(env, art, 5, env.acc.alice)
    return env, art


@sp.add_test()
def test_transfers_and_operators():
    sc = sp.test_scenario("fa2_transfers")
    env, art = minted_env(sc)
    c, alice, bob = env.collection, env.acc.alice, env.acc.bob

    def tx(sender, amount, **kwargs):
        c.transfer([sp.record(from_=alice.address, txs=[
            sp.record(to_=bob.address, token_id=art, amount=amount)])],
            _sender=sender, _now=at(NOW), **kwargs)

    tx(alice, 2)
    tx(bob, 1, _valid=False, _exception="FA2_NOT_OPERATOR")
    tx(alice, 4, _valid=False, _exception="FA2_INSUFFICIENT_BALANCE")
    sc.verify(balance(c, bob, art) == 2)

    op = sp.record(owner=alice.address, operator=bob.address, token_id=art)
    c.update_operators([sp.variant.add_operator(op)], _sender=bob, _now=at(NOW),
                       _valid=False, _exception="FA2_NOT_OWNER")
    c.update_operators([sp.variant.add_operator(op)], _sender=alice, _now=at(NOW))
    tx(bob, 1)
    c.update_operators([sp.variant.remove_operator(op)], _sender=alice, _now=at(NOW))
    tx(bob, 1, _valid=False, _exception="FA2_NOT_OPERATOR")
    c.transfer([sp.record(from_=alice.address, txs=[
        sp.record(to_=bob.address, token_id=77, amount=1)])],
        _sender=alice, _now=at(NOW), _valid=False, _exception="FA2_TOKEN_UNDEFINED")

    sc.h2("Only a copy's owner burns it, not even an operator allowed to move it")
    c.burn([sp.record(from_=alice.address, token_id=art, amount=1)], _sender=bob, _now=at(NOW),
           _valid=False, _exception="FA2_NOT_OWNER")
    c.update_operators([sp.variant.add_operator(op)], _sender=alice, _now=at(NOW))
    c.burn([sp.record(from_=alice.address, token_id=art, amount=1)], _sender=bob, _now=at(NOW),
           _valid=False, _exception="FA2_NOT_OWNER")
    c.update_operators([sp.variant.remove_operator(op)], _sender=alice, _now=at(NOW))
    c.burn([sp.record(from_=alice.address, token_id=art, amount=1)], _sender=alice, _now=at(NOW))
    c.burn([sp.record(from_=alice.address, token_id=art, amount=9)], _sender=alice, _now=at(NOW),
           _valid=False, _exception="FA2_INSUFFICIENT_BALANCE")
    sc.verify(balance(c, alice, art) == 1)
    sc.verify(c.data.supply[art] == 4)


@sp.add_test()
def test_balance_of_and_contract_holder():
    sc = sp.test_scenario("fa2_balance_of", [t, receiver])
    env, art = minted_env(sc)
    r = receiver.Receiver()
    sc += r
    cb = sp.contract(sp.list[t.balance_of_response], r.address, entrypoint="receive").unwrap_some()
    env.collection.balance_of(
        sp.record(requests=[sp.record(owner=env.acc.alice.address, token_id=art)], callback=cb),
        _sender=env.acc.bob, _now=at(NOW))
    sc.verify(sp.len(r.data.last) == 1)

    sc.h2("A contract can be a token holder")
    env.collection.transfer([sp.record(from_=env.acc.alice.address, txs=[
        sp.record(to_=r.address, token_id=art, amount=1)])], _sender=env.acc.alice, _now=at(NOW))
    sc.verify(env.collection.data.ledger[(r.address, art)] == 1)


@sp.add_test()
def test_tez_refused_everywhere():
    sc = sp.test_scenario("fa2_no_tez", [t, receiver])
    env, art = minted_env(sc)
    c, s, p = env.collection, env.sale, env.payout
    alice, admin, guardian = env.acc.alice, env.acc.admin, env.acc.guardian
    no = dict(_amount=TEZ, _now=at(NOW), _valid=False, _exception="NO_TEZ")

    c.transfer([], _sender=alice, **no)
    c.update_operators([], _sender=alice, **no)
    c.burn([], _sender=alice, **no)
    r = receiver.Receiver()
    sc += r
    cb = sp.contract(sp.list[t.balance_of_response], r.address, entrypoint="receive").unwrap_some()
    c.balance_of(sp.record(requests=[], callback=cb), _sender=alice, **no)
    c.register(metadata_uri=ipfs(50), cap=sp.Some(1), mint_end=None, floor=sp.mutez(1),
               _sender=admin, **no)
    c.retire(art, _sender=admin, **no)
    c.add_history(token_id=art, text=utf8("x"), uri=None, _sender=admin, **no)
    c.propose_minter(alice.address, _sender=admin, **no)
    c.cancel_minter(alice.address, _sender=admin, **no)
    c.confirm_minter(alice.address, _sender=admin, **no)
    c.remove_minter(s.address, _sender=admin, **no)
    s.set_sale(token_id=art, price=sp.mutez(1), start=at(NOW), end=None, max_per_buy=1,
               _sender=admin, **no)
    s.remove_sale(art, _sender=admin, **no)
    s.set_paused(True, _sender=admin, **no)
    s.set_sale_paused(token_id=art, paused=True, _sender=admin, **no)
    p.propose_payout(alice.address, _sender=admin, **no)
    p.cancel_payout(_sender=guardian, **no)
    p.accept_payout(alice.public_key, _sender=alice, **no)
    for contract in (c, s, p):
        contract.propose_admin(alice.address, _sender=admin, **no)
        contract.cancel_admin(_sender=guardian, **no)
        contract.accept_admin(_sender=alice, **no)
        contract.propose_guardian(alice.address, _sender=admin, **no)
        contract.cancel_guardian(_sender=guardian, **no)
        contract.accept_guardian(_sender=alice, **no)
    sc.verify(c.balance == sp.mutez(0))
    sc.verify(s.balance == sp.mutez(0))
    sc.verify(p.balance == sp.mutez(0))
