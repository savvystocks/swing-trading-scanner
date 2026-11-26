"""Known-answer cases for research/prop_rules.py, copied unchanged from
swing_research/funded_2026-11/prop_sim/test_prop_rules.py (12 cases), plus a pin that the module is the
unchanged copy of swing_research/funded_2026-11/prop_sim/prop_rules.py (sha256 below, LF line endings)."""
import hashlib
import os

import fxtest
from prop_rules import BREACH_DAILY, BREACH_TOTAL, OPEN, PASS, run_challenge, run_phase, utc

PROP_RULES_SHA256 = "24636a5c37176246dd8880a71d10242bedd8ef9c1a44e32999889441cbcaa8a6"


def test_prop_rules_is_the_unchanged_copy():
    raw = open(os.path.join(fxtest.ROOT, "research", "prop_rules.py"), "rb").read().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == PROP_RULES_SHA256


K = 100_000.0


def m(t, eq, bal=None, traded=True, flat=True):
    return (t, eq, eq if bal is None else bal, traded, flat)


def case_steady_pass():
    marks = [m(utc(2025, 1, 6, 12), K, traded=False)] + [m(utc(2025, 1, 6 + i, 12), K * (1 + 0.025 * i)) for i in range(1, 5)]
    return run_phase(marks, 0, 0.10), (PASS, 4)


def case_target_before_min_days():
    marks = [m(utc(2025, 1, 6, 12), K, traded=False), m(utc(2025, 1, 7, 12), K * 1.11), m(utc(2025, 1, 8, 12), K * 1.11),
             m(utc(2025, 1, 9, 12), K * 1.11, traded=False), m(utc(2025, 1, 10, 12), K * 1.11), m(utc(2025, 1, 13, 12), K * 1.11)]
    return run_phase(marks, 0, 0.10), (PASS, 5)


def case_intraday_daily_breach():
    marks = [m(utc(2025, 1, 6, 9), K, traded=False), m(utc(2025, 1, 6, 13), K * 0.949, bal=K, flat=False),
             m(utc(2025, 1, 6, 20), K * 1.01)]
    return run_phase(marks, 0, 0.10), (BREACH_DAILY, 1)


def case_daily_exactly_at_limit_is_allowed():
    marks = [m(utc(2025, 1, 6, 9), K, traded=False), m(utc(2025, 1, 6, 13), K * 0.95, bal=K, flat=False),
             m(utc(2025, 1, 6, 20), K * 0.99)]
    return run_phase(marks, 0, 0.10), (OPEN, 2)


def case_slow_bleed_total_breach():
    marks = [m(utc(2025, 1, 6, 12), K, traded=False)]
    eq = K
    for i in range(1, 10):
        eq -= 0.012 * K
        marks.append(m(utc(2025, 1, 6 + i, 12), eq))
    return run_phase(marks, 0, 0.10), (BREACH_TOTAL, 9)


def case_reference_is_day_start_balance():
    ok = [m(utc(2025, 1, 6, 12), K, traded=False), m(utc(2025, 1, 6, 15), K * 1.04),
          m(utc(2025, 1, 7, 12), K * 0.995, bal=K * 1.04, flat=False), m(utc(2025, 1, 7, 20), K * 1.0)]
    bad = ok[:2] + [m(utc(2025, 1, 7, 12), K * 0.989, bal=K * 1.04, flat=False)]
    return (run_phase(ok, 0, 0.10), run_phase(bad, 0, 0.10)), ((OPEN, 3), (BREACH_DAILY, 2))


def case_open_loss_carried_over_midnight():
    marks = [m(utc(2025, 1, 6, 12), K, traded=False), m(utc(2025, 1, 6, 20), K * 0.97, bal=K, flat=False),
             m(utc(2025, 1, 7, 2), K * 0.94, bal=K, flat=False)]
    return run_phase(marks, 0, 0.10), (BREACH_DAILY, 2)


def case_closed_loss_resets_at_midnight():
    marks = [m(utc(2025, 1, 6, 12), K, traded=False), m(utc(2025, 1, 6, 20), K * 0.97),
             m(utc(2025, 1, 7, 2), K * 0.94)]
    return run_phase(marks, 0, 0.10), (OPEN, 2)


def case_reset_follows_prague_clock_in_summer():
    winter = [m(utc(2025, 1, 6, 12), K, traded=False), m(utc(2025, 1, 6, 21, 30), K * 0.97), m(utc(2025, 1, 6, 22, 30), K * 0.94)]
    summer = [m(utc(2025, 7, 7, 12), K, traded=False), m(utc(2025, 7, 7, 21, 30), K * 0.97), m(utc(2025, 7, 7, 22, 30), K * 0.94)]
    return (run_phase(winter, 0, 0.10), run_phase(summer, 0, 0.10)), ((BREACH_DAILY, 2), (OPEN, 2))


def case_two_phases_rebased():
    marks = [m(utc(2025, 1, 6, 12), K, traded=False)]
    eq = K
    for i in range(1, 5):
        eq *= 1.025
        marks.append(m(utc(2025, 1, 6 + i, 12), eq))
    for i in range(5, 9):
        eq *= 1.013
        marks.append(m(utc(2025, 1, 8 + i, 12), eq))
    return run_challenge(marks), (PASS, 8, 2)


def case_phase_two_breach_reported():
    marks = [m(utc(2025, 1, 6, 12), K, traded=False)]
    eq = K
    for i in range(1, 5):
        eq *= 1.025
        marks.append(m(utc(2025, 1, 6 + i, 12), eq))
    marks.append(m(utc(2025, 1, 13, 12), eq * 0.94))
    return run_challenge(marks), (BREACH_DAILY, 5, 2)


def case_must_start_flat():
    try:
        run_phase([m(utc(2025, 1, 6, 12), K, flat=False), m(utc(2025, 1, 7, 12), K)], 0, 0.10)
    except ValueError:
        return "raised", "raised"
    return "no error", "raised"


if __name__ == "__main__":
    fxtest.run(globals())
