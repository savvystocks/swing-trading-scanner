from datetime import datetime, timedelta, date


FOMC_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 16),
]


def _days_until(target_date, from_date=None):
    if from_date is None:
        from_date = datetime.utcnow().date()
    return (target_date - from_date).days


def next_fomc_days(from_date=None):
    if from_date is None:
        from_date = datetime.utcnow().date()
    upcoming = [d for d in FOMC_2026 if d >= from_date]
    if not upcoming:
        return None
    return _days_until(upcoming[0], from_date)


def next_cpi_days(from_date=None):
    if from_date is None:
        from_date = datetime.utcnow().date()
    year = from_date.year
    month = from_date.month
    next_release = date(year, month, 12)
    if from_date > next_release:
        if month == 12:
            next_release = date(year + 1, 1, 12)
        else:
            next_release = date(year, month + 1, 12)
    return _days_until(next_release, from_date)


def next_nfp_days(from_date=None):
    if from_date is None:
        from_date = datetime.utcnow().date()
    year = from_date.year
    month = from_date.month
    first_of_month = date(year, month, 1)
    days_to_friday = (4 - first_of_month.weekday()) % 7
    first_friday = first_of_month + timedelta(days=days_to_friday)
    if from_date > first_friday:
        if month == 12:
            next_first = date(year + 1, 1, 1)
        else:
            next_first = date(year, month + 1, 1)
        dtf = (4 - next_first.weekday()) % 7
        first_friday = next_first + timedelta(days=dtf)
    return _days_until(first_friday, from_date)


def next_opex_days(from_date=None):
    if from_date is None:
        from_date = datetime.utcnow().date()
    year = from_date.year
    month = from_date.month
    first_of_month = date(year, month, 1)
    days_to_friday = (4 - first_of_month.weekday()) % 7
    first_friday = first_of_month + timedelta(days=days_to_friday)
    third_friday = first_friday + timedelta(days=14)
    if from_date > third_friday:
        if month == 12:
            next_month_first = date(year + 1, 1, 1)
        else:
            next_month_first = date(year, month + 1, 1)
        dtf = (4 - next_month_first.weekday()) % 7
        next_first_fri = next_month_first + timedelta(days=dtf)
        third_friday = next_first_fri + timedelta(days=14)
    return _days_until(third_friday, from_date)


def day_of_week_signal(from_date=None):
    if from_date is None:
        from_date = datetime.utcnow().date()
    dow = from_date.weekday()
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_name = names[dow]

    if dow == 0:
        note = "Monday - typical gap reversion candidate, 75% of gaps fill in week"
    elif dow == 4:
        note = "Friday - thin afternoon liquidity, watch for after-hours news dumps"
    elif dow == 1:
        note = "Tuesday - often the highest-volume trend day of week"
    elif dow == 2:
        note = "Wednesday - mid-week, often the FOMC announcement day"
    elif dow == 3:
        note = "Thursday - earnings AMC peak day, jobless claims release"
    else:
        note = "Weekend - market closed"

    return {
        "dow": dow_name,
        "dow_idx": dow,
        "note": note,
    }


def compute_calendar_signals(from_date=None):
    fomc = next_fomc_days(from_date)
    cpi = next_cpi_days(from_date)
    nfp = next_nfp_days(from_date)
    opex = next_opex_days(from_date)
    dow_info = day_of_week_signal(from_date)

    risks = []
    if fomc is not None and fomc <= 5:
        risks.append(f"FOMC in {fomc}d")
    if cpi is not None and cpi <= 3:
        risks.append(f"CPI in {cpi}d")
    if nfp is not None and nfp <= 2:
        risks.append(f"NFP in {nfp}d")
    if opex is not None and opex <= 3:
        risks.append(f"OPEX in {opex}d (dealer hedging)")

    return {
        "days_to_next_fomc": fomc,
        "days_to_next_cpi": cpi,
        "days_to_next_nfp": nfp,
        "days_to_next_opex": opex,
        "dow_info": dow_info,
        "near_term_risks": risks,
    }


def enrich_macro_with_calendar(macro, from_date=None):
    if macro is None:
        macro = {}
    cal = compute_calendar_signals(from_date)
    macro.update({
        "days_to_next_fomc": cal["days_to_next_fomc"],
        "days_to_next_cpi": cal["days_to_next_cpi"],
        "days_to_next_nfp": cal["days_to_next_nfp"],
        "days_to_next_opex": cal["days_to_next_opex"],
        "dow_info": cal["dow_info"],
        "near_term_calendar_risks": cal["near_term_risks"],
    })
    return macro
