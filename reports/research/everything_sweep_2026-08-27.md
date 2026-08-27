# EVERYTHING SWEEP - 2026-08-27 (hourly precision, permanent library)

28440 strategy configurations scored on 169685 real trades with stored
hourly paths. Entry at ask; stops TOUCH (bar-low) vs CLOSE (hourly close) both tested.
**NULL BAR 3.00** (best t of the same search on shuffled outcomes) vs real
best 11.05. ROBUST = clears null bar + both halves + train + 2026 test.
ROBUST: 2027 of 28440

| strategy | exit | day-mean | vs-pool | t-pool | plateau | halves | train/test | n |
|---|---|---|---|---|---|---|---|---|
| FOLLOW/calls/deepbear+dteL | CLOSE stop-70 trig80 give30% | +67.9% | +51.5 | +7.43 | +53.4 | +46/+89 | +53.4/+81.9 | 746 |
| FOLLOW/calls/deepbear+dteL | TOUCH stop-70 trig80 give30% | +67.5% | +52.1 | +7.50 | +52.3 | +46/+89 | +52.9/+81.9 | 746 |
| FADE/calls/deepbear+dteL | CLOSE stop-70 trig80 give30% | +66.5% | +50.7 | +6.03 | +51.5 | +44/+89 | +52.9/+83.4 | 564 |
| FADE/calls/deepbear+dteL | TOUCH stop-70 trig80 give30% | +66.1% | +51.1 | +6.04 | +51.0 | +43/+89 | +52.2/+83.4 | 564 |
| FADE/both/deepbear+dteL | CLOSE stop-70 trig80 give30% | +65.3% | +49.0 | +5.81 | +50.7 | +40/+90 | +52.5/+83.4 | 569 |
| FADE/both/deepbear+dteL | TOUCH stop-70 trig80 give30% | +64.8% | +49.5 | +5.86 | +50.2 | +39/+90 | +51.8/+83.4 | 569 |
| FOLLOW/calls/bear+dteL | CLOSE stop-70 trig80 give30% | +59.5% | +43.0 | +6.76 | +46.8 | +37/+81 | +42.5/+79.6 | 1015 |
| FADE/calls/bear+dteL | CLOSE stop-70 trig80 give30% | +61.0% | +46.5 | +5.72 | +46.7 | +36/+86 | +44.8/+93.2 | 668 |
| FADE/calls/bear+dteL | TOUCH stop-70 trig80 give30% | +60.6% | +47.1 | +5.78 | +46.2 | +35/+86 | +44.2/+93.2 | 668 |
| FOLLOW/calls/bear+dteL | TOUCH stop-70 trig80 give30% | +59.0% | +43.6 | +6.84 | +45.9 | +36/+81 | +41.6/+79.6 | 1015 |
| FOLLOW/calls/deepbear+dteL | CLOSE stop-60 trig80 give30% | +59.8% | +44.5 | +6.12 | +44.9 | +37/+82 | +45.6/+73.8 | 746 |
| FADE/calls/deepbear+dteL | CLOSE stop-60 trig80 give30% | +57.4% | +42.4 | +4.80 | +44.8 | +35/+80 | +45.4/+76.6 | 564 |
| FADE/both/deepbear+dteL | CLOSE stop-60 trig80 give30% | +56.4% | +41.0 | +4.69 | +44.2 | +30/+81 | +45.1/+76.6 | 569 |
| FOLLOW/calls/deepbear+dteL | CLOSE stop-70 trig80 give10% | +50.4% | +34.7 | +6.67 | +42.8 | +34/+66 | +41.4/+54.8 | 746 |
| FOLLOW/calls/deepbear+dteL | CLOSE stop-70 trig80 give20% | +61.5% | +45.7 | +6.70 | +42.8 | +39/+83 | +46.3/+76.2 | 746 |
| FADE/both/bear+dteL | CLOSE stop-70 trig80 give30% | +54.8% | +38.9 | +4.56 | +42.7 | +38/+71 | +44.8/+86.5 | 744 |
| FOLLOW/calls/deepbear+dteL | TOUCH stop-60 trig80 give30% | +58.7% | +44.9 | +6.18 | +42.5 | +35/+82 | +43.9/+73.8 | 746 |
| FADE/both/bear+dteL | TOUCH stop-70 trig80 give30% | +54.4% | +39.8 | +4.65 | +42.3 | +38/+71 | +44.3/+86.5 | 744 |
| FADE/calls/deepbear+dteL | TOUCH stop-60 trig80 give30% | +56.9% | +43.4 | +4.93 | +42.2 | +34/+80 | +44.6/+76.6 | 564 |
| FADE/calls/deepbear+dteL | CLOSE stop-70 trig80 give10% | +51.3% | +35.9 | +5.45 | +42.0 | +33/+70 | +40.9/+60.3 | 564 |
| FADE/calls/deepbear+dteL | CLOSE stop-70 trig80 give20% | +60.9% | +45.5 | +5.55 | +42.0 | +38/+84 | +45.4/+78.8 | 564 |
| FADE/both/deepbear+dteL | TOUCH stop-60 trig80 give30% | +55.9% | +42.1 | +4.84 | +41.6 | +30/+81 | +44.3/+76.6 | 569 |
| FOLLOW/calls/deepbear+dteL | TOUCH stop-70 trig80 give10% | +50.0% | +35.3 | +6.78 | +41.6 | +33/+66 | +40.9/+54.8 | 746 |
| FOLLOW/calls/deepbear+dteL | TOUCH stop-70 trig80 give20% | +61.2% | +46.3 | +6.77 | +41.6 | +38/+83 | +45.7/+76.2 | 746 |
| FADE/both/deepbear+dteL | CLOSE stop-70 trig80 give10% | +50.5% | +34.9 | +5.34 | +41.5 | +29/+71 | +40.6/+60.3 | 569 |

## Top raw (luck-prone, shown for completeness)

| strategy | exit | day-mean | t |
|---|---|---|---|
| FOLLOW/both/all+loswp | CLOSE stop-40 trig30 give10% | +6.3% | +11.05 |
| FOLLOW/calls/all+dteL | CLOSE stop-50 trig80 give30% | +20.9% | +10.90 |
| FOLLOW/calls/all+dteL | CLOSE stop-60 trig80 give30% | +22.1% | +10.82 |
| FOLLOW/both/all | CLOSE stop-40 trig30 give10% | +6.4% | +10.75 |
| FOLLOW/calls/all+dteL | CLOSE stop-70 trig80 give30% | +22.6% | +10.70 |
| FOLLOW/calls/all+dteL | TOUCH stop-50 trig80 give30% | +20.3% | +10.69 |
| FOLLOW/calls/all+dteL | TOUCH stop-60 trig80 give30% | +21.6% | +10.60 |
| FOLLOW/calls/all+dteL | CLOSE stop-40 trig80 give30% | +19.0% | +10.56 |
