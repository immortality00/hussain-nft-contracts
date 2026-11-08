"""The FA2 entry points of SmartPy's FA2 library, refusing tez.

The library's transfer, update_operators, balance_of and burn accept tez
that nothing could ever send back. These are the library's own bodies,
unchanged, with one added first line: refuse any tez sent with the call.
One more change, in burn: only a copy's owner can burn it. The library
also lets the owner's operators burn, which would let a marketplace that
was approved to sell a copy destroy it instead.

Adapted from SmartPy's FA2 library (smartpy-tezos 0.25.1, templates/fa2_lib.py):

    Copyright (c) 2025 - present Trilitech Limited
    Permission is hereby granted, free of charge, to any person obtaining
    a copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import smartpy as sp
from smartpy.templates import fa2_lib

main = fa2_lib.main
t = fa2_lib.t


@sp.module
def fa2_no_tez():
    import main
    import t

    class NoTezFungible(main.Fungible):
        def __init__(self, metadata):
            main.Fungible.__init__(self, metadata, {}, [])

        @sp.entrypoint
        def update_operators(self, batch):
            sp.cast(batch, t.update_operators_params)
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            if self.private.policy.supports_operator:
                for action in batch:
                    match action:
                        case add_operator(operator):
                            _ = self.check_operator_update_permissions_(operator)
                            self.data.operators[operator] = ()
                        case remove_operator(operator):
                            _ = self.check_operator_update_permissions_(operator)
                            del self.data.operators[operator]
            else:
                raise "FA2_OPERATORS_UNSUPPORTED"

        @sp.entrypoint
        def balance_of(self, params):
            sp.cast(params, t.balance_of_params)
            assert sp.amount == sp.mutez(0), "NO_TEZ"

            @sp.effects(with_storage="read-write")
            def f_process_request(param):
                (req, is_defined, balance) = param
                sp.cast(req, t.balance_of_request)
                return sp.cast(
                    sp.record(request=req, balance=balance((is_defined, req))),
                    t.balance_of_response,
                )

            answers = [
                f_process_request((x, self.is_defined_, self.balance_))
                for x in params.requests
            ]
            sp.transfer(answers, sp.mutez(0), params.callback)

        @sp.entrypoint
        def transfer(self, batch):
            sp.cast(batch, t.transfer_params)
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            if self.private.policy.supports_transfer:
                for transfer in batch:
                    for tx in transfer.txs:
                        # The ordering of assert is important:
                        # 1) token_undefined, 2) transfer permission 3) balance
                        assert self.is_defined_(tx.token_id), "FA2_TOKEN_UNDEFINED"
                        _ = self.check_tx_transfer_permissions_(
                            sp.record(
                                from_=transfer.from_, to_=tx.to_, token_id=tx.token_id
                            )
                        )
                        if tx.amount > 0:
                            tx_params = sp.record(from_=transfer.from_, tx=tx)
                            self.transfer_tx_(tx_params)
            else:
                raise "FA2_TX_DENIED"

        @sp.entrypoint
        def burn(self, batch):
            sp.cast(
                batch,
                sp.list[
                    sp.record(
                        from_=sp.address,
                        token_id=sp.nat,
                        amount=sp.nat,
                    ).layout(("from_", ("token_id", "amount")))
                ],
            )
            assert sp.amount == sp.mutez(0), "NO_TEZ"
            assert self.private.policy.supports_transfer, "FA2_TX_DENIED"
            for action in batch:
                assert self.is_defined_(action.token_id), "FA2_TOKEN_UNDEFINED"
                assert sp.sender == action.from_, "FA2_NOT_OWNER"
                from_ = (action.from_, action.token_id)
                self.data.ledger[from_] = sp.as_nat(
                    self.data.ledger.get(from_, default=0) - action.amount,
                    error="FA2_INSUFFICIENT_BALANCE",
                )
                is_supply = sp.is_nat(
                    self.data.supply.get(action.token_id, default=0) - action.amount
                )
                match is_supply:
                    case Some(supply):
                        self.data.supply[action.token_id] = supply
                    case None:
                        self.data.supply[action.token_id] = 0
