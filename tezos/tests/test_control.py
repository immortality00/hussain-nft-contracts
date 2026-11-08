"""Changing the admin and the guardian, on all three contracts.

The rule (control.py): each wallet votes; both voting for the same address
approves it at once (then nothing can cancel or replace it, and it lapses
after 7 days); one wallet's vote alone is ready after 48 hours if the other
wallet hasn't voted; a vote counts 9 days, and only until the next change
of admin or guardian.
"""

import smartpy as sp

from tests.setup import DAY, DELAY, T0, WEEK, at, deploy

NINE_DAYS = 9 * DAY


def refused(c, sender, now, error, call="propose_admin", candidate=None, **kwargs):
    entry = getattr(c, call)
    args = () if candidate is None else (candidate,)
    entry(*args, _sender=sender, _now=at(now), _valid=False, _exception=error, **kwargs)


def who_may_vote(sc, c, acc):
    admin, guardian, stranger = acc.admin, acc.guardian, acc.stranger
    refused(c, stranger, T0, "NOT_ADMIN_OR_GUARDIAN", candidate=acc.new_admin.address)
    refused(c, admin, T0, "NO_TEZ", candidate=acc.new_admin.address, _amount=sp.mutez(1))
    refused(c, admin, T0, "SAME_WALLET", candidate=guardian.address)
    refused(c, guardian, T0, "SAME_WALLET", candidate=admin.address)
    refused(c, admin, T0, "SAME_WALLET", call="propose_guardian", candidate=admin.address)
    refused(c, stranger, T0, "NOT_ADMIN_OR_GUARDIAN", call="cancel_admin")
    refused(c, admin, T0, "NO_TEZ", call="cancel_guardian", _amount=sp.mutez(1))
    refused(c, acc.new_admin, T0, "NOT_READY", call="accept_admin")


def both_wallets(sc, c, acc):
    sc.h3("Both wallets vote for the same address: approved, then accepted at once")
    admin, guardian, new = acc.admin, acc.guardian, acc.new_admin
    c.propose_admin(new.address, _sender=admin, _now=at(T0))
    refused(c, new, T0 + 1, "NOT_READY", call="accept_admin")
    c.propose_admin(new.address, _sender=guardian, _now=at(T0 + 2))
    sc.verify(c.data.admin_approved.unwrap_some().candidate == new.address)

    sc.h3("Once approved, neither wallet can cancel or replace it")
    refused(c, admin, T0 + 3, "APPROVED", call="cancel_admin")
    refused(c, guardian, T0 + 3, "APPROVED", call="cancel_admin")
    refused(c, admin, T0 + 3, "APPROVED", candidate=acc.stranger.address)
    refused(c, acc.stranger, T0 + 3, "NOT_READY", call="accept_admin")
    refused(c, new, T0 + 3, "NO_TEZ", call="accept_admin", _amount=sp.mutez(1))
    c.accept_admin(_sender=new, _now=at(T0 + 4))
    sc.verify(c.data.administrator == new.address)
    sc.verify(c.data.admin_approved == None)
    sc.verify(c.data.admin_votes.by_admin == None)
    sc.verify(c.data.epoch == 1)
    refused(c, admin, T0 + 5, "NOT_ADMIN_OR_GUARDIAN", candidate=acc.bob.address)

    sc.h3("The guardian the same way")
    c.propose_guardian(acc.new_guardian.address, _sender=guardian, _now=at(T0 + 6))
    c.propose_guardian(acc.new_guardian.address, _sender=new, _now=at(T0 + 7))
    c.accept_guardian(_sender=acc.new_guardian, _now=at(T0 + 8))
    sc.verify(c.data.guardian == acc.new_guardian.address)
    sc.verify(c.data.epoch == 2)
    refused(c, guardian, T0 + 9, "NOT_ADMIN_OR_GUARDIAN", call="cancel_guardian")


def swapped_vote(sc, c, acc):
    """Round 2, finding 1: a thief with a copy of the admin key swaps its own
    address in before the guardian's approval. The guardian's vote names the
    address it approves, so nothing is approved, and the thief's address is
    never ready either: the guardian's vote stands against it."""
    admin, guardian, thief, mine = acc.admin, acc.guardian, acc.stranger, acc.alice
    c.propose_admin(mine.address, _sender=admin, _now=at(T0))
    c.propose_admin(thief.address, _sender=admin, _now=at(T0 + 1))
    c.propose_admin(mine.address, _sender=guardian, _now=at(T0 + 2))
    sc.verify(c.data.admin_approved == None)
    refused(c, thief, T0 + 3, "NOT_READY", call="accept_admin")
    refused(c, thief, T0 + 1 + DELAY, "NOT_READY", call="accept_admin")
    refused(c, mine, T0 + 1 + DELAY, "NOT_READY", call="accept_admin")

    sc.h3("The owner votes again with the admin key: approved; the thief can't undo it")
    c.propose_admin(mine.address, _sender=admin, _now=at(T0 + 4))
    refused(c, admin, T0 + 5, "APPROVED", candidate=thief.address)
    refused(c, admin, T0 + 5, "APPROVED", call="cancel_admin")
    c.accept_admin(_sender=mine, _now=at(T0 + 6))
    sc.verify(c.data.administrator == mine.address)


