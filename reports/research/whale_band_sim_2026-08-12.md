# Whale-band replay - 2026-08-12 00:40 UTC (owner question: why only 50-400k?)

Method: stored harvest cohort (VPS harvest.db, read-only), candidates joined to triple-barrier
labels, fade shape (20d trend AND day-SPY both oppose the bet side), spread <= 2%, split by
aggregated flow premium tier. IDENTICAL label policy across tiers - the comparison is
relative; absolute levels differ from the fade book's live exit policy (trail 50/20).
All stats day-clustered per standing rule.

| tier | n | days | pooled | day-mean | t | halves |
|---|---|---|---|---|---|---|
| in-band 50-400k | 602 | 30 | +1.21% | -0.47% | -0.07 | +0.8 / -1.7 |
| whale 400k-1M | 47 | 24 | +2.79% | +3.37% | +0.34 | +13.7 / -6.9 |
| whale 1M-3M | 8 | 7 | -5.47% | -5.09% | -0.39 | +11.1 / -17.3 |
| mega >3M | 0 | - | - | - | - | - |

Verdict (pre-agreed rule: not clearly toxic -> probe goes live):
- 400k-1M: NOT toxic - outscores in-band on this yardstick, but the second half is
  sign-flipped (+13.7 -> -6.9): regime-sensitive, unproven. FADE_WHALE probe slot added
  (spec v1.7.1): fade-shaped 400k-1M prints from a side-pool; the live fade book's
  candidate list stays byte-identical. 5 fills/day cap, $1k, book=PROBE.
- 1M-3M: negative and thin - excluded.
- >3M: nothing stored - the funnel has never scored one; no claim possible.

Context this extends: the 2026-08-05 replay measured the whale band crowded at 13.6% wins
BEFORE the fade shape existed; this run asks the narrower question (fade-SHAPED whales) and
gets a different, better answer on a small sample. The probe settles it with real fills.
