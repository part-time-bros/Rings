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

## Verifying the install

```bash
uvx --from tradingview-mcp-server tradingview-mcp
```

The process starts an MCP server speaking JSON-RPC over stdio — it will sit
silently waiting for input, which means it launched correctly. Press Ctrl-C to
exit. From inside Claude Code, `/mcp` shows connection status and the tool list.
