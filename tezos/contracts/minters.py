"""The minter list of the collection contract.

Only listed contracts can mint: the sale contract now, an auction contract
later. Adding one is decided by the votes in control.py: when both wallets
vote for it, it is added at once; when one wallet votes and the other hasn't
voted, either wallet can confirm it 48 hours later. Removing one is
immediate and either wallet can do it. Every step emits an event.
"""

import smartpy as sp

from contracts.control import control
from contracts.types import htypes


@sp.module
def minters():
    import htypes
    import control

    class Minters(control.Control):
        def __init__(self, administrator, guardian):
            control.Control.__init__(self, administrator, guardian)
            self.data.minters = sp.cast(sp.big_map(), sp.big_map[sp.address, sp.unit])
            self.data.minter_votes = sp.cast(sp.big_map(), sp.big_map[sp.address, htypes.votes])

        @sp.entrypoint
        def propose_minter(self, minter):
            sp.cast(minter, sp.address)
            by_admin = self.signer_()
            assert not (minter in self.data.minters), "ALREADY_MINTER"
            empty = sp.record(by_admin=None, by_guardian=None)
            r = self.vote_(sp.record(
                votes=self.data.minter_votes.get(minter, default=empty),
                by_admin=by_admin,
                candidate=sp.Some(minter),
            ))
            self.data.minter_votes[minter] = r.votes
            sp.emit(sp.record(minter=minter, by_admin=by_admin, approved=r.agree),
                    tag="minter_vote")
            if r.agree:
                del self.data.minter_votes[minter]
                self.data.minters[minter] = ()
                sp.emit(minter, tag="minter_added")

        @sp.entrypoint
        def cancel_minter(self, minter):
            sp.cast(minter, sp.address)
            by_admin = self.signer_()
            empty = sp.record(by_admin=None, by_guardian=None)
            r = self.vote_(sp.record(
                votes=self.data.minter_votes.get(minter, default=empty),
                by_admin=by_admin,
                candidate=None,
            ))
            self.data.minter_votes[minter] = r.votes
            sp.emit(sp.record(minter=minter, by_admin=by_admin), tag="minter_objection")

        @sp.entrypoint
        def confirm_minter(self, minter):
            sp.cast(minter, sp.address)
            _ = self.signer_()
            votes = self.data.minter_votes.get(minter, error="NOT_READY")
            assert self.ready_alone_(sp.record(votes=votes, candidate=minter)), "NOT_READY"
            del self.data.minter_votes[minter]
            self.data.minters[minter] = ()
            sp.emit(minter, tag="minter_added")

        @sp.entrypoint
        def remove_minter(self, minter):
            sp.cast(minter, sp.address)
            _ = self.signer_()
            assert minter in self.data.minters, "NOT_MINTER"
            del self.data.minters[minter]
            sp.emit(minter, tag="minter_removed")
