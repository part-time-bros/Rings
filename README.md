# Rings

Market-analysis tooling for Claude Code, focused on Indian equities.

## India Signals

Live NSE/BSE buy/sell verdicts for **intraday** or **long-term** trading — one
stock, a watchlist, or a ranked scan of the whole exchange. No account or API
key required.

```bash
uv sync
uv run india-signals RELIANCE --mode longterm
uv run india-signals --scan --mode intraday --direction buy
```

Or just ask Claude: *"is HDFCBANK a buy for intraday?"*

See **[docs/india-signals.md](docs/india-signals.md)** for how verdicts are
scored, the liquidity filters, and the limits of what indicator ratings can tell
you.

## TradingView MCP

The upstream [tradingview-mcp](https://github.com/atilaahmettaner/tradingview-mcp)
server — 37 tools covering global stocks, crypto, futures, options and
backtesting. Note it does **not** support NSE/BSE and silently returns crypto if
you ask it to; that gap is what India Signals fills.

See **[docs/tradingview-mcp.md](docs/tradingview-mcp.md)**.

## Setup

Both servers are declared in `.mcp.json`, so a Claude Code session started in
this repo picks them up after a one-time approval. Requires
[uv](https://docs.astral.sh/uv/).

---

The ŌRB sculptural-objects landing page previously in this repo remains in git
history at commit `cf15802`.
