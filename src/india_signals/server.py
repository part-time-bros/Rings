"""MCP server exposing live NSE/BSE buy/sell signals."""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from india_signals.signals import analyse, scan
from india_signals.watch import check as window_check
from india_signals.watch import market_status

mcp = MCPServer("India Signals", version="0.1.0")


@mcp.tool()
def stock_signal(
    symbol: str,
    mode: Literal["intraday", "longterm"] = "intraday",
    exchange: Literal["NSE", "BSE"] = "NSE",
) -> dict[str, Any]:
    """Buy/sell verdict for one Indian stock, live from TradingView.

    Args:
        symbol: Bare NSE/BSE ticker — "RELIANCE", "TCS", "HDFCBANK".
            Not the Yahoo form ("RELIANCE.NS") and not exchange-prefixed.
        mode: "intraday" weights 5m/15m/1h with a daily trend filter;
            "longterm" weights daily/weekly/monthly.
        exchange: NSE or BSE.

    Returns a verdict (STRONG_BUY…STRONG_SELL), a [-1, 1] score, a confidence
    reading based on how far the timeframes agree, and the full per-timeframe
    breakdown including RSI, MACD histogram and EMA20/50/200.
    """
    return analyse(symbol=symbol, mode=mode, exchange=exchange)


@mcp.tool()
def scan_market(
    mode: Literal["intraday", "longterm"] = "intraday",
    direction: Literal["buy", "sell"] = "buy",
    exchange: Literal["NSE", "BSE"] = "NSE",
    limit: int = 15,
    min_market_cap: float = 5e10,
    min_volume: int = 200_000,
) -> dict[str, Any]:
    """Scan the whole exchange and rank the strongest buy or sell candidates.

    One upstream request covers every listed stock, so this is fast enough to
    run interactively.

    Args:
        mode: "intraday" ranks on the fast timeframes, "longterm" on weekly.
        direction: "buy" ranks most bullish first, "sell" most bearish first.
        exchange: NSE or BSE.
        limit: How many rows to return.
        min_market_cap: Floor in INR. Default 50bn filters out microcaps that
            look good on a chart but cannot be filled.
        min_volume: Minimum share volume on the current session.
    """
    return scan(
        mode=mode,
        direction=direction,
        exchange=exchange,
        limit=limit,
        min_market_cap=min_market_cap,
        min_volume=min_volume,
    )


@mcp.tool()
def compare_signals(
    symbols: list[str],
    mode: Literal["intraday", "longterm"] = "intraday",
    exchange: Literal["NSE", "BSE"] = "NSE",
) -> dict[str, Any]:
    """Rank a watchlist of Indian stocks strongest to weakest.

    Args:
        symbols: Bare tickers, e.g. ["RELIANCE", "TCS", "INFY"].
        mode: "intraday" or "longterm".
        exchange: NSE or BSE.
    """
    results = [analyse(symbol=s, mode=mode, exchange=exchange) for s in symbols]
    ranked = sorted(
        (r for r in results if "error" not in r), key=lambda r: r["score"], reverse=True
    )
    return {
        "mode": mode,
        "exchange": exchange.upper(),
        "ranked": [
            {
                "symbol": r["symbol"],
                "verdict": r["verdict"],
                "score": r["score"],
                "confidence": r["confidence"],
                "last_price": r["last_price"],
            }
            for r in ranked
        ],
        "failed": [r["symbol"] for r in results if "error" in r],
    }


@mcp.tool()
def check_window(
    symbol: str,
    exchange: Literal["NSE", "BSE"] = "NSE",
    record: bool = True,
) -> dict[str, Any]:
    """Has an actionable buy or sell window just opened for this stock?

    A rating is not a window — a stock can sit at BUY for weeks. This reports
    ``opened: true`` only on a transition into a buy or sell condition, so
    polling it on a schedule yields one alert per window, not one per check.

    Buy window needs all of: intraday composite >= +0.10, 5m and 15m both
    positive, daily RSI < 70, close above the daily EMA50.
    Sell window needs any of: composite <= -0.10, close below daily EMA20, or
    daily RSI > 80 with the 1h MACD histogram rolling over.

    Args:
        symbol: Bare NSE/BSE ticker, e.g. "CUPID".
        exchange: NSE or BSE.
        record: Persist the window state so the next call can detect a
            transition. Pass False for a read-only peek that does not affect
            a running watch.
    """
    return window_check(symbol=symbol, exchange=exchange, record=record)


@mcp.tool()
def market_open() -> dict[str, Any]:
    """Is the Indian market in session right now?

    Weekday and clock only (9:15–15:30 IST) — exchange holidays are not
    tracked, so a holiday reads as open while prices are actually stale.
    """
    return market_status()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
