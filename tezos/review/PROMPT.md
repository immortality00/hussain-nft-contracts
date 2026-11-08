# Review brief

The same brief goes to every reviewer, human or AI. The findings and what was done about each are
recorded in [SECURITY.md](../../SECURITY.md).

## What you are reviewing

Three Tezos contracts, written in SmartPy 0.25.1 (Ushuaia protocol). They sell a photographer's
artworks directly to collectors.

- `contracts/collection.py`: the permanent FA2 token contract, one token id per artwork with N
  copies per edition, a floor price per artwork, unique metadata links and a history log. It uses
  SmartPy's FA2 library (`main.Fungible`, `main.OnchainviewBalanceOf`). `contracts/fa2_no_tez.py`
  holds the library's transfer, update_operators, balance_of and burn entry points, each with an
  added tez refusal; burn is owner-only.
- `contracts/control.py`: the admin and guardian wallets and the one rule for every change of
  admin, guardian, minter or payout wallet. Used by all three contracts.
- `contracts/minters.py`: the collection's minter list.
- `contracts/payout.py`: the permanent contract that receives every sale and royalty and passes
  it on to the payout wallet.
- `contracts/sale.py`: the replaceable fixed-price minter.
- `contracts/types.py`: shared types.
- The tests are in `tests/`; `run_tests.py` runs them all.

## What must hold

1. Nobody can mint past an edition's cap or after its end time, through any minter, ever.
   Burning never reopens an edition.
2. An artwork's metadata never changes after registration, and the same metadata link is never
   registered twice (unless the first was retired with no copy minted). The contracts' own
   metadata never changes after deployment.
3. Nobody but a token's owner, or an operator the owner chose, can move it. Only the owner can
   burn it.
4. A buyer pays exactly price × quantity, or the purchase fails. No copy is ever minted, by any
   minter, for less than its artwork's floor: the collection checks it and sends the payment on
   to the payout contract, which sends it to the payout wallet, in the same operation. No
   contract ever holds tez.
5. A change of admin, guardian, minter or payout wallet happens only when both wallets voted for
   the same address, or when one wallet voted for it 48 hours ago and the other wallet has no vote
   that counts. Each wallet can only change its own vote. A change both wallets voted for uses up
   both votes, can't be cancelled or replaced, and lapses 7 days later; a vote counts 9 days;
   completing an admin or guardian change voids every older vote and open approval. The guardian can never register, list, price, resume
   sales or touch a token.
6. Rights follow `sender`, never `source`: a contract called by a wallet never acts with its
   rights.
7. One stolen wallet can't take sold tokens, sell below a floor, or redirect money; the other
   wallet can block anything it starts; and it can't stop or redirect a change both wallets
   voted for.
8. The payout contract's `default` refuses no payment, from any payer and of any amount (an
   operation still needs enough gas, like any other).
9. No entry point can be locked by unbounded data or gas.

## Checklist

OpenTezos "Avoiding flaws" (all 14): opentezos.com/smart-contracts/avoiding-flaws, and
docs.tezos.com/developing/security. Also look for:
- type or layout mismatches between the sale's `mint` call or `edition` view and the collection;
- any way for one wallet to make a change count as both wallets' vote, or to complete a stale,
  expired or objected-to one;
- a 0-tez transfer to an implicit account;
- mutez overflow;
- timestamp edge cases (equal to start or end);
- option handling;
- the FA2 standard (TZIP-12) and how indexers read token metadata (the off-chain view precedence);
- anything in SmartPy 0.25's compilation that differs from what the source suggests.

## What to send back

A list of findings. For each one:
- **severity:** critical, high, medium, low or note;
- **file and line;**
- **what goes wrong and how to trigger it**, a SmartPy scenario if you can;
- **the fix.**

Say plainly if you find nothing at a severity level. Do not pad the list.
