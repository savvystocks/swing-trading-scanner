# MEGA SWEEP - 2026-08-23

Cohort 326077 real triggers. Entry AT THE ASK, outcomes ON THE BID, live exit replay.
59292 configurations scored across shape x regime x threshold x band x spread x side
x delta x stop x trail-trigger x give.

**NULL BAR: 2.24** - the best t the SAME search finds on scrambled data.
Real best t: 5.17. A config only counts as ROBUST if its t clears the null bar
AND it is positive in both halves AND in train(<2026) AND in test(2026).

ROBUST configs: 4819 of 59292

## Top ROBUST configurations (ranked by PLATEAU - neighbour-safe, not lone spikes)

| shape/regime | entry filters | exits | day-mean | t | plateau | halves | train/test | n |
|---|---|---|---|---|---|---|---|---|
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig80 give20% | +67.8% | +3.43 | +67.8 | +11/+122 | +49.1/+87.3 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig80 give30% | +66.8% | +3.39 | +66.8 | +12/+120 | +49.3/+87.1 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-60 trig80 give20% | +66.6% | +3.30 | +66.6 | +9/+124 | +48.3/+87.3 | 680 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-50 trig80 give20% | +65.8% | +3.46 | +65.8 | +12/+117 | +48.2/+81.9 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-60 trig80 give30% | +65.6% | +3.27 | +65.6 | +10/+122 | +48.5/+87.1 | 680 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-50 trig80 give20% | +64.6% | +3.33 | +64.6 | +10/+119 | +47.4/+81.9 | 680 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-50 trig80 give30% | +64.5% | +3.40 | +64.5 | +11/+115 | +47.3/+82.1 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-50 trig80 give30% | +63.2% | +3.27 | +63.2 | +9/+117 | +46.5/+82.1 | 680 |
| FADE/bear(±3.0) | 50-400k spr3.0 calls lo<0.30 | stop-50 trig80 give20% | +62.2% | +3.21 | +62.2 | +23/+99 | +55.7/+103.7 | 335 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig30 give20% | +62.1% | +3.20 | +62.1 | +9/+113 | +43.9/+67.1 | 685 |
| FADE/bear(±3.0) | 50-400k spr3.0 calls lo<0.30 | stop-60 trig80 give20% | +61.9% | +3.09 | +61.9 | +21/+101 | +56.2/+106.5 | 335 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-40 trig80 give20% | +61.4% | +3.33 | +61.4 | +12/+109 | +47.5/+83.1 | 685 |
| FADE/bear(±3.0) | 50-400k spr3.0 calls lo<0.30 | stop-60 trig80 give30% | +61.1% | +3.06 | +61.1 | +20/+100 | +54.2/+108.7 | 335 |
| FADE/bear(±3.0) | 50-400k spr3.0 both lo<0.30 | stop-50 trig80 give20% | +61.0% | +3.21 | +61.0 | +23/+99 | +55.3/+103.7 | 337 |
| FADE/bear(±3.0) | 50-400k spr3.0 calls lo<0.30 | stop-50 trig80 give30% | +60.9% | +3.16 | +60.9 | +21/+99 | +52.7/+105.9 | 335 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig30 give30% | +60.8% | +3.15 | +60.8 | +9/+110 | +43.9/+66.4 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-60 trig30 give20% | +60.8% | +3.07 | +60.8 | +7/+114 | +43.0/+67.1 | 680 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig50 give20% | +63.3% | +3.24 | +60.8 | +10/+114 | +47.0/+69.1 | 685 |
| FADE/bear(±3.0) | 50-400k spr3.0 both lo<0.30 | stop-60 trig80 give20% | +60.7% | +3.10 | +60.7 | +21/+101 | +55.8/+106.5 | 337 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-40 trig80 give30% | +60.2% | +3.28 | +60.2 | +11/+107 | +46.5/+83.7 | 685 |

## Highest raw return (ignoring robustness - shown because it was asked for; these are the cells most likely to be luck)

| shape/regime | entry filters | exits | day-mean | t | plateau | halves | train/test | n |
|---|---|---|---|---|---|---|---|---|
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig80 give20% | +67.8% | +3.43 | +67.8 | +11/+122 | +49.1/+87.3 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig80 give30% | +66.8% | +3.39 | +66.8 | +12/+120 | +49.3/+87.1 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-60 trig80 give20% | +66.6% | +3.30 | +66.6 | +9/+124 | +48.3/+87.3 | 680 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-50 trig80 give20% | +65.8% | +3.46 | +65.8 | +12/+117 | +48.2/+81.9 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-60 trig80 give30% | +65.6% | +3.27 | +65.6 | +10/+122 | +48.5/+87.1 | 680 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-50 trig80 give20% | +64.6% | +3.33 | +64.6 | +10/+119 | +47.4/+81.9 | 680 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-50 trig80 give30% | +64.5% | +3.40 | +64.5 | +11/+115 | +47.3/+82.1 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 both lo<0.30 | stop-60 trig50 give20% | +63.3% | +3.24 | +60.8 | +10/+114 | +47.0/+69.1 | 685 |
| FADE/bear(±3.0) | 50-1000k spr3.0 calls lo<0.30 | stop-50 trig80 give30% | +63.2% | +3.27 | +63.2 | +9/+117 | +46.5/+82.1 | 680 |
| CONSENSUS/mild(±1.0) | 50-1000k spr3.0 calls lo<0.30 | stop-40 trig80 give20% | +62.8% | +2.01 | +62.8 | +27/+97 | +36.2/+130.7 | 425 |

## Regime table rebased (executable, spread<=2.0, band 50-400k)

| shape | BEAR | MILD | BULL |
|---|---|---|---|
| FADE | +22.7% t+2.78 (62d, n=1045) | -8.9% t-2.61 (185d, n=3619) | -20.5% t-7.69 (239d, n=6935) |
| CONSENSUS | -3.8% t-0.40 (62d, n=991) | -17.4% t-4.63 (184d, n=3139) | -0.8% t-0.35 (234d, n=5813) |
| FOLLOW | +6.3% t+1.48 (63d, n=2400) | -12.6% t-5.75 (188d, n=9766) | -11.3% t-8.92 (241d, n=15380) |
