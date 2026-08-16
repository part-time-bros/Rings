# TradingView MCP Server

Source: <https://github.com/atilaahmettaner/tradingview-mcp> (PyPI package `tradingview-mcp-server`)

Real-time market data, technical analysis, screeners and backtesting for stocks,
crypto, forex and futures. No TradingView account required — it reads public
endpoints.

## How it's wired up here

`.mcp.json` at the repo root declares the server, so any Claude Code session
started in this repo picks it up automatically. Approve it once when prompted
(`/mcp` lists its status).

```json
{
  "mcpServers": {
    "tradingview": {
      "command": "uvx",
      "args": ["--from", "tradingview-mcp-server", "tradingview-mcp"],
      "env": { "MARKETAUX_API_TOKEN": "${MARKETAUX_API_TOKEN:-}" }
    }
  }
}
```

`uvx` fetches and caches the package on first launch, so there is no separate
install step. It does require [uv](https://docs.astral.sh/uv/) on PATH:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

To pre-warm the cache (optional, makes the first tool call faster):

```bash
uv tool install tradingview-mcp-server
```

## Other clients

**Claude Code CLI**, without the committed config:

```bash
claude mcp add tradingview -- uvx --from tradingview-mcp-server tradingview-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`. On macOS the GUI app
does not inherit your shell PATH, so `command` must be the absolute path to
`uvx` (typically `~/.local/bin/uvx`; run `which uvx` to confirm):

```json
{
  "mcpServers": {
    "tradingview": {
      "command": "/Users/YOUR_USERNAME/.local/bin/uvx",
      "args": ["--from", "tradingview-mcp-server", "tradingview-mcp"]
    }
  }
}
```

## Optional API key

Everything works with no credentials. Setting `MARKETAUX_API_TOKEN` additionally
enables the news and sentiment tools (`financial_news`, `market_sentiment`).
Free tier is 100 requests/day — get a token at <https://www.marketaux.com/>, then
export it in your shell before launching the client:

```bash
export MARKETAUX_API_TOKEN=your_token_here
```

The `${MARKETAUX_API_TOKEN:-}` expansion in `.mcp.json` passes it through when
set and stays empty otherwise, so no key ever gets committed.

## Available tools

37 tools, verified against package version 0.8.0 (server reports itself as
"TradingView Multi-Market Screener" 1.29.0):

- **Screeners** — `top_gainers`, `top_losers`, `stock_screener`, `rating_filter`,
  `bollinger_scan`, `volume_breakout_scanner`, `smart_volume_scanner`,
  `consecutive_candles_scan`, `advanced_candle_pattern`,
  `volume_confirmation_analysis`
- **Analysis** — `coin_analysis`, `multi_timeframe_analysis`, `combined_analysis`,
  `multi_agent_analysis`, `market_sentiment`, `financial_news`
- **Prices & snapshots** — `yahoo_price`, `stock_prices`, `market_snapshot`,
  `bitcoin_market_pulse`, `stock_extended_hours`
- **Options** — `stock_options_chain`, `stock_options_unusual_activity`
- **Futures** — `futures_market_overview`, `futures_top_movers`,
  `futures_category_snapshot`, `futures_watchlist`
- **Backtesting** — `backtest_strategy`, `compare_strategies`,
  `walk_forward_backtest_strategy`
- **EGX (Egyptian Exchange)** — `egx_market_overview`, `egx_sector_scan`,
  `egx_sector_scanner`, `egx_index_analysis`, `egx_stock_screener`,
  `egx_trade_plan`, `egx_fibonacci_retracement`

## No NSE/BSE support — and it fails silently

The technical-analysis and scanner tools (`coin_analysis`,
`multi_timeframe_analysis`, `top_gainers`, `top_losers`, `bollinger_scan`,
`rating_filter`, the volume scanners) accept a fixed exchange list: EGX, BIST,
NASDAQ, NYSE, BURSA, HKEX, SSE, SZSE, TWSE, TPEX, plus crypto venues. `NSE` and
`BSE` are not on it.

Passing them does **not** raise an error — the request falls back to KuCoin:

- `top_gainers(exchange="NSE")` returns `KUCOIN:PIXUSDT`, a crypto microcap, with
  no mention of NSE anywhere in the response.
- `multi_timeframe_analysis(symbol="RELIANCE", exchange="NSE")` returns
  `"symbol": "KUCOIN:RELIANCE"`, every timeframe reading `"No data"`, and still
  emits a confident-looking `HOLD/NO TRADE` recommendation block.

Use [India Signals](india-signals.md) for Indian technical analysis instead.

What *does* work for India through this server:

| Tool | Symbol format | Example |
|------|---------------|---------|
| `stock_screener` | `country="india"` | 7,652 listings, NSE + BSE, INR |
| `stock_prices` | `EXCHANGE:SYMBOL`, comma-separated **string** | `"NSE:TCS,BSE:RELIANCE"` |
| `yahoo_price` | Yahoo suffix | `RELIANCE.NS`, `RELIANCE.BO`, `^NSEI`, `^BSESN` |
| `backtest_strategy`, `compare_strategies`, `walk_forward_backtest_strategy` | Yahoo suffix | `INFY.NS` |

One ranking quirk worth knowing: in `compare_strategies`, strategies that took
**zero trades** rank first, because 0% beats a negative return. Check
`total_trades` before reading the winner.

## Verifying the install

```bash
uvx --from tradingview-mcp-server tradingview-mcp
```

The process starts an MCP server speaking JSON-RPC over stdio — it will sit
silently waiting for input, which means it launched correctly. Press Ctrl-C to
exit. From inside Claude Code, `/mcp` shows connection status and the tool list.
