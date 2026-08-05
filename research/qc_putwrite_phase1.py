# PHASE 1 VALIDATION - Tier 1 core: monthly SPX put-write, hold to expiry (PUT-methodology).
# Paste into a new QuantConnect project (Python) and click Backtest. Free tier, free data.
# NOTE: SPX contract notional (~$600k) exceeds a $100k book, so the backtest runs at $1M cash -
# we are validating RETURN SHAPE (CAGR, drawdown, crash years), not sizing; sizing is XSP/10 live.
from AlgorithmImports import *


class PutWritePhase1(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2013, 1, 1)
        self.SetEndDate(2026, 8, 1)
        self.SetCash(1_000_000)
        index = self.AddIndex("SPX", Resolution.Minute)
        opt = self.AddIndexOption(index.Symbol, Resolution.Minute)
        opt.SetFilter(lambda u: u.IncludeWeeklys(False).Strikes(-3, 3).Expiration(20, 40))
        self.opt_symbol = opt.Symbol
        self.contract = None
        self.SetBenchmark(index.Symbol)

    def OnData(self, data):
        if self.contract is not None:
            if not self.Portfolio[self.contract].Invested:
                self.contract = None          # expired/settled -> free to re-enter
            else:
                return
        chain = data.OptionChains.get(self.opt_symbol)
        if not chain:
            return
        puts = [c for c in chain if c.Right == OptionRight.Put]
        if not puts:
            return
        spot = chain.Underlying.Price
        # nearest monthly expiry in 20-40 DTE, ATM strike (PUT methodology)
        expiry = min(set(c.Expiry for c in puts))
        atm = sorted((c for c in puts if c.Expiry == expiry),
                     key=lambda c: abs(c.Strike - spot))[0]
        if atm.BidPrice and atm.BidPrice > 0:
            self.MarketOrder(atm.Symbol, -1)   # sell 1 ATM put, cash-secured at this book size
            self.contract = atm.Symbol

    def OnEndOfAlgorithm(self):
        self.Log(f"Final equity: {self.Portfolio.TotalPortfolioValue:0.0f}")