def one_wallet(sc, c, acc):
    sc.h3("Admin wallet lost: the guardian's vote alone is ready after 48 hours")
    admin, guardian, new = acc.admin, acc.guardian, acc.new_admin
    c.propose_admin(new.address, _sender=guardian, _now=at(T0))
    refused(c, new, T0 + DELAY - 1, "NOT_READY", call="accept_admin")
    refused(c, acc.alice, T0 + DELAY, "NOT_READY", call="accept_admin")
    c.accept_admin(_sender=new, _now=at(T0 + DELAY))
    sc.verify(c.data.administrator == new.address)

    sc.h3("Guardian wallet lost: the admin's vote alone, the same; it lapses after 9 days")
    t = T0 + 2 * WEEK
    c.propose_guardian(acc.new_guardian.address, _sender=new, _now=at(t))
    refused(c, acc.new_guardian, t + DELAY - 1, "NOT_READY", call="accept_guardian")
    refused(c, acc.alice, t + DELAY, "NOT_READY", call="accept_guardian")
    refused(c, acc.new_guardian, t + NINE_DAYS, "NOT_READY", call="accept_guardian")
    c.accept_guardian(_sender=acc.new_guardian, _now=at(t + NINE_DAYS - 1))
    sc.verify(c.data.guardian == acc.new_guardian.address)


def objection(sc, c, acc):
    sc.h3("A stolen guardian votes for the thief; the admin objects in time")
    admin, guardian, thief = acc.admin, acc.guardian, acc.stranger
    c.propose_admin(thief.address, _sender=guardian, _now=at(T0))
    c.cancel_admin(_sender=admin, _now=at(T0 + 10))
    refused(c, thief, T0 + DELAY, "NOT_READY", call="accept_admin")
    refused(c, thief, T0 + DELAY + WEEK, "NOT_READY", call="accept_admin")

    sc.h3("Voting for another address stands against it too")
    t = T0 + 3 * WEEK
    c.propose_admin(thief.address, _sender=guardian, _now=at(t))
    c.propose_admin(acc.alice.address, _sender=admin, _now=at(t + 1))
    refused(c, thief, t + DELAY, "NOT_READY", call="accept_admin")
    refused(c, acc.alice, t + DELAY + 1, "NOT_READY", call="accept_admin")
    sc.verify(c.data.administrator == admin.address)

    sc.h3("Objections count 9 days too: a thief who keeps voting must keep being refused")
    t = T0 + 6 * WEEK
    c.propose_admin(thief.address, _sender=guardian, _now=at(t))
    c.cancel_admin(_sender=admin, _now=at(t))
    c.propose_admin(thief.address, _sender=guardian, _now=at(t + NINE_DAYS))
    c.accept_admin(_sender=thief, _now=at(t + NINE_DAYS + DELAY))
    sc.verify(c.data.administrator == thief.address)


def lapses_and_epochs(sc, c, acc):
    sc.h3("An approved change not completed within 7 days lapses; it can't be extended")
    admin, guardian, new = acc.admin, acc.guardian, acc.new_admin
    c.propose_admin(new.address, _sender=admin, _now=at(T0))
    c.propose_admin(new.address, _sender=guardian, _now=at(T0))
    refused(c, guardian, T0 + WEEK - 1, "APPROVED", candidate=new.address)
    refused(c, new, T0 + WEEK, "NOT_READY", call="accept_admin")
    c.cancel_admin(_sender=guardian, _now=at(T0 + WEEK))

    sc.h3("Staggered votes: the approval uses both up, so nothing is left once it lapses")
    t = T0 + 2 * WEEK
    c.propose_admin(new.address, _sender=admin, _now=at(t))
    c.propose_admin(new.address, _sender=guardian, _now=at(t + 4 * DAY))
    sc.verify(c.data.admin_votes.by_guardian == None)
    refused(c, new, t + 4 * DAY + WEEK, "NOT_READY", call="accept_admin")

    sc.h3("A completed change voids every vote cast before it")
    t = T0 + 4 * WEEK
    c.propose_admin(new.address, _sender=admin, _now=at(t))
    c.propose_guardian(acc.new_guardian.address, _sender=admin, _now=at(t))
    c.propose_guardian(acc.new_guardian.address, _sender=guardian, _now=at(t))
    c.accept_guardian(_sender=acc.new_guardian, _now=at(t))
    refused(c, new, t + DELAY, "NOT_READY", call="accept_admin")
    c.propose_admin(new.address, _sender=acc.new_guardian, _now=at(t + 1))
    sc.verify(c.data.admin_approved.unwrap_some().until == at(T0 + 3 * WEEK + 4 * DAY))
    c.accept_admin(_sender=new, _now=at(t + 1 + DELAY))
    sc.verify(c.data.administrator == new.address)

    sc.h3("It also voids an approval still open on another change")
    t = t + 2 * DELAY
    c.propose_admin(acc.alice.address, _sender=new, _now=at(t))
    c.propose_admin(acc.alice.address, _sender=acc.new_guardian, _now=at(t))
    c.propose_guardian(acc.bob.address, _sender=new, _now=at(t))
    c.propose_guardian(acc.bob.address, _sender=acc.new_guardian, _now=at(t))
    c.accept_guardian(_sender=acc.bob, _now=at(t))
    refused(c, acc.alice, t + 1, "NOT_READY", call="accept_admin")


@sp.add_test()
def test_control():
    sc = sp.test_scenario("control")
    for name in ("collection", "payout", "sale"):
        for part in (who_may_vote, both_wallets, swapped_vote, one_wallet, objection,
                     lapses_and_epochs):
            sc.h2("%s: %s" % (name, part.__name__))
            env = deploy(sc, confirm_minter=False)
            part(sc, getattr(env, name), env.acc)
