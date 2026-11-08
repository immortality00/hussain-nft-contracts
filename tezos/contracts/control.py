"""Who controls a contract: an admin wallet and a guardian wallet.

Used by all three contracts. The admin does the daily work. The guardian is
a second wallet, on another device, that can only vote on changes, stop all
sales and remove a minter: it can never register, list, price or touch a
token.

Every change of who controls a contract (its admin, its guardian, and in the
other modules its minters and its payout wallet) is decided by votes. Each
wallet has its own vote on each change and can only replace its own:
- propose_*(address) votes for that address;
- cancel_*() votes against any change;
- when both wallets have voted for the same address, the change is approved
  at once and the two votes are used up. An approved change can't be
  cancelled or replaced; it must be completed within 7 days or it lapses;
- when only one wallet has voted for an address, and the other has not
  voted at all, the change is ready 48 hours after that vote;
- a vote counts for 9 days (the 48 hours plus the 7 days after them).
A new admin, guardian or payout wallet completes its own change (accept_*),
which proves somebody can sign for that address.

So one wallet alone, stolen or not, can never change anything in less than
48 hours, the other wallet can block it in that time (every vote emits an
event, for alerts), and it can never undo or redirect what both wallets
agreed, because it can't touch the other wallet's vote.

Completing a change of admin or guardian moves `epoch` on, which voids every
vote and every approval still open, on every kind of change: a decision
never outlives the wallets that made it. So completing one change can void
another the two wallets had approved; they vote again.
"""

import smartpy as sp

from contracts.types import htypes


