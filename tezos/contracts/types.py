"""Types shared by the three contracts.

They all use these exact definitions, so a value one contract sends or
returns always has the type another expects.
"""

import smartpy as sp


@sp.module
def htypes():
    # One artwork's edition on the collection contract.
    # cap: None is an open edition (it must then have a mint_end).
    # minted: copies ever minted; burning never lowers it.
    # floor: the lowest price any sale may ever ask, fixed at registration.
    edition: type = sp.record(
        cap=sp.option[sp.nat],
        minted=sp.nat,
        mint_end=sp.option[sp.timestamp],
        floor=sp.mutez,
        retired=sp.bool,
        history_count=sp.nat,
    )

    mint_request: type = sp.record(
        to_=sp.address,
        token_id=sp.nat,
        amount=sp.nat,
    ).layout(("to_", ("token_id", "amount")))

    # One record in an artwork's history log (an exhibition, a publication).
    # text and uri are UTF-8 bytes: Michelson strings only allow ASCII.
    history_entry: type = sp.record(
        text=sp.bytes,
        uri=sp.option[sp.bytes],
        added_at=sp.timestamp,
    )

    # One wallet's vote on a change of admin, guardian, minter or payout
    # wallet: the address it proposes, or None to object. A vote counts for
    # 9 days, and only in the epoch it was cast in: any change of admin or
    # guardian moves the epoch on, which voids every earlier vote.
    vote: type = sp.record(candidate=sp.option[sp.address], at=sp.timestamp, epoch=sp.nat)

    # Each wallet's vote on one change. A wallet can only replace its own.
    votes: type = sp.record(by_admin=sp.option[vote], by_guardian=sp.option[vote])

    # A change both wallets voted for: ready at once, can't be cancelled,
    # lapses at `until` if not completed.
    approval: type = sp.record(candidate=sp.address, until=sp.timestamp, epoch=sp.nat)

    # One artwork's listing on the sale contract.
    sale: type = sp.record(
        price=sp.mutez,
        start=sp.timestamp,
        end=sp.option[sp.timestamp],
        max_per_buy=sp.nat,
        paused=sp.bool,
    )
