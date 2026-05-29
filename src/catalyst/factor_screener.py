FACTOR_DEFINITIONS = [
    {
        "id": "hyperscaler_capex",
        "name": "AI data center / hyperscaler capex exposure",
        "type": "theme",
        "industry_keywords": ["semiconductor", "data center", "communications equipment", "internet infrastructure", "computer hardware", "computer storage"],
        "description_keywords": ["data center", "hyperscaler", "ai infrastructure", "cloud infrastructure", "ai cloud", "ai compute", "ai workload", "datacenter", "compute capacity"],
    },
    {
        "id": "memory_storage",
        "name": "AI memory/storage (HBM/NAND/HDD)",
        "type": "theme",
        "industry_keywords": ["semiconductor", "computer storage", "computer hardware"],
        "description_keywords": ["nand flash", "hbm", "high bandwidth memory", "dram", "ssd", "hard disk", "hdd", "storage solutions", "memory chip", "flash memory", "data storage", "solid state"],
    },
    {
        "id": "optical_photonic",
        "name": "Optical/photonic interconnect",
        "type": "theme",
        "industry_keywords": ["communications equipment", "electronic equipment", "semiconductor"],
        "description_keywords": ["optical", "photonic", "transceiver", "interconnect", "fiber optic", "laser", "wavelength", "silicon photonics", "coherent optical", "optical networking"],
    },
    {
        "id": "data_center_power",
        "name": "Data center power generation",
        "type": "theme",
        "industry_keywords": ["industrial machinery", "specialty industrial", "electrical equipment", "diversified industrials", "power equipment"],
        "description_keywords": ["power generation", "gas turbine", "diesel generator", "backup power", "ups system", "reciprocating engine", "natural gas power", "gensets", "power plant"],
    },
    {
        "id": "wafer_fab_equipment",
        "name": "Wafer fab equipment (WFE)",
        "type": "theme",
        "industry_keywords": ["semiconductor equipment", "semiconductors"],
        "description_keywords": ["wafer fab", "photolithography", "etch", "deposition", "semiconductor equipment", "process equipment", "metrology", "ion implantation", "cmp", "wafer processing"],
    },
    {
        "id": "liquid_cooling",
        "name": "Liquid cooling / thermal management",
        "type": "theme",
        "industry_keywords": ["industrial machinery", "specialty industrial", "building products", "electrical equipment"],
        "description_keywords": ["liquid cooling", "thermal management", "data center cooling", "immersion cooling", "rack cooling", "heat exchanger", "chiller", "precision cooling"],
    },
    {
        "id": "foundry_packaging",
        "name": "Foundry / advanced packaging",
        "type": "theme",
        "industry_keywords": ["semiconductor equipment", "semiconductors"],
        "description_keywords": ["foundry", "advanced packaging", "chip packaging", "fabrication services", "wafer foundry", "chiplet", "interposer", "2.5d", "3d packaging", "system in package"],
    },
    {
        "id": "ai_accelerator",
        "name": "AI accelerator / GPU / TPU silicon",
        "type": "theme",
        "industry_keywords": ["semiconductor"],
        "description_keywords": ["ai accelerator", "gpu", "tensor processing", "npu", "ai chip", "ai silicon", "neural processor", "machine learning chip", "deep learning", "inference chip"],
    },
    {
        "id": "lithium_battery",
        "name": "Lithium / battery / BESS",
        "type": "theme",
        "industry_keywords": ["specialty chemicals", "metals & mining", "industrial", "battery", "renewable energy"],
        "description_keywords": ["lithium", "battery materials", "ev battery", "energy storage system", "bess", "battery cell", "lithium ion", "battery production"],
    },
    {
        "id": "streaming_media_restructure",
        "name": "Streaming / media restructure",
        "type": "theme",
        "industry_keywords": ["media", "entertainment"],
        "description_keywords": ["streaming service", "content studio", "media library", "subscription video", "svod", "streaming platform"],
    },
    {
        "id": "spectrum_assets",
        "name": "Spectrum / 5G assets",
        "type": "theme",
        "industry_keywords": ["telecom", "wireless"],
        "description_keywords": ["wireless spectrum", "5g spectrum", "millimeter wave", "spectrum auction", "spectrum holder", "spectrum license"],
    },
    {
        "id": "advanced_node_transition",
        "name": "Advanced transistor node (GAA/2nm)",
        "type": "theme",
        "industry_keywords": ["semiconductor equipment", "semiconductors"],
        "description_keywords": ["gate-all-around", "gaa transistor", "finfet", "advanced node", "2nm", "3nm process", "transistor architecture"],
    },
    {
        "id": "earnings_beat_raised_guidance",
        "name": "Earnings beat + revision spike",
        "type": "event",
        "dynamic_signals": ["earnings_bmo_with_beat_streak", "revision_spike"],
    },
    {
        "id": "order_backlog",
        "name": "Order backlog surge",
        "type": "event",
        "dynamic_signals": ["backlog_surge"],
    },
    {
        "id": "spinoff_separation",
        "name": "Spinoff / separation",
        "type": "event",
        "dynamic_signals": ["spinoff_catalyst", "merger_cash_buyout", "merger", "asset_sale"],
    },
    {
        "id": "nvidia_strategic",
        "name": "NVIDIA strategic investment / partnership",
        "type": "event",
        "news_keywords": ["nvidia invests", "nvidia stake", "nvidia partnership", "strategic partnership with nvidia", "nvidia equity", "from nvidia"],
    },
    {
        "id": "capital_return",
        "name": "Capital return (buyback / dividend)",
        "type": "event",
        "dynamic_signals": ["buyback"],
        "news_keywords": ["share repurchase", "buyback program", "dividend increase", "raises dividend"],
    },
    {
        "id": "sp500_inclusion_proximity",
        "name": "S&P 500 inclusion proximity ($10B-$25B mcap)",
        "type": "numeric",
        "mcap_min": 10_000_000_000,
        "mcap_max": 25_000_000_000,
    },
    {
        "id": "short_squeeze_turnaround",
        "name": "Short squeeze setup (SI >15%)",
        "type": "numeric",
        "short_pct_min": 15,
    },
]


