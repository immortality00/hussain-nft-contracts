# hussain-nft-contracts

The smart contracts behind Hussain Marzooq's collection on [hussain.art](https://hussain.art).
Collectors buy directly from these contracts. No marketplace sits in between.

Tezos first (`tezos/`). Ethereum and Base come later (`evm/`).

The code is MIT-licensed. That licence never covers the art: each artwork's terms are in its
own token metadata (`rights`, `rightsUri`).

## Tezos

Three contracts, written in [SmartPy](https://smartpy.tezos.com) 0.25.2 on SmartPy's FA2 library.

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
- **A 1/1 can offer commercial rights**, with their own floor fixed at registration. An edition
  never can, and a 1/1 registered without that floor never will. A minter adds the artwork's
  **commercial rights mark** only for the wallet holding the copy, and only when paid at least
  that floor, which goes on to the payout contract like a sale. The mark is set once and never
  cleared. It belongs to the token, so whoever holds the copy has the rights;
  `has_commercial_rights(token_id)` reads it.
- **An artwork's metadata is final at registration.** Its link must be exactly `ipfs://` and the
  file's raw CIDv1 (`bafkrei…`, 59 characters of a–z and 2–7, nothing after it), which depends on
  the file's bytes alone, so each file has one link; no entry point can change it, and the same
  link can't be registered twice, ever.
  An artwork registered by mistake can be retired while no copy exists. Its link stays used, so
  a corrected registration needs new metadata (hussain.art's carries its build time, so a rebuild
  always has a new link).
- Later exhibitions and publications go in an append-only history log: up to 500 bytes of
  UTF-8 text and an optional `ipfs://` or `https://` link per record.
- Only listed minters can mint. Adding one is voted on like any change; removing one is immediate.
- The contract's own metadata (TZIP-16) is stored on-chain and fixed at deployment.
- Transfers, operators and balances come from SmartPy's FA2 library, unchanged except that they
  refuse tez and no copy can be sent where it could never be moved again: the collection, the
  payout contract, or an address carrying an entrypoint (`tz1…%foo`), which no caller ever is.
  **Only a copy's owner can burn it**, not an operator such as a marketplace
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
- `buy(token_id, quantity, recipient, commercial)` must pay exactly price × quantity. It mints to
  the recipient and passes the whole amount with the mint, so the contract never holds tez.
- A 1/1 that offers commercial rights can also have a **commercial price**, never below their
  floor, set and removed at once like a listing. `buy` with `commercial` true sells the copy and
  the rights in one purchase, at exactly the two prices together, the rights going to the
  recipient. `buy_commercial_rights(token_id)` sells them later to whoever holds the copy, at the
  price set then. Removing the commercial price, or pausing all sales, stops both at once.
- Either wallet can pause all sales; only the admin can resume them.

**What no entry point can do:** change or remove an artwork's metadata or the contract
metadata, lower a floor, mint a copy for less than its floor, raise an edition cap or extend an
end time, add the commercial rights mark for a wallet that doesn't hold the copy, for less than
its floor or to an edition, clear the mark, move, freeze or burn anyone else's tokens, redirect
a payment, or withdraw tez. Only `buy`, `buy_commercial_rights`, `mint` and
`add_commercial_rights` (each passes the payment straight on) and the payout contract's `default`
take tez; every other entry point refuses it. `tests/test_interface.py` pins each contract's
exact list of entry points and views.

### Run

Python 3.10 or newer. SmartPy runs natively on Linux x86-64 and Apple Silicon Macs; other
machines need Docker.

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
tezos/.venv/bin/python tezos/deploy/check.py --network shadownet tezos/deployments/shadownet-v2/collection
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
pinned SmartPy, rebuild each contract with `build.py` and the addresses in its
`<name>.storage.json` (git should show no change), then compare it with the chain:

```bash
tezos/.venv/bin/python tezos/deploy/verify.py --network shadownet \
  --address KT1… --compiled tezos/deployments/shadownet-v2/collection.json
```

| Network | Tag | Date | SmartPy | Payout | Collection | Sale |
|---|---|---|---|---|---|---|
| Shadownet | `tezos-shadownet-v1` | 2026-11-06/07 | 0.25.1 | `KT1BQMafNM1H67Tf4m7EtrAjsr1d3PvH9v3F` | `KT1CuxLwWSWuHysExf2GYJ3272xg7VnhoZdY` | `KT1R5nwPWnZivkF9W1qE1eEhfN7tgWrGNsdm` |
| Shadownet | `tezos-shadownet-v2` | 2026-11-15 | 0.25.2 | `KT1MMHoyb2hmQet7FcSJ9UvMqDtXf8PEuyPT` | `KT19Dsj3JFbFcAujxgmLSiTuT2TxH7WHqyJx` | `KT1FJAwejtFW4z8V81LBCkuMBDuBRdJU3b73` |

v1 has no commercial rights and accepts copies sent to an address carrying an entrypoint; v2
replaces it.

**Shadownet test, 2026-11-07.** `verify.py` matches all three contracts. A 1/1, an edition of 10
and an open edition were registered. A listing below the floor and purchases at the wrong amount
were refused. A collector bought two copies: the 2 tez went from the sale contract through the
collection and the payout contract to the payout wallet, exactly, and no contract kept any. A
0.1 tez royalty sent to the payout contract was passed on at once. objkt shows the copies and the
10% royalty. Every operation is on [TzKT](https://shadownet.tzkt.io) under the three addresses.

**Shadownet test of v2, 2026-11-16.** `verify.py` matches all three contracts, and the sale
contract was added as a minter by both wallets' votes. Two 1/1s were registered with a 1 tez floor
and a 2 tez commercial floor, listed at 1 tez with a 2 tez commercial price. One was bought with
its commercial rights in one approval for exactly 3 tez: the sale minted the copy with 1 tez and
added the mark with 2 tez, each payment going through the collection and the payout contract to
the payout wallet. The other was bought for 1 tez; its holder then bought the rights for exactly
2 tez and moved the copy to another wallet, and `has_commercial_rights` still answers true. Both
purchases were signed by the admin wallet, the first copy going to a collector's address: buying
treats every wallet the same. Simulated against the deployed contracts, these were refused: the
rights bought by a wallet that doesn't hold the copy (`NOT_HOLDER`), wrong amounts
(`WRONG_AMOUNT`), a second copy of a 1/1 (`EDITION_FULL`), a commercial floor on an edition of 2
(`NOT_SINGLE`), a listing or commercial price below its floor, and mints and transfers to the
collection, the payout contract or an address carrying an entrypoint (`BAD_RECIPIENT`), which the
v1 collection accepts. No contract kept any tez.

| On v2 | Fee (tez) | Storage (tez) |
|---|---|---|
| Register an artwork | 0.0006 | 0.084–0.095 |
| List it, or set its commercial price | 0.005 | 0.018–0.022 |
| Buy, with or without commercial rights | 0.002–0.003 | 0.017 the first time a wallet holds that artwork |
| Buy the rights later | 0.0014 | none |
| Send a copy to a new holder | 0.0006 | 0.017 |

Deploying all three cost about 13.4 tez (the collection 7.97), paid once.

### Security

See [SECURITY.md](SECURITY.md) for the threat model, the review record and how to report a flaw
privately.
