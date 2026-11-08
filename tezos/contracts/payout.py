"""The payout contract: passes every payment straight on to the payout wallet.

Permanent. Its address receives every sale (from the collection contract) and
every royalty (it is the royalty address written into each artwork's
metadata). Each payment goes on to the payout wallet in the same operation,
so this contract never holds tez, and changing the payout wallet here moves
both sales and the royalties of every artwork ever registered.

The payout wallet is a key hash, so it can only ever be a plain wallet,
which cannot refuse a payment. Changing it is decided by the votes in
control.py, and the new wallet completes the change itself with its public
key: money can never be sent to a contract, or to an address nobody can
sign for.
"""

import smartpy as sp

from contracts.control import control
from contracts.types import htypes


@sp.module
def payout():
    import htypes
    import control

    class Payout(control.Control):
        def __init__(self, administrator, guardian, wallet, metadata):
            control.Control.__init__(self, administrator, guardian)
            self.data.payout = sp.cast(wallet, sp.key_hash)
            self.data.payout_votes = sp.cast(
                sp.record(by_admin=None, by_guardian=None), htypes.votes
            )
            self.data.payout_approved = sp.cast(None, sp.option[htypes.approval])
            self.data.metadata = sp.cast(metadata, sp.big_map[sp.string, sp.bytes])

        @sp.entrypoint
        def default(self):
            # Must never fail, whoever pays: a marketplace whose royalty
            # payment failed could not sell the artwork at all. Zero is
            # skipped (Tezos refuses an empty transfer to a wallet).
            if sp.amount > sp.mutez(0):
                sp.transfer((), sp.amount, sp.implicit_account(self.data.payout))

        @sp.entrypoint
        def propose_payout(self, candidate):
            sp.cast(candidate, sp.address)
            by_admin = self.signer_()
            current = sp.to_address(sp.implicit_account(self.data.payout))
            assert candidate != current, "SAME_WALLET"
            assert self.open_(self.data.payout_approved).is_none(), "APPROVED"
            r = self.vote_(sp.record(
                votes=self.data.payout_votes,
                by_admin=by_admin,
                candidate=sp.Some(candidate),
            ))
            self.data.payout_votes = r.votes
            if r.agree:
                self.data.payout_approved = self.approval_(candidate)
                # The two votes are used up by the approval: once it lapses,
                # a change needs fresh votes.
                self.data.payout_votes = sp.record(by_admin=None, by_guardian=None)
            sp.emit(sp.record(candidate=candidate, by_admin=by_admin, approved=r.agree),
                    tag="payout_vote")

        @sp.entrypoint
        def cancel_payout(self):
            by_admin = self.signer_()
            assert self.open_(self.data.payout_approved).is_none(), "APPROVED"
            r = self.vote_(sp.record(
                votes=self.data.payout_votes,
                by_admin=by_admin,
                candidate=None,
            ))
            self.data.payout_votes = r.votes
            sp.emit(by_admin, tag="payout_objection")

        @sp.entrypoint
        def accept_payout(self, key):
            sp.cast(key, sp.key)
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            wallet = sp.hash_key(key)
            # Only a plain wallet, signing for itself, can become the payout wallet.
            assert sp.sender == sp.to_address(sp.implicit_account(wallet)), "NOT_YOUR_KEY"
            approved = self.open_(self.data.payout_approved) == sp.Some(sp.sender)
            alone = self.ready_alone_(
                sp.record(votes=self.data.payout_votes, candidate=sp.sender)
            )
            assert approved or alone, "NOT_READY"
            self.data.payout = wallet
            self.data.payout_votes = sp.record(by_admin=None, by_guardian=None)
            self.data.payout_approved = None
            sp.emit(wallet, tag="payout_changed")