def _match_industry(industry, keywords):
    if not industry or not keywords:
        return False
    industry_low = industry.lower()
    return any(kw in industry_low for kw in keywords)


def _count_description_matches(description, keywords):
    if not description or not keywords:
        return 0
    desc_low = description.lower()
    return sum(1 for kw in keywords if kw in desc_low)


def _match_news(news_headlines, keywords):
    if not news_headlines or not keywords:
        return False
    for h in news_headlines:
        title = (h.get("title") or "").lower()
        for kw in keywords:
            if kw in title:
                return True
    return False


def _has_dynamic_signal(catalysts, signal_keys):
    if not catalysts or not signal_keys:
        return False
    catalyst_keys = {c.get("key") for c in catalysts if isinstance(c, dict)}
    return any(k in catalyst_keys for k in signal_keys)


def compute_factor_matches(ticker_data):
    industry = ticker_data.get("industry", "") or ""
    description = ticker_data.get("description", "") or ""
    sector = ticker_data.get("sector", "") or ""
    catalysts = ticker_data.get("catalysts") or []
    news = ticker_data.get("news") or {}
    news_headlines = news.get("headlines") if isinstance(news, dict) else []
    market_cap = ticker_data.get("market_cap") or 0
    short_pct = ticker_data.get("short_pct_float") or 0

    matched = []
    sector_industry_blob = f"{industry} {sector}"

    for f in FACTOR_DEFINITIONS:
        evidence = []
        ftype = f.get("type", "theme")

        if ftype == "theme":
            ind_match = _match_industry(sector_industry_blob, f["industry_keywords"])
            desc_count = _count_description_matches(description, f["description_keywords"])
            if ind_match and desc_count >= 2:
                evidence.append(f"industry+{desc_count} desc kws")

        elif ftype == "event":
            if "dynamic_signals" in f and _has_dynamic_signal(catalysts, f["dynamic_signals"]):
                evidence.append("signal fired")
            if "news_keywords" in f and _match_news(news_headlines, f["news_keywords"]):
                evidence.append("named in news")

        elif ftype == "numeric":
            if "mcap_min" in f and "mcap_max" in f:
                if market_cap and f["mcap_min"] <= market_cap <= f["mcap_max"]:
                    evidence.append(f"${market_cap/1e9:.1f}B in range")
            if "short_pct_min" in f and short_pct >= f["short_pct_min"]:
                evidence.append(f"SI {short_pct:.0f}%")

        if evidence:
            matched.append({
                "factor_id": f["id"],
                "factor_name": f["name"],
                "type": ftype,
                "evidence": evidence,
            })

    theme_count = sum(1 for m in matched if m["type"] == "theme")
    event_count = sum(1 for m in matched if m["type"] == "event")
    numeric_count = sum(1 for m in matched if m["type"] == "numeric")

    return {
        "factor_count": len(matched),
        "theme_count": theme_count,
        "event_count": event_count,
        "numeric_count": numeric_count,
        "matched_factors": matched,
        "factor_ids": [m["factor_id"] for m in matched],
    }


def screen_lower_caps(scored_results, mcap_max=50_000_000_000, mcap_min=300_000_000,
                      min_factor_count=2, require_theme_match=True):
    out = []
    for s in scored_results:
        mcap = s.get("market_cap") or 0
        if mcap < mcap_min or mcap > mcap_max:
            continue
        result = compute_factor_matches(s)
        if result["factor_count"] < min_factor_count:
            continue
        if require_theme_match and result["theme_count"] < 1:
            continue
        out.append({
            "ticker": s.get("ticker"),
            "name": s.get("name") or s.get("company") or "",
            "sector": s.get("sector"),
            "industry": s.get("industry"),
            "market_cap": mcap,
            "price": s.get("price"),
            "live_spot": s.get("live_spot"),
            "live_change_pct": s.get("live_change_pct"),
            "score": s.get("score"),
            "bucket": s.get("bucket"),
            "deep_research": s.get("deep_research"),
            "catalysts": s.get("catalysts") or [],
            "factor_count": result["factor_count"],
            "theme_count": result["theme_count"],
            "event_count": result["event_count"],
            "matched_factors": result["matched_factors"],
            "eodhd_ticker": s.get("eodhd_ticker"),
        })
    out.sort(key=lambda x: (x["theme_count"], x["factor_count"], x.get("score") or 0), reverse=True)
    return out
