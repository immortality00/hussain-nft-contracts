"""The sale contract: sells editions at a fixed price, minting on purchase.

Replaceable: it is one minter of the collection contract; an auction
contract can be added later beside it without touching any token.

A purchase pays exactly price x quantity and passes the whole amount with
the mint call; the collection checks it against the floor and sends it on
to the payout contract in the same operation, so this contract never holds
tez. A listing can never ask less than the artwork's floor price (read from
the collection), and listings, price changes and removals take effect at
once. Either wallet can pause all sales; only the
admin can resume them. No function can touch anyone's tokens.

A 1/1 that offers commercial rights can have a commercial price, never
below their floor. They are bought with the copy in one purchase
(buy with commercial=True), or later by whoever holds the copy
(buy_commercial_rights). The collection adds the mark only for the holder
and sends the payment on to the payout contract. Removing the commercial
price stops both at once, and pausing all sales stops them too.
"""

import smartpy as sp

from contracts.control import control
from contracts.types import htypes


@sp.module
def sale():
    import htypes
    import control

    class Sale(control.Control):
        def __init__(self, administrator, guardian, collection, metadata):
            control.Control.__init__(self, administrator, guardian)
            self.data.collection = sp.cast(collection, sp.address)
            self.data.paused = False
            self.data.sales = sp.cast(sp.big_map(), sp.big_map[sp.nat, htypes.sale])
            self.data.commercial_prices = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.mutez])
            self.data.metadata = sp.cast(metadata, sp.big_map[sp.string, sp.bytes])

        @sp.private(with_storage="read-only")
        def edition_(self, token_id):
            """The artwork's edition, read from the collection; never a retired one."""
            sp.cast(token_id, sp.nat)
            edition = sp.view(
                "edition", self.data.collection, token_id, sp.option[htypes.edition]
            ).unwrap_some(error="NO_EDITION_VIEW").unwrap_some(error="UNKNOWN_TOKEN")
            assert not edition.retired, "RETIRED"
            return edition

        @sp.private(with_storage="read-only", with_operations=True)
        def add_rights_(self, params):
            """Asks the collection to add the commercial rights mark, passing the payment."""
            sp.cast(params, sp.record(request=htypes.commercial_request, paid=sp.mutez))
            add = sp.contract(
                htypes.commercial_request, self.data.collection, entrypoint="add_commercial_rights"
            ).unwrap_some(error="NO_RIGHTS_ENTRYPOINT")
            sp.transfer(params.request, params.paid, add)

        @sp.entrypoint
        def set_sale(self, token_id, price, start, end, max_per_buy):
            sp.cast(token_id, sp.nat)
            sp.cast(price, sp.mutez)
            sp.cast(start, sp.timestamp)
            sp.cast(end, sp.option[sp.timestamp])
            sp.cast(max_per_buy, sp.nat)
            self.only_admin_()
            assert max_per_buy > 0, "MAX_ZERO"
            match end:
                case Some(e):
                    assert e > start, "END_BEFORE_START"
                case None:
                    pass
            edition = self.edition_(token_id)
            # The floor is never zero, so neither is any price.
            assert price >= edition.floor, "BELOW_FLOOR"
            paused = False
            match self.data.sales.get_opt(token_id):
                case Some(existing):
                    paused = existing.paused
                case None:
                    pass
            self.data.sales[token_id] = sp.record(
                price=price, start=start, end=end, max_per_buy=max_per_buy, paused=paused
            )
            sp.emit(
                sp.record(token_id=token_id, price=price, start=start, end=end,
                          max_per_buy=max_per_buy),
                tag="sale_set",
            )

        @sp.entrypoint
        def set_sale_paused(self, token_id, paused):
            sp.cast(token_id, sp.nat)
            sp.cast(paused, sp.bool)
            self.only_admin_()
            assert token_id in self.data.sales, "NO_SALE"
            self.data.sales[token_id].paused = paused
            sp.emit(sp.record(token_id=token_id, paused=paused), tag="sale_paused")

        @sp.entrypoint
        def remove_sale(self, token_id):
            sp.cast(token_id, sp.nat)
            self.only_admin_()
            assert token_id in self.data.sales, "NO_SALE"
            del self.data.sales[token_id]
            sp.emit(token_id, tag="sale_removed")

        @sp.entrypoint
        def set_commercial_price(self, token_id, price):
            sp.cast(token_id, sp.nat)
            sp.cast(price, sp.mutez)
            self.only_admin_()
            edition = self.edition_(token_id)
            floor = edition.commercial_floor.unwrap_some(error="NO_COMMERCIAL_RIGHTS")
            assert not edition.commercial, "HAS_COMMERCIAL_RIGHTS"
            # The commercial floor is never zero, so neither is this price.
            assert price >= floor, "BELOW_COMMERCIAL_FLOOR"
            self.data.commercial_prices[token_id] = price
            sp.emit(sp.record(token_id=token_id, price=price), tag="commercial_price_set")

        @sp.entrypoint
        def remove_commercial_price(self, token_id):
            sp.cast(token_id, sp.nat)
            self.only_admin_()
            assert token_id in self.data.commercial_prices, "NO_COMMERCIAL_PRICE"
            del self.data.commercial_prices[token_id]
            sp.emit(token_id, tag="commercial_price_removed")

        @sp.entrypoint
        def set_paused(self, paused):
            sp.cast(paused, sp.bool)
            # Either wallet can stop all sales; only the admin starts them again.
            if paused:
                _ = self.signer_()
            else:
                self.only_admin_()
            self.data.paused = paused
            sp.emit(paused, tag="all_paused")

        @sp.entrypoint
        def buy(self, token_id, quantity, recipient, commercial):
            sp.cast(token_id, sp.nat)
            sp.cast(quantity, sp.nat)
            sp.cast(recipient, sp.address)
            sp.cast(commercial, sp.bool)
            assert not self.data.paused, "SALES_PAUSED"
            listing = self.data.sales.get(token_id, error="NO_SALE")
            assert not listing.paused, "SALE_PAUSED"
            assert sp.now >= listing.start, "NOT_STARTED"
            match listing.end:
                case Some(e):
                    assert sp.now < e, "SALE_ENDED"
                case None:
                    pass
            assert quantity > 0 and quantity <= listing.max_per_buy, "BAD_QUANTITY"
            price = sp.mul(listing.price, quantity)
            rights = sp.mutez(0)
            if commercial:
                # Commercial rights come with a single copy, at their own price,
                # which is used up by this purchase.
                assert quantity == 1, "BAD_QUANTITY"
                rights = self.data.commercial_prices.get(token_id, error="NO_COMMERCIAL_PRICE")
                del self.data.commercial_prices[token_id]
            assert sp.amount == price + rights, "WRONG_AMOUNT"
            # A copy sent here could never be moved again (the collection
            # refuses itself and the payout contract).
            assert recipient != sp.self_address, "BAD_RECIPIENT"
            mint = sp.contract(
                sp.list[htypes.mint_request], self.data.collection, entrypoint="mint"
            ).unwrap_some(error="NO_MINT_ENTRYPOINT")
            sp.transfer(
                [sp.record(to_=recipient, token_id=token_id, amount=quantity)],
                price,
                mint,
            )
            if commercial:
                # Runs after the mint, so the recipient holds the copy by then.
                self.add_rights_(sp.record(
                    request=sp.record(token_id=token_id, holder=recipient), paid=rights
                ))
            sp.emit(
                sp.record(token_id=token_id, quantity=quantity, recipient=recipient,
                          buyer=sp.sender, paid=sp.amount, commercial=commercial),
                tag="sold",
            )

        @sp.entrypoint
        def buy_commercial_rights(self, token_id):
            sp.cast(token_id, sp.nat)
            assert not self.data.paused, "SALES_PAUSED"
            price = self.data.commercial_prices.get(token_id, error="NO_COMMERCIAL_PRICE")
            assert sp.amount == price, "WRONG_AMOUNT"
            del self.data.commercial_prices[token_id]
            # The collection adds the mark only if the caller holds the copy.
            self.add_rights_(sp.record(
                request=sp.record(token_id=token_id, holder=sp.sender), paid=sp.amount
            ))
            sp.emit(
                sp.record(token_id=token_id, holder=sp.sender, paid=sp.amount),
                tag="commercial_rights_sold",
            )
