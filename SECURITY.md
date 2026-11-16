# Security

## Reporting a flaw

Report a vulnerability privately through this repository's **Security** tab → **Report a
vulnerability**. Please don't open a public issue for anything that could put collectors at risk.

## How the contracts are kept safe

- **No key on any server.** Every deployment and admin action is signed in a wallet in a
  browser. Nothing in this repository or on hussain.art holds a key.
- **Buying never asks a collector for a token approval or a message signature.** It is one
  transaction at the exact price.
- **No upgradeability.** The collection and payout contracts never change. A new sale or auction
  contract can only be added as a minter.
- **Two wallets, one rule.** Changing an admin, a guardian, a minter or the payout wallet needs
  both wallets' votes for the same address, or one wallet's vote and 48 hours in which the other
  wallet can object. Each wallet can only change its own vote. Every vote emits an event, and
  hussain.art will alert the owner on each one.
- **hussain.art's part is not built yet.** The alerts, and the site's rules below (showing only
  what it registered and wrote itself), come with the site's minting pages, before any mainnet
  deployment. On Shadownet nothing of value is at stake.
- **A floor price per artwork, fixed at registration and enforced by the permanent collection on
  every mint**, whichever minter sends it. The payment always goes on to the payout contract in
  the same operation.
- **Commercial rights the same way.** A 1/1's commercial floor is fixed at registration, and the
  permanent collection adds the commercial rights mark only for the wallet holding the copy,
  only when paid at least that floor (sent on to the payout contract in the same operation), and
  only once. Nothing clears it.

## What a stolen wallet can and can't do

**The admin wallet alone** can, at once:
- list and reprice unsold copies, never below each artwork's floor, with the money still going to
  the payout wallet;
- set or remove a 1/1's commercial price, never below its commercial floor, the money still going
  to the payout wallet, and only the copy's holder (or, with the copy, its recipient) can buy the
  rights;
- register new artworks, never with metadata already registered;
- add history records, pause or remove listings, pause all sales, retire an artwork no copy
  exists of (its link stays used, so its metadata can never come back with lower floors);
- vote for a new admin, guardian, minter or payout wallet, which is ready after 48 hours unless
  the guardian objects. Even a minter added that way pays at least the floor for every copy, to
  the payout wallet.

**The guardian wallet alone** can vote or object, pause all sales and remove a minter.

**Neither can** take a sold copy, lower a floor, mint a copy for less than its floor, raise a cap,
change metadata, add the commercial rights mark below its floor or for a wallet that doesn't hold
the copy, clear the mark, send money anywhere but the payout wallet, or undo or redirect a change
both wallets voted for. With both wallets in
hand, the owner replaces a stolen one at once, and the thief can't stop it: vote for the new
wallet with both, then accept with the new one.

## Known limits

- **A wallet stolen while the other is lost is a stalemate.** The thief objects to the owner's
  changes and the owner objects to the thief's, and objections, like votes, must be renewed every
  9 days. Art and money stay safe, but the contracts can't be handed over again; the way out is a
  new collection contract. No two-wallet design can avoid this. A paper copy of each wallet's
  recovery phrase, kept apart, does: a wallet is then never lost.
