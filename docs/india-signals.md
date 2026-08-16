# India Signals — live NSE/BSE buy/sell verdicts

Answers one question fast: **is this stock a buy or a sell right now, for the
kind of trading I actually do?**

Live data from TradingView's public scanner endpoints. No account, no API key,
no paid feed.

## Why this exists

The `tradingview` MCP server in this repo cannot see Indian markets. Its
technical-analysis tools accept a fixed exchange list (EGX, BIST, NASDAQ, NYSE,
BURSA, HKEX, SSE, SZSE, TWSE, TPEX) and — the dangerous part — **silently fall
back to KuCoin crypto** when handed `NSE` or `BSE`. Asking it for "top NSE
gainers" returns a crypto microcap with no warning.

The underlying `tradingview_ta` library supports India perfectly well via
`screener="india"`. This package uses that directly.

## Two modes

Mode decides which timeframes are consulted and how much each one counts:

| Mode | 5m | 15m | 1h | 1D | 1W | 1M |
|------|----|-----|----|----|----|-----|
| `intraday` | 0.20 | 0.30 | 0.30 | 0.20 | — | — |
| `longterm` | — | — | — | 0.30 | 0.40 | 0.30 |

Intraday leans on the fast frames but keeps a daily term so a scalp signal
can't fully ignore the prevailing trend. Long term inverts that: weekly carries
the most weight, monthly sets the regime, daily handles timing.

Each timeframe contributes a score in `[-1, 1]` — the net bullish share of
TradingView's ~26-indicator panel. The weighted composite maps onto TradingView's
own bands: `≥0.5` STRONG_BUY, `≥0.1` BUY, `>-0.1` NEUTRAL, `>-0.5` SELL, else
STRONG_SELL.

**Confidence** comes from agreement, not strength. Four aligned timeframes read
`high`; a split panel reads `low (timeframes conflict)` even when the composite
looks decisive. A conflicted intraday reading is the tool telling you there is
no clean setup.

## Command line

```bash
uv run india-signals RELIANCE --mode longterm
uv run india-signals TCS --mode intraday --exchange NSE
uv run india-signals --scan --mode intraday --direction buy --limit 10
uv run india-signals --scan --mode longterm --direction sell
uv run india-signals INFY --json          # machine-readable
```

Single-stock output shows the composite plus every timeframe behind it, so you
can see *why*:

```
NSE:RELIANCE  (longterm)
  verdict    SELL  score -0.196
  confidence medium  —  2/3 timeframes aligned
  price      1310

  timeframe  rating        score    rsi     osc/ma
  1D         SELL          -0.115   50.73   NEUTRAL/SELL
  1W         SELL          -0.346   44.76   NEUTRAL/STRONG_SELL
  1M         NEUTRAL       -0.077   46.78   NEUTRAL/SELL
```

`--scan` ranks the whole exchange in a single upstream request:

```
NSE longterm — top buy candidates (570 stocks passed the liquidity filter)

  ticker               verdict        score      price    chg%    rsi  relvol
  NSE:LGEINDIA         STRONG_BUY    +0.749     1729.7    9.59  73.86   32.36
  NSE:UTLSOLAR         STRONG_BUY    +0.748     423.85     3.4  69.67    2.95
  NSE:LENSKART         STRONG_BUY    +0.702     611.85     2.5   76.3     1.3
```

## From Claude

`.mcp.json` registers the server, so a Claude Code session in this repo can just
be asked in plain language — "is HDFCBANK a buy for intraday?", "scan NSE for
long-term sells". Three tools back it:

| Tool | Does |
|------|------|
| `stock_signal(symbol, mode, exchange)` | Verdict for one stock with full timeframe breakdown |
| `scan_market(mode, direction, exchange, limit, …)` | Rank the whole exchange, strongest buys or sells |
| `compare_signals(symbols, mode, exchange)` | Rank a watchlist strongest to weakest |
| `check_window(symbol, exchange, record)` | Has a buy/sell window just opened? |
| `market_open()` | Is the exchange in session right now? |

Symbols are **bare NSE/BSE tickers** — `RELIANCE`, `TCS`, `HDFCBANK`. Not the
Yahoo form (`RELIANCE.NS`), not exchange-prefixed (`NSE:RELIANCE`); both are
stripped or rejected with a message telling you which form to use.

## Windows — when is it actually actionable?

A rating is not a window. A stock can sit at BUY for weeks, so alerting on
"verdict == BUY" fires on every check and tells you nothing. A **window** is a
transition into a condition worth acting on, and it fires once, when it opens.

```bash
uv run india-signals CUPID --window          # check and record state
uv run india-signals CUPID --window --peek   # read-only, leaves a watch untouched
```

**Buy window** — all four must hold:

| Condition | Why |
|-----------|-----|
| intraday composite ≥ +0.10 | rated BUY or better |
| 5m and 15m both positive | the intraday tape is participating, so the signal isn't just inherited from a strong daily chart |
| daily RSI < 70 | not blown off — you're buying a pullback, not a top |
| close > daily EMA50 | the larger uptrend is still intact |

**Sell window** — any one is enough:

| Condition | Why |
|-----------|-----|
| intraday composite ≤ -0.10 | rated SELL or worse |
| close < daily EMA20 | trend break |
| daily RSI > 80 **and** 1h MACD histogram < 0 | exhaustion rollover — the specific risk in a name trading far above its moving averages |

Sell is evaluated first: an exit outranks an entry when both somehow qualify.

State lives in `~/.cache/india-signals/windows.json`, so `opened` is true only
on a transition. Poll it on a schedule and you get one alert per window rather
than one per check.

### Market hours

Every check reports `market.open`, and `alert` is never true while the exchange
is shut — outside 9:15–15:30 IST on a weekday, the 5m/15m candles are the
previous session's close, frozen. A weekend reading looks live and is not.

Exchange **holidays are not tracked**. On a holiday the clock check says open
and the prices are stale. Worth knowing before trusting an alert on a public
holiday.

## Liquidity filters

`scan_market` defaults to `min_market_cap` ₹50bn and `min_volume` 200,000
shares. This is deliberate: without it the top of an intraday scan fills with
microcaps whose ratings look excellent and which you cannot actually fill. Lower
them if you want the long tail:

```bash
uv run india-signals --scan --mode intraday --limit 20
```
```python
scan_market(mode="intraday", min_market_cap=1e9, min_volume=50_000)
```

A stock is dropped from a scan unless **every** weighted timeframe returned a
rating, so a stock scored on one frame can't outrank one scored on all of them.

## Install

Needs [uv](https://docs.astral.sh/uv/). From the repo root:

```bash
uv sync
```

That's it — `uv run` handles the venv from there. The `.mcp.json` entry uses
`--directory .`, so it resolves against the directory Claude Code was started
in; if you launch from elsewhere, change it to the absolute path of this repo.

## What this is and isn't

These are mechanical aggregations of technical indicators. They describe current
price structure — they do not predict returns, and no indicator panel does.
Ratings flip intraday, and a STRONG_BUY on a 5-minute chart can be a losing
trade ten minutes later.

Treat the output as one input to your own decision, not a decision. Backtest a
rule before trading it — the `tradingview` MCP server's `backtest_strategy` and
`compare_strategies` accept Yahoo-format Indian symbols (`RELIANCE.NS`,
`INFY.NS`, `.BO` for BSE) if you want to check how a strategy behaved
historically. Nothing here manages risk or sizes positions for you.
