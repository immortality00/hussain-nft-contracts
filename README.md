# hussain-nft-contracts

The smart contracts behind Hussain Marzooq's collection on [hussain.art](https://hussain.art).
Collectors buy directly from these contracts. No marketplace sits in between.

Tezos first (`tezos/`). Ethereum and Base come later (`evm/`).

The code is MIT-licensed. That licence never covers the art: each artwork's terms are in its
own token metadata (`rights`, `rightsUri`).

## Tezos

Three contracts, written in [SmartPy](https://smartpy.tezos.com) 0.25.1 on SmartPy's FA2 library.

**Two wallets control every contract: an admin and a guardian** (`contracts/control.py`). The admin
does the daily work. The guardian is a second wallet on another device. It can only vote on
changes, stop all sales and remove a minter; it can never register, list, price or touch a token.
Every change of who controls a contract (its admin, its guardian, a minter, the payout wallet) is
decided by the two wallets' votes. Each wallet has its own vote and can only change its own:
- both wallets vote for the same address: the change is approved at once, and nothing can cancel
  or replace it;
- one wallet votes and the other hasn't voted: the change is ready after 48 hours. The other
  wallet blocks it by objecting (or by voting for another address);
- a vote counts for 9 days; an approved change must be completed within 7 days. A new admin,
  guardian or payout wallet completes the change itself, which proves somebody can sign for it;
- completing an admin or guardian change voids every other open vote and approval.

Every vote emits an event, so a watcher can alert on it.

**Collection** (`contracts/collection.py`) is permanent. There is one FA2 token per artwork,
and N copies of it make an edition.
- The admin registers an artwork with its IPFS metadata link, an edition cap (or none, for an
  open edition), an optional end time (required for an open edition) and a **floor price**.
- **The contract itself refuses any mint past the cap or after the end time, whoever the minter
  is.** The cap counts copies ever minted, so burning a copy never reopens an edition.
- **No copy is ever minted for less than its floor, whoever the minter is.** The floor is fixed
  at registration, like the cap. The minter passes the payment with the mint; the collection
  refuses anything under the floors of the copies and sends the whole payment on to the payout
  contract in the same operation.
- **An artwork's metadata is final at registration.** It must be an IPFS link to a base32 CIDv1
  (`ipfs://baf…`), no entry point can change it, and the same link can't be registered twice.
  An artwork registered by mistake can be retired while no copy exists, which frees its link.
- Later exhibitions and publications go in an append-only history log: up to 500 bytes of
  UTF-8 text and an optional `ipfs://` or `https://` link per record.
- Only listed minters can mint. Adding one is voted on like any change; removing one is immediate.
- The contract's own metadata (TZIP-16) is stored on-chain and fixed at deployment.
- Transfers, operators and balances come from SmartPy's FA2 library, unchanged except that they
  refuse tez. **Only a copy's owner can burn it**, not an operator such as a marketplace
  (`contracts/fa2_no_tez.py`).

**Payout** (`contracts/payout.py`) is permanent. Its address receives every sale (from the
collection) and is the royalty address in every artwork's metadata. It passes each payment
straight on to the payout wallet in the same operation and never holds tez, so changing the
payout wallet here moves sales and the royalties of every artwork ever registered. Nothing in
it refuses a payment.

**Sale** (`contracts/sale.py`) is a replaceable minter: an auction contract can be added beside
it later without touching any token.
- Each artwork has a price (never below its floor), a start, an optional end and a per-purchase
  limit. Listing, repricing, pausing and removing a listing take effect at once.
- `buy(token_id, quantity, recipient)` must pay exactly price × quantity. It mints to the
  recipient and passes the whole amount with the mint, so the contract never holds tez.
- Either wallet can pause all sales; only the admin can resume them.

**What no entry point can do:** change or remove an artwork's metadata or the contract
metadata, lower a floor, mint a copy for less than its floor, raise an edition cap or extend an
end time, move, freeze or burn anyone else's tokens, redirect a payment, or withdraw tez. Only
`buy`, `mint` (both pass the payment straight on) and the payout contract's `default` take tez;
every other entry point refuses it. `tests/test_interface.py` pins each contract's exact list of
entry points and views.

### Run

Python 3.10–3.13. Linux or macOS (Apple Silicon runs natively; Intel Macs need Docker).

```bash
python3 -m venv tezos/.venv
tezos/.venv/bin/python -m pip install --require-hashes --only-binary :all: -r tezos/requirements.txt
tezos/.venv/bin/python tezos/run_tests.py
```

To deploy, in this order (each needs the addresses of the ones before):
```bash
tezos/.venv/bin/python tezos/deploy/build.py payout --network shadownet --admin tz1… --guardian tz1… --wallet tz1…
tezos/.venv/bin/python tezos/deploy/build.py collection --network shadownet --admin tz1… --guardian tz1… --payout KT1…
tezos/.venv/bin/python tezos/deploy/build.py sale --network shadownet --admin tz1… --guardian tz1… --collection KT1…
tezos/.venv/bin/python tezos/deploy/check.py --network shadownet tezos/deployments/shadownet-v1/collection
```
1. `build.py` writes the exact code and starting storage to `tezos/deployments/<network>-<version>/`.
   `--wallet` is the payout wallet; `--payout` is the payout contract.
2. `check.py` has a public node typecheck them and measure the operation size.
3. In [smartpy.io/origination](https://smartpy.io/origination), turn on **JSON** in the
   contract's ⋯ menu and paste `<name>.storage.json` and `<name>.json`, then sign with the admin
   wallet. No key ever exists on disk. **Never paste the `.tz` text:** SmartPy rewrites pasted
   Michelson, so the deployed code would not match the build. A large contract freezes the page
   for a few minutes while it is sent to the wallet.
4. Run `verify.py` on the new address before using it.
5. Add the sale contract as a minter: both wallets vote for it (`propose_minter`), and it is
   added on the second vote.

### Check a deployment

Every deployment is tagged on the exact commit it was built from. Check out the tag, install the
pinned SmartPy, and compare the code your build produces with the code on chain:

```bash
tezos/.venv/bin/python tezos/deploy/verify.py --network shadownet \
  --address KT1… --compiled tezos/deployments/shadownet-v1/collection.json
```

| Network | Tag | Date | SmartPy | Payout | Collection | Sale |
|---|---|---|---|---|---|---|
| Shadownet | `tezos-shadownet-v1` | 2026-11-06/07 | 0.25.1 | `KT1BQMafNM1H67Tf4m7EtrAjsr1d3PvH9v3F` | `KT1CuxLwWSWuHysExf2GYJ3272xg7VnhoZdY` | `KT1R5nwPWnZivkF9W1qE1eEhfN7tgWrGNsdm` |

**Shadownet test, 2026-11-07.** `verify.py` matches all three contracts. A 1/1, an edition of 10
and an open edition were registered. A listing below the floor and purchases at the wrong amount
were refused. A collector bought two copies: the 2 tez went from the sale contract through the
collection and the payout contract to the payout wallet, exactly, and no contract kept any. A
0.1 tez royalty sent to the payout contract was passed on at once. objkt shows the copies and the
10% royalty. Every operation is on [TzKT](https://shadownet.tzkt.io) under the three addresses.

### Security

See [SECURITY.md](SECURITY.md) for the threat model, the review record and how to report a flaw
privately.
