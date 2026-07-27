# Halt-channel drill + 2c roll-call — 2026-07-28 (~23:05 UTC 07-27)

## Halt channel: armed and drilled end-to-end (phone link excepted)

Chain drilled with the REAL script, REAL flag file, REAL git push, REAL engine workflow — only the
Telegram API calls were synthetic (I cannot send from the owner's phone):

1. Intruder `/halt` from chat 424242 → **ignored and logged**, no reply, no flag change.
2. Owner-chat `/status` → replied `halt=False flatten=False`.
3. Owner-chat `/halt` → flag `{halt: true}` written AND pushed to harvest-snapshots (commit cc09c84).
4. **Real engine dispatch** (market closed, nothing tradeable): workflow read the flag and exported
   `owner flag: halt=1 flatten=0` — the halt reached a live engine run. The in-loop "OWNER HALT
   ACTIVE" print sits past the market-open guard; that leg is proven by the passivity suite (run E:
   SCHOOL_HALT=1 → no entry placed, harvest continues, 12/12).
5. Owner-chat `/resume` → flag cleared, pushed (commit 57d49fd), `/status` confirms false/false.
   **System left RESUMED** — nothing pauses at the open.

Deliberately NOT drilled: a real `/flatten`. It would close every live paper position (46 tracked
legs) and reset the book — that is an owner decision, not a drill step. Flatten is proven to the
final gate: flag write + workflow export path identical to halt, and the engine-side sentinel logic
is covered in the suites. Remaining untested link in the whole channel: one real `/status` from the
owner's phone.

## 2c roll-call: notebook now matches broker truth

Read-only Alpaca roll-call of every OPEN record (VPS, 2026-07-27 ~23:10 UTC):

| | before | after |
|---|---|---|
| OPEN records | 101 | **46** |
| broker option positions | 49 | 49 (46 tracked + 3 orphans) |

The 55 phantom legs, classified by their actual order states, never guessed:
- **46 never filled** (36 cancelled, 6 expired, 4 unresolvable order ids on adjusted symbols) →
  `STALE_CANCELLED_RECONCILED`. No position ever existed; these were silently blocking
  one-per-underlying re-entries.
- **9 filled but position since closed at the broker** without the notebook recording the exit
  (SLV, TRIP, UPST, TLT, BMNR, NN, ARKK, TSLL, IGV) → `CLOSED_RECONCILED_UNTRACKED_EXIT`. Their
  realized returns are NOT fabricated here; the fill ledger holds the exit fills where captured.
- **3 orphans remain** (LQD, PFE, STLA calls): broker positions with no record — left for the
  daily reconcile marker / engine adoption; not manufactured into records by hand.

No trade logic touched: status strings and notes only; every engine filter reads `status == "OPEN"`.
