"""Adding and removing minters on the collection contract."""

import smartpy as sp

from tests.setup import DAY, DELAY, T0, WEEK, at, deploy


@sp.add_test()
def test_minters():
    sc = sp.test_scenario("minters")
    env = deploy(sc, confirm_minter=False)
    c, acc = env.collection, env.acc
    admin, guardian, stranger = acc.admin, acc.guardian, acc.stranger
    m = env.sale.address

    def no(call, minter, sender, now, error, **kwargs):
        getattr(c, call)(minter, _sender=sender, _now=at(now), _valid=False, _exception=error, **kwargs)

    sc.h2("Both wallets vote: added at once")
    no("propose_minter", m, stranger, T0, "NOT_ADMIN_OR_GUARDIAN")
    no("confirm_minter", m, admin, T0, "NOT_READY")
    c.propose_minter(m, _sender=admin, _now=at(T0))
    no("confirm_minter", m, admin, T0, "NOT_READY")
    c.propose_minter(m, _sender=admin, _now=at(T0 + 1))
    sc.verify(~c.data.minters.contains(m))
    c.propose_minter(m, _sender=guardian, _now=at(T0 + 2))
    sc.verify(c.data.minters.contains(m))
    sc.verify(~c.data.minter_votes.contains(m))
    no("propose_minter", m, admin, T0 + 3, "ALREADY_MINTER")

    sc.h2("One wallet alone: either wallet confirms 48 hours later, within 9 days")
    bob = acc.bob.address
    c.propose_minter(bob, _sender=guardian, _now=at(T0))
    no("confirm_minter", bob, guardian, T0 + DELAY - 1, "NOT_READY")
    no("confirm_minter", bob, stranger, T0 + DELAY, "NOT_ADMIN_OR_GUARDIAN")
    no("confirm_minter", bob, admin, T0 + DELAY, "NO_TEZ", _amount=sp.mutez(1))
    c.confirm_minter(bob, _sender=admin, _now=at(T0 + DELAY))
    sc.verify(c.data.minters.contains(bob))
    late = acc.new_admin.address
    c.propose_minter(late, _sender=admin, _now=at(T0))
    no("confirm_minter", late, admin, T0 + 9 * DAY, "NOT_READY")

    sc.h2("An objection from the other wallet blocks it")
    alice = acc.alice.address
    c.propose_minter(alice, _sender=admin, _now=at(T0))
    no("cancel_minter", alice, stranger, T0, "NOT_ADMIN_OR_GUARDIAN")
    c.cancel_minter(alice, _sender=guardian, _now=at(T0 + 1))
    no("confirm_minter", alice, admin, T0 + DELAY, "NOT_READY")

    sc.h2("Changing a wallet voids every minter vote")
    t = T0 + 4 * WEEK
    c.propose_minter(alice, _sender=admin, _now=at(t))
    c.propose_guardian(acc.new_guardian.address, _sender=admin, _now=at(t))
    c.propose_guardian(acc.new_guardian.address, _sender=guardian, _now=at(t))
    c.accept_guardian(_sender=acc.new_guardian, _now=at(t))
    c.propose_minter(alice, _sender=acc.new_guardian, _now=at(t + 1))
    sc.verify(~c.data.minters.contains(alice))
    no("confirm_minter", alice, admin, t + DELAY, "NOT_READY")

    sc.h2("Either wallet removes a minter at once")
    no("remove_minter", m, stranger, t, "NOT_ADMIN_OR_GUARDIAN")
    c.remove_minter(m, _sender=acc.new_guardian, _now=at(t))
    c.remove_minter(bob, _sender=admin, _now=at(t))
    sc.verify(~c.data.minters.contains(m))
    no("remove_minter", m, admin, t, "NOT_MINTER")

    sc.h2("A minter a stolen wallet removed comes back with both wallets' votes, at once")
    c.propose_minter(m, _sender=admin, _now=at(t + 2))
    c.propose_minter(m, _sender=acc.new_guardian, _now=at(t + 2))
    sc.verify(c.data.minters.contains(m))