- **A thief with one wallet's key can repeat instant nuisances until that wallet is replaced**
  (with both wallets, at once): pausing all sales, removing the sale contract as a minter (both
  wallets' votes bring it back at once), or, with the admin key, listing at the floor and
  resuming sales the guardian paused. The guardian's lasting stop is removing the sale contract
  as a minter: one wallet alone can't add it back in less than 48 hours.
- **Completing an admin or guardian change voids every other open vote and approval**, on every
  kind of change, even one both wallets approved. The wallets vote again for anything still
  wanted. This keeps a decision from outliving the wallets that made it.
- **A thief with the admin wallet can register a counterfeit** under a different metadata link (a
  link ever registered is refused, even after its artwork is retired, and a link must be the
  file's raw CIDv1, so a file has one link; but a copy of the file with any change has a new
  one) and sell it, the money going to the owner's payout wallet. hussain.art will show only the artworks it registered itself and alert on every
  registration; the owner then replaces the admin wallet with both wallets.
- **A thief with the admin wallet can add history records**, which can never be removed: up to 500
  bytes of text and an `ipfs://` or `https://` link each. hussain.art will show only the records
  it wrote itself, and must escape the text it shows.
- **Keep a little tez in the payout wallet, from before deployment on.** If it is ever emptied,
  Tezos deletes the account, and the next payment pays about 0.064 tez to create it again: a
  payer whose operation doesn't allow that storage, or can't pay it, fails, which could stop a
  purchase or a marketplace's royalty payment. Nothing in the payout contract refuses a payment,
  but like any operation one still needs enough gas.
- **The admin of each contract is separate.** Changing wallets means changing all three
  contracts; hussain.art will do it in one signature per wallet.
- **Fixed-price sales are first come, first served.** A bot can buy as fast as anyone, up to the
  per-purchase limit each time (OpenTezos flaw 6). This is accepted for fixed-price editions.
- **Copies can be burned by their owners only.** Burning lowers the supply but never the count of
  copies minted, so it never reopens an edition.
- **Operators can be approved for a token id before it is registered**, as FA2 allows. An operator
  can move a copy but never burn it.
- **An open edition's end time has no upper limit.** It is the admin's choice at registration.
- **Commercial rights are offered at registration or never.** A 1/1 registered without a
  commercial floor can never have the mark, and an edition can never offer the rights.
- **Any minter can add the mark for a copy's holder** by paying at least the commercial floor
  itself, the money going to the payout wallet. A minter voted in by a stolen wallet could
  give a holder the rights for that floor; the owner always receives at least the floor.
- **Only the holder can buy the rights after the purchase**, since `buy_commercial_rights` names
  its caller as the holder. A copy held by a contract (a marketplace escrow, a multisig) gets
  them only if that contract makes the call.
- **The mark stays on a burned token.** With no copy left, nobody holds the rights.
- **A commercial price can outlive its use.** If another minter adds the mark, the sale contract
  keeps that token's commercial price until the admin removes it; buying the rights then fails as
  a whole, and nothing is paid.
- **A copy can still be sent to the sale contract, or to any other address that can never move
  it** (a mistyped one), as FA2 allows. That is its owner's choice, like burning it. Mints and
  transfers to the collection, the payout contract or an address carrying an entrypoint are
  refused.
- **Marketplaces show only the fixed token metadata.** It says that commercial rights, when
  bought, are recorded on-chain; the mark itself is read from the contract
  (`has_commercial_rights`, or the `edition` view), which is what hussain.art shows.

## Review record

The brief every reviewer gets is [tezos/review/PROMPT.md](tezos/review/PROMPT.md). There was no
paid audit. The review was the test suite, mutation checks (each safeguard broken on purpose to
prove a test catches it), the OpenTezos flaw list, and several AI models trying to break the
contracts.

### Round 1: Claude Opus, Sonnet and Haiku, on the two-contract version

None found anything critical or high.

| Finding | Severity | Found by | What was done |
|---|---|---|---|
| A stolen admin key can reprice unsold copies to 1 mutez and buy them, or mint an open edition without limit, at once | Medium | all three | A floor price per artwork, fixed at registration and enforced on every listing. Repricing stays instant, as on every marketplace |
| One key, no recovery: after a theft, owner and thief cancel each other for ever | Low / design | Opus, Sonnet | A guardian wallet on every contract and one rule for all changes (`control.py`) |
| Retire and closing a listing were instant and final | Medium | Haiku | `close_sale` replaced by `remove_sale` (relist any time). Retire still needs zero copies minted, and now frees the metadata link |
| Counterfeits: the same metadata could be registered again as a new token | Low–medium | Opus | Each metadata link can be registered once (`uris`) |
| Proposals survived an admin handover | Low | Sonnet | Completing an admin or guardian change voids every older proposal (`epoch`) |
| Proposals never expired | Low | all three | A ready change must be completed within 7 days |
| A copy could be minted to a contract and stuck there for ever | Low / note | Haiku, Opus | `buy` refuses the collection, payout and sale contracts as recipient |
| The history log accepted any link scheme (`javascript:`) | Note | Opus | Only `ipfs://` and `https://` links are accepted |
| An operator (a marketplace) could burn a copy | Note | all three | Burning is owner-only |
| `verify.py` compared only the code | Note | Opus | It also checks the metadata big map and every address the contract was deployed with |
| The deployment files used placeholder addresses | Note | Haiku | Deleted; real deployments are built from real addresses |
| No events on mint, transfer and burn | Note | Sonnet, Haiku | Kept: indexers read balances from the ledger, and `buy` emits `sold` |
| The FA2 library's off-chain views aren't listed in the contract metadata | Note | Haiku | Deliberate: the contract metadata lists no views, so nothing overrides the stored token metadata |
| An open edition can end in the year 9999 | Note | Opus | Accepted; recorded under Known limits |
| Unused helper, unusual class order | Note | Sonnet, Haiku | Removed and reordered |

### Round 2: Claude Opus, on the three-contract version

| Finding | Severity | What was done |
|---|---|---|
| An approval didn't name what it approved: a thief with a copy of one wallet could swap its own address in just before the other wallet's approval | High | Approving is now voting for the same address, and each wallet can only change its own vote (`control.py`). A swapped address never matches the other wallet's vote; the test `swapped_vote` replays the attack on all three contracts |
| A thief with one key could cancel between the owner's separate steps, so even with both wallets the owner couldn't be sure to win | Low | Same fix: nothing the thief does with one key touches the other wallet's vote, and a change both wallets voted for can't be cancelled or replaced |
| Approving again reset the 7-day window, so one wallet could keep a proposal alive | Low | An approved change can't be voted on again; it lapses 7 days after approval, and votes count 9 days |
| `verify.py` only checked that the expected addresses appeared somewhere | Low | It now compares the whole starting storage, every big map entry included, and refuses an admin equal to the guardian |
| "The same metadata is refused" overstated it: only the same link is refused | Note | Wording corrected under Known limits |
| A stolen admin key can add history records that can't be removed | Note | Recorded under Known limits; hussain.art shows only its own records |
| An emptied payout wallet costs each payer about 0.064 tez | Note | Recorded under Known limits |

### Round 3: ChatGPT and Gemini, on the vote version

| Finding | Severity | Found by | What was done |
|---|---|---|---|
| With staggered votes, a change could still be accepted after its approval lapsed, through the later vote alone | High | ChatGPT | An approval now uses up both votes; once it lapses, a change needs fresh votes. Test: `lapses_and_epochs` |
| Any minter could mint below the floor, or keep the payment | High | ChatGPT | The permanent collection now checks every mint against the floors and sends the payment on to the payout contract itself; minters pass the payment with the mint. Tests: `test_floor_on_every_mint` |
| Completing one change voids an approval the two wallets gave another | Medium | ChatGPT | Kept on purpose: a decision never outlives the wallets that made it. Now stated in `control.py`, the README and Known limits, and pinned by a test |
| Either wallet can remove a minter both approved | Medium | ChatGPT | Kept on purpose: it is the emergency stop. A thief who repeats it is stopped by replacing that wallet with both, at once (Known limits) |
| A stolen admin key can resume sales the guardian paused | Medium | ChatGPT | Kept: the guardian's lasting stop is removing the sale contract as a minter, and resumed sales still pay at least the floor to the payout wallet (Known limits) |
| `ipfs://x` and other spellings of the same file were accepted | Low | ChatGPT | Links must now be a base32 CIDv1 (`ipfs://baf…`, 59 characters), so CIDv0 and base36 spellings are refused. Paths remain free; hussain.art builds each link from Pinata's answer |
| "Never fails" depends on the operation having enough gas | Note | ChatGPT | Wording corrected in the README and Known limits. On Shadownet a royalty sent to the payout contract was passed on at once (README, Shadownet test) |
| The collection should add the library's off-chain `token_metadata` view | Medium | Gemini | Not done, on purpose: TZIP-12 lets a contract provide token metadata through the `token_metadata` big map (which TzKT and objkt read) or an off-chain view, and an advertised view takes precedence. Publishing none, and locking the contract metadata, keeps every artwork's metadata in the big map where no one can change it |

### Round 4: Claude Opus, Sonnet and Haiku, ChatGPT and Gemini, on the commercial rights version

The whole code, including Round 3's floor and payment change, which no reviewer had seen. Before
it: each new safeguard broken on purpose, every one caught by a test, and the OpenTezos flaw
list. After it, Opus checked its own fixes in the final code.

| Finding | Severity | Found by | What was done |
|---|---|---|---|
| A recipient carrying an entrypoint (`tz1…%foo`, `KT1…%mint`) passed the recipient checks and became a ledger owner no caller can ever be, stranding a paid copy and its commercial rights | Medium | ChatGPT | `mint` and `transfer` refuse any recipient whose packed address isn't the 28 bytes of a plain one (`BAD_RECIPIENT`). SmartPy's test simulator can't represent such addresses, so this was checked on Shadownet by simulating against the deployed contracts: the v1 collection accepts such a transfer; v2 refuses it, and a mint to one (README, Shadownet test of v2) |
| The same file could be registered again under another link: a trailing `/`, `?`, `#`, a path or other characters, or (Opus, checking the first fix) another CID of the same bytes, dag-pb instead of raw or a last character with its unused bits set | Medium / low | ChatGPT, Sonnet, Haiku, Opus | A link must be exactly `ipfs://` and the file's raw CIDv1 (`bafkrei…`, base32, its last character canonical), which depends on the file's bytes alone. Tests: `test_register` |
| Retiring an unsold artwork freed its exact link: a stolen admin key could re-register it with 1-mutez floors and buy it, getting round the floors fixed at registration | Low | Opus | A link is registered once, ever: `retire` keeps it used. Test: `test_retire` |
| A copy could be transferred to the collection or the payout contract, which can never move it | Low | Haiku, Opus | `transfer` refuses both (`BAD_RECIPIENT`), as `mint` did. Test: `test_transfers_and_operators` |
| The test helper that reads payments from the scenario log counted a payment whose operation failed later | Note | ChatGPT | It now counts only operations that went through. `test_rollback_after_mint` mints, then fails, and the old helper would have counted that payment |
| The `edition` record, which the permanent view returns to every minter, had no pinned layout | Note | Opus | Pinned; the compiled code is unchanged |
| Either wallet can remove a minter both approved | Medium | ChatGPT | Kept, as in Round 3: it is the emergency stop (Known limits) |
| Completing a role change one wallet started voids an approval both wallets gave | Medium | ChatGPT | Kept, as in Round 3: a decision never outlives the wallets that made it; the other wallet objects within the 48 hours (Known limits) |
| Admin and guardian could be the same wallet at deployment | Low / medium | ChatGPT, Sonnet, Haiku | Not possible on-chain: Tezos runs no code at deployment, so a contract can't check its starting storage. `build.py` refuses it, and `verify.py`, required before any deployment is used, checks it |
| One wallet alone can add a minter after 48 hours if the other doesn't object | Medium (design) | Haiku | Kept: the rule since Round 2. Every vote emits an event for alerts, and even such a minter pays at least each copy's floor to the payout wallet |
| A payment can fail when an emptied payout wallet must be created again and the payer's operation doesn't allow that storage | Low | ChatGPT | Known limit reworded: keep the payout wallet funded from before deployment on |
| A commercial price outlives its use if another minter adds the mark | Low | Sonnet | Kept: buying the rights then fails as a whole and nothing is paid (Known limits) |
| Any minter can add the mark for a holder by paying the commercial floor | Note | Haiku | Kept on purpose: never below the floor, always to the payout wallet (Known limits) |
| An objection lapses after 9 days, like any vote | Note | Sonnet | Already under Known limits |
| `balance_of` answering a wallet instead of a contract fails | Note | Haiku | Kept: FA2 sends the answer to a contract |

Gemini found nothing at any severity.