@sp.module
def control():
    import htypes

    class Control(sp.Contract):
        def __init__(self, administrator, guardian):
            self.data.administrator = sp.cast(administrator, sp.address)
            self.data.guardian = sp.cast(guardian, sp.address)
            self.data.epoch = sp.nat(0)
            self.data.admin_votes = sp.cast(
                sp.record(by_admin=None, by_guardian=None), htypes.votes
            )
            self.data.admin_approved = sp.cast(None, sp.option[htypes.approval])
            self.data.guardian_votes = sp.cast(
                sp.record(by_admin=None, by_guardian=None), htypes.votes
            )
            self.data.guardian_approved = sp.cast(None, sp.option[htypes.approval])

        @sp.private(with_storage="read-only")
        def only_admin_(self):
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            assert sp.sender == self.data.administrator, "NOT_ADMIN"

        @sp.private(with_storage="read-only")
        def signer_(self):
            """Either wallet may call; returns True for the admin."""
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            is_admin = sp.sender == self.data.administrator
            assert is_admin or sp.sender == self.data.guardian, "NOT_ADMIN_OR_GUARDIAN"
            return is_admin

        @sp.private(with_storage="read-only")
        def vote_(self, params):
            """The caller's vote replaces its previous one. Returns the new votes,
            and whether both wallets now vote for the same address."""
            sp.cast(params, sp.record(votes=htypes.votes, by_admin=sp.bool,
                                      candidate=sp.option[sp.address]))
            votes = params.votes
            candidate = params.candidate
            mine = sp.Some(sp.record(candidate=candidate, at=sp.now, epoch=self.data.epoch))
            other = votes.by_admin
            result = sp.record(by_admin=votes.by_admin, by_guardian=mine)
            if params.by_admin:
                other = votes.by_guardian
                result = sp.record(by_admin=mine, by_guardian=votes.by_guardian)
            agree = False
            match other:
                case Some(o):
                    # A vote counts in its own epoch, for 9 days (777,600 seconds).
                    stands = o.epoch == self.data.epoch and sp.now < sp.add_seconds(o.at, 777600)
                    agree = stands and candidate.is_some() and o.candidate == candidate
                case None:
                    pass
            return sp.record(votes=result, agree=agree)

        @sp.private(with_storage="read-only")
        def ready_alone_(self, params):
            """True if one wallet voted for `candidate` 48 hours ago or more and
            the other wallet's vote doesn't count (none, too old or stale)."""
            sp.cast(params, sp.record(votes=htypes.votes, candidate=sp.address))
            wanted = sp.Some(params.candidate)
            admin_stands = False
            admin_ready = False
            match params.votes.by_admin:
                case Some(a):
                    # The same 9 days as in vote_; the 48-hour wait is 172,800 seconds.
                    admin_stands = (a.epoch == self.data.epoch
                                    and sp.now < sp.add_seconds(a.at, 777600))
                    admin_ready = (admin_stands and a.candidate == wanted
                                   and sp.now >= sp.add_seconds(a.at, 172800))
                case None:
                    pass
            guardian_stands = False
            guardian_ready = False
            match params.votes.by_guardian:
                case Some(g):
                    guardian_stands = (g.epoch == self.data.epoch
                                       and sp.now < sp.add_seconds(g.at, 777600))
                    guardian_ready = (guardian_stands and g.candidate == wanted
                                      and sp.now >= sp.add_seconds(g.at, 172800))
                case None:
                    pass
            return (admin_ready and not guardian_stands) or (guardian_ready and not admin_stands)

        @sp.private(with_storage="read-only")
        def approval_(self, candidate):
            """The approval of a change both wallets voted for: 7 days to complete."""
            sp.cast(candidate, sp.address)
            # 604,800 seconds: the 7 days an approved change stays open.
            return sp.Some(sp.record(
                candidate=candidate, until=sp.add_seconds(sp.now, 604800), epoch=self.data.epoch
            ))

        @sp.private(with_storage="read-only")
        def open_(self, approved):
            """The approved change, if one is open (this epoch, not lapsed)."""
            sp.cast(approved, sp.option[htypes.approval])
            out = sp.cast(None, sp.option[sp.address])
            match approved:
                case Some(a):
                    if a.epoch == self.data.epoch and sp.now < a.until:
                        out = sp.Some(a.candidate)
                case None:
                    pass
            return out

        @sp.private(with_storage="read-only")
        def check_candidate_(self, candidate):
            sp.cast(candidate, sp.address)
            # Admin and guardian are always two different wallets.
            is_current = candidate == self.data.administrator or candidate == self.data.guardian
            assert not is_current, "SAME_WALLET"

        @sp.entrypoint
        def propose_admin(self, candidate):
            sp.cast(candidate, sp.address)
            by_admin = self.signer_()
            self.check_candidate_(candidate)
            assert self.open_(self.data.admin_approved).is_none(), "APPROVED"
            r = self.vote_(sp.record(
                votes=self.data.admin_votes,
                by_admin=by_admin,
                candidate=sp.Some(candidate),
            ))
            self.data.admin_votes = r.votes
            if r.agree:
                self.data.admin_approved = self.approval_(candidate)
                # The two votes are used up by the approval: once it lapses,
                # a change needs fresh votes.
                self.data.admin_votes = sp.record(by_admin=None, by_guardian=None)
            sp.emit(sp.record(candidate=candidate, by_admin=by_admin, approved=r.agree),
                    tag="admin_vote")

        @sp.entrypoint
        def cancel_admin(self):
            by_admin = self.signer_()
            assert self.open_(self.data.admin_approved).is_none(), "APPROVED"
            r = self.vote_(sp.record(
                votes=self.data.admin_votes,
                by_admin=by_admin,
                candidate=None,
            ))
            self.data.admin_votes = r.votes
            sp.emit(by_admin, tag="admin_objection")

        @sp.entrypoint
        def accept_admin(self):
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            approved = self.open_(self.data.admin_approved) == sp.Some(sp.sender)
            alone = self.ready_alone_(
                sp.record(votes=self.data.admin_votes, candidate=sp.sender)
            )
            assert approved or alone, "NOT_READY"
            self.data.administrator = sp.sender
            self.data.admin_votes = sp.record(by_admin=None, by_guardian=None)
            self.data.admin_approved = None
            self.data.epoch += 1
            sp.emit(sp.sender, tag="admin_changed")

        @sp.entrypoint
        def propose_guardian(self, candidate):
            sp.cast(candidate, sp.address)
            by_admin = self.signer_()
            self.check_candidate_(candidate)
            assert self.open_(self.data.guardian_approved).is_none(), "APPROVED"
            r = self.vote_(sp.record(
                votes=self.data.guardian_votes,
                by_admin=by_admin,
                candidate=sp.Some(candidate),
            ))
            self.data.guardian_votes = r.votes
            if r.agree:
                self.data.guardian_approved = self.approval_(candidate)
                # The two votes are used up by the approval: once it lapses,
                # a change needs fresh votes.
                self.data.guardian_votes = sp.record(by_admin=None, by_guardian=None)
            sp.emit(sp.record(candidate=candidate, by_admin=by_admin, approved=r.agree),
                    tag="guardian_vote")

        @sp.entrypoint
        def cancel_guardian(self):
            by_admin = self.signer_()
            assert self.open_(self.data.guardian_approved).is_none(), "APPROVED"
            r = self.vote_(sp.record(
                votes=self.data.guardian_votes,
                by_admin=by_admin,
                candidate=None,
            ))
            self.data.guardian_votes = r.votes
            sp.emit(by_admin, tag="guardian_objection")

        @sp.entrypoint
        def accept_guardian(self):
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            approved = self.open_(self.data.guardian_approved) == sp.Some(sp.sender)
            alone = self.ready_alone_(
                sp.record(votes=self.data.guardian_votes, candidate=sp.sender)
            )
            assert approved or alone, "NOT_READY"
            self.data.guardian = sp.sender
            self.data.guardian_votes = sp.record(by_admin=None, by_guardian=None)
            self.data.guardian_approved = None
            self.data.epoch += 1
            sp.emit(sp.sender, tag="guardian_changed")
