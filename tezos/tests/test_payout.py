"""The payout contract: forwards every payment, and changing the payout wallet."""

import smartpy as sp

from tests.setup import DELAY, T0, WALLETS, WEEK, at, deploy, payments


def pay(env, tez, sender=None, now=T0):
    env.payout.default(_sender=sender or env.acc.stranger, _amount=sp.tez(tez), _now=at(now))


@sp.add_test()
def test_payout():
    sc = sp.test_scenario("payout")
    env = deploy(sc)
    p, acc = env.payout, env.acc
    admin, guardian, stranger = acc.admin, acc.guardian, acc.stranger

    sc.h2("Anyone can pay; every payment goes straight on; nothing is kept")
    pay(env, 5)
    pay(env, 0)
    sc.verify(p.balance == sp.mutez(0))

    sc.h2("A new payout wallet: both wallets vote, the new wallet accepts with its own key")
    alice, bob = acc.alice, acc.bob
    p.propose_payout(alice.address, _sender=stranger, _now=at(T0),
                     _valid=False, _exception="NOT_ADMIN_OR_GUARDIAN")
    p.propose_payout(acc.payout.address, _sender=admin, _now=at(T0),
                     _valid=False, _exception="SAME_WALLET")
    p.accept_payout(alice.public_key, _sender=alice, _now=at(T0), _valid=False, _exception="NOT_READY")
    p.propose_payout(alice.address, _sender=admin, _now=at(T0))
    p.accept_payout(alice.public_key, _sender=alice, _now=at(T0), _valid=False, _exception="NOT_READY")
    p.propose_payout(alice.address, _sender=guardian, _now=at(T0))
    p.cancel_payout(_sender=admin, _now=at(T0), _valid=False, _exception="APPROVED")
    p.accept_payout(bob.public_key, _sender=alice, _now=at(T0), _valid=False, _exception="NOT_YOUR_KEY")
    p.accept_payout(alice.public_key, _sender=bob, _now=at(T0), _valid=False, _exception="NOT_YOUR_KEY")
    p.accept_payout(bob.public_key, _sender=bob, _now=at(T0), _valid=False, _exception="NOT_READY")
    p.accept_payout(alice.public_key, _sender=alice, _now=at(T0), _amount=sp.mutez(1),
                    _valid=False, _exception="NO_TEZ")
    p.accept_payout(alice.public_key, _sender=alice, _now=at(T0))
    sc.verify(p.data.payout == alice.public_key_hash)
    sc.verify(p.data.payout_approved == None)
    pay(env, 3)

    sc.h2("A contract can never be voted in: only a wallet can accept, with its key")
    p.propose_payout(env.sale.address, _sender=admin, _now=at(T0 + 1))
    p.propose_payout(env.sale.address, _sender=guardian, _now=at(T0 + 1))
    sc.verify(p.data.payout == alice.public_key_hash)
    p.propose_payout(env.sale.address, _sender=admin, _now=at(T0 + 2),
                     _valid=False, _exception="APPROVED")

    sc.h2("One wallet alone: ready after 48 hours; an objection blocks it")
    t = T0 + 2 * WEEK
    p.propose_payout(stranger.address, _sender=guardian, _now=at(t))
    p.cancel_payout(_sender=stranger, _now=at(t), _valid=False, _exception="NOT_ADMIN_OR_GUARDIAN")
    p.cancel_payout(_sender=admin, _now=at(t))
    p.accept_payout(stranger.public_key, _sender=stranger, _now=at(t + DELAY),
                    _valid=False, _exception="NOT_READY")
    t = T0 + 5 * WEEK
    p.propose_payout(bob.address, _sender=guardian, _now=at(t))
    p.accept_payout(bob.public_key, _sender=bob, _now=at(t + DELAY - 1),
                    _valid=False, _exception="NOT_READY")
    p.accept_payout(bob.public_key, _sender=bob, _now=at(t + DELAY))
    pay(env, 2)

    sc.h2("Changing the admin voids payout votes")
    t = T0 + 8 * WEEK
    p.propose_payout(alice.address, _sender=admin, _now=at(t))
    p.propose_admin(acc.new_admin.address, _sender=admin, _now=at(t))
    p.propose_admin(acc.new_admin.address, _sender=guardian, _now=at(t))
    p.accept_admin(_sender=acc.new_admin, _now=at(t))
    p.accept_payout(alice.public_key, _sender=alice, _now=at(t + DELAY),
                    _valid=False, _exception="NOT_READY")
    sc.verify(p.data.payout == bob.public_key_hash)
    sc.verify(p.balance == sp.mutez(0))

    sc.h2("The wallets the payments below must reach")
    for name, address in WALLETS.items():
        sc.verify(getattr(acc, name).address == sp.address(address))


expected = [(5_000_000, WALLETS["payout"]), (3_000_000, WALLETS["alice"]),
            (2_000_000, WALLETS["bob"])]
assert payments("payout") == expected, payments("payout")
print("payments ok")
