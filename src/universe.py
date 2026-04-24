import io
import json
import pathlib
import re
import requests
import pandas as pd

UNIVERSE_DIR = pathlib.Path(__file__).parent.parent / "data" / "universe"
UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _fetch_html(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_sp500():
    html = _fetch_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    tables = pd.read_html(io.StringIO(html))
    df = tables[0]
    return [{"ticker": f"{s.replace('.', '-')}.US", "name": n, "sector": sec, "index": "SP500"}
            for s, n, sec in zip(df["Symbol"], df["Security"], df["GICS Sector"])]


def fetch_sp400():
    html = _fetch_html("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")
    tables = pd.read_html(io.StringIO(html))
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        if "Symbol" in cols and ("Security" in cols or "Company" in cols):
            sym_col = "Symbol"
            name_col = "Security" if "Security" in cols else "Company"
            sector_col = next((c for c in cols if "GICS Sector" in c or c == "Sector"), None)
            rows = []
            for _, row in t.iterrows():
                s = row.get(sym_col)
                if pd.isna(s):
                    continue
                s = str(s).strip().replace(".", "-")
                rows.append({
                    "ticker": f"{s}.US",
                    "name": str(row.get(name_col, "")),
                    "sector": str(row.get(sector_col, "")) if sector_col else "",
                    "index": "SP400",
                })
            if rows:
                return rows
    return []


def fetch_russell2000():
    url = "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    text = r.text
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("Ticker,") or line.startswith('"Ticker"'):
            start = i
            break
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    rows = []
    for _, row in df.iterrows():
        t = str(row.get("Ticker", "")).strip()
        asset_class = str(row.get("Asset Class", "")).strip()
        if not t or t == "nan" or asset_class != "Equity":
            continue
        if not re.match(r"^[A-Z.\-]+$", t):
            continue
        rows.append({
            "ticker": f"{t.replace('.', '-')}.US",
            "name": str(row.get("Name", "")),
            "sector": str(row.get("Sector", "")),
            "index": "RUSSELL2000",
        })
    return rows


def _fetch_ftse_wiki(url, index_label):
    html = _fetch_html(url)
    tables = pd.read_html(io.StringIO(html))
    for t in tables:
        cols = [str(c) for c in t.columns]
        ticker_col = next((c for c in cols if c in ("EPIC", "Ticker", "Symbol")), None)
        if not ticker_col:
            continue
        name_col = next((c for c in cols if "Company" in c or "Constituent" in c), cols[0])
        sector_col = next((c for c in cols if "Sector" in c or "Industry" in c), None)
        rows = []
        for _, row in t.iterrows():
            s = row[ticker_col]
            if pd.isna(s):
                continue
            s = str(s).strip().replace(".", "-")
            rows.append({
                "ticker": f"{s}.LSE",
                "name": str(row[name_col]) if name_col else "",
                "sector": str(row[sector_col]) if sector_col else "",
                "index": index_label,
            })
        if rows:
            return rows
    return []


def fetch_ftse100():
    return _fetch_ftse_wiki("https://en.wikipedia.org/wiki/FTSE_100_Index", "FTSE100")


def fetch_ftse250():
    return _fetch_ftse_wiki("https://en.wikipedia.org/wiki/FTSE_250_Index", "FTSE250")


def build_universe():
    universe = {}
    for loader, label in [
        (fetch_sp500, "S&P 500"),
        (fetch_sp400, "S&P 400 MidCap"),
        (fetch_russell2000, "Russell 2000"),
        (fetch_ftse100, "FTSE 100"),
        (fetch_ftse250, "FTSE 250"),
    ]:
        try:
            rows = loader()
            print(f"  {label}: {len(rows)} tickers")
            for r in rows:
                universe.setdefault(r["ticker"], r)
        except Exception as e:
            print(f"  {label}: FAILED ({type(e).__name__}: {e})")

    out_path = UNIVERSE_DIR / "universe.json"
    with open(out_path, "w") as f:
        json.dump(list(universe.values()), f, indent=2)
    print(f"Total unique: {len(universe)} -> {out_path}")
    return out_path


if __name__ == "__main__":
    build_universe()
