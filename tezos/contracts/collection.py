"""The collection contract: one FA2 token id per artwork, N copies an edition.

Permanent. It holds the artworks and enforces each edition itself: no
minter can mint past an edition's cap or after its end, and every copy, from
any minter, is paid at least the artwork's floor price (set when it is
registered), the payment going straight on to the payout contract. An
artwork's metadata can never change once registered, and the same metadata
can never be registered twice. Later exhibitions and publications go in an
append-only history log.

FA2 transfers, balances and operators are SmartPy's FA2 library
(owner-or-operator transfer policy), refusing tez; only a copy's owner can
burn it (see fa2_no_tez.py). Admin, guardian and minters: control.py and
minters.py. This file is longer than the others because it is one
contract's own logic.
"""

import smartpy as sp
from smartpy.templates import fa2_lib

from contracts.fa2_no_tez import fa2_no_tez
from contracts.minters import minters
from contracts.types import htypes

main = fa2_lib.main
t = fa2_lib.t


@sp.module
def collection():
    import main
    import t
    import htypes
    import fa2_no_tez
    import minters

    # Minters includes the admin and guardian (control.Control).
    class Collection(
        minters.Minters,
        fa2_no_tez.NoTezFungible,
        main.OnchainviewBalanceOf,
    ):
        def __init__(self, administrator, guardian, payout, metadata):
            main.OnchainviewBalanceOf.__init__(self)
            fa2_no_tez.NoTezFungible.__init__(self, metadata)
            minters.Minters.__init__(self, administrator, guardian)
            # The payout contract: every mint's payment goes there, at once.
            self.data.payout = sp.cast(payout, sp.address)
            self.data.editions = sp.cast(sp.big_map(), sp.big_map[sp.nat, htypes.edition])
            self.data.history = sp.cast(
                sp.big_map(), sp.big_map[sp.pair[sp.nat, sp.nat], htypes.history_entry]
            )
            # Every metadata link in use, and its token: one artwork, one token.
            self.data.uris = sp.cast(sp.big_map(), sp.big_map[sp.bytes, sp.nat])

        @sp.entrypoint
        def register(self, metadata_uri, cap, mint_end, floor):
            sp.cast(metadata_uri, sp.bytes)
            sp.cast(cap, sp.option[sp.nat])
            sp.cast(mint_end, sp.option[sp.timestamp])
            sp.cast(floor, sp.mutez)
            self.only_admin_()
            # Metadata must be an IPFS link (its content can never change) to a
            # base32 CIDv1, "ipfs://baf..." (59 characters): one spelling per
            # file, so it can't be registered twice in another encoding.
            ipfs_cid_v1 = sp.bytes("0x697066733a2f2f626166")
            assert sp.slice(0, 10, metadata_uri) == sp.Some(ipfs_cid_v1), "NOT_IPFS"
            assert sp.len(metadata_uri) >= 66 and sp.len(metadata_uri) <= 256, "BAD_URI"
            assert not (metadata_uri in self.data.uris), "URI_USED"
            assert floor > sp.mutez(0), "FLOOR_ZERO"
            match cap:
                case Some(c):
                    assert c > 0, "CAP_ZERO"
                case None:
                    assert mint_end.is_some(), "OPEN_EDITION_NEEDS_END"
            match mint_end:
                case Some(end):
                    assert end > sp.now, "END_IN_PAST"
                case None:
                    pass
            token_id = self.data.next_token_id
            self.data.token_metadata[token_id] = sp.record(
                token_id=token_id, token_info={"": metadata_uri}
            )
            self.data.supply[token_id] = 0
            self.data.editions[token_id] = sp.record(
                cap=cap, minted=0, mint_end=mint_end, floor=floor, retired=False, history_count=0
            )
            self.data.uris[metadata_uri] = token_id
            self.data.next_token_id += 1
            sp.emit(
                sp.record(token_id=token_id, metadata_uri=metadata_uri, cap=cap,
                          mint_end=mint_end, floor=floor),
                tag="registered",
            )

        @sp.entrypoint
        def retire(self, token_id):
            sp.cast(token_id, sp.nat)
            self.only_admin_()
            edition = self.data.editions.get(token_id, error="UNKNOWN_TOKEN")
            assert edition.minted == 0, "ALREADY_MINTED"
            assert not edition.retired, "RETIRED"
            self.data.editions[token_id].retired = True
            # Its metadata link is free again, to register correctly.
            del self.data.uris[self.data.token_metadata[token_id].token_info[""]]
            sp.emit(token_id, tag="retired")

        @sp.entrypoint
        def mint(self, batch):
            sp.cast(batch, sp.list[htypes.mint_request])
            assert sp.sender in self.data.minters, "NOT_MINTER"
            floor = sp.mutez(0)
            for request in batch:
                edition = self.data.editions.get(request.token_id, error="UNKNOWN_TOKEN")
                assert not edition.retired, "RETIRED"
                assert request.amount > 0, "ZERO_AMOUNT"
                # A copy sent to one of these contracts could never be moved again.
                assert request.to_ != sp.self_address, "BAD_RECIPIENT"
                assert request.to_ != self.data.payout, "BAD_RECIPIENT"
                floor += sp.mul(edition.floor, request.amount)
                match edition.mint_end:
                    case Some(end):
                        assert sp.now < end, "MINTING_ENDED"
                    case None:
                        pass
                minted = edition.minted + request.amount
                match edition.cap:
                    case Some(cap):
                        assert minted <= cap, "EDITION_FULL"
                    case None:
                        pass
                self.data.editions[request.token_id].minted = minted
                self.data.supply[request.token_id] += request.amount
                key = (request.to_, request.token_id)
                self.data.ledger[key] = self.data.ledger.get(key, default=0) + request.amount
            # Whichever minter sends it, every copy is paid at least its floor,
            # and the payment goes on to the payout contract in this operation.
            assert sp.amount >= floor, "BELOW_FLOOR"
            if sp.amount > sp.mutez(0):
                pay = sp.contract(sp.unit, self.data.payout).unwrap_some(error="NO_PAYOUT")
                sp.transfer((), sp.amount, pay)

        @sp.entrypoint
        def add_history(self, token_id, text, uri):
            sp.cast(token_id, sp.nat)
            sp.cast(text, sp.bytes)
            sp.cast(uri, sp.option[sp.bytes])
            self.only_admin_()
            edition = self.data.editions.get(token_id, error="UNKNOWN_TOKEN")
            assert sp.len(text) > 0 and sp.len(text) <= 500, "BAD_TEXT"
            match uri:
                case Some(u):
                    # Only links a page can safely show: ipfs:// or https://.
                    assert sp.len(u) > 8 and sp.len(u) <= 300, "BAD_URI"
                    is_ipfs = sp.slice(0, 7, u) == sp.Some(sp.bytes("0x697066733a2f2f"))
                    is_https = sp.slice(0, 8, u) == sp.Some(sp.bytes("0x68747470733a2f2f"))
                    assert is_ipfs or is_https, "BAD_URI"
                case None:
                    pass
            index = edition.history_count
            self.data.history[(token_id, index)] = sp.record(text=text, uri=uri, added_at=sp.now)
            self.data.editions[token_id].history_count = index + 1
            sp.emit(
                sp.record(token_id=token_id, index=index, text=text, uri=uri),
                tag="history_added",
            )

        @sp.onchain_view()
        def edition(self, token_id):
            """The edition of `token_id` (cap, copies minted, end, floor), or None."""
            sp.cast(token_id, sp.nat)
            return self.data.editions.get_opt(token_id)
