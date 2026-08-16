"""Terminal front-end for the signal engine.

    india-signals RELIANCE --mode longterm
    india-signals --scan --mode intraday --direction buy
"""

from __future__ import annotations

import argparse
import json
import sys

from india_signals.signals import DISCLAIMER, analyse, scan
from india_signals.watch import check as window_check

BAR = {
    "STRONG_BUY": "\033[92m",
    "BUY": "\033[32m",
    "NEUTRAL": "\033[90m",
    "SELL": "\033[31m",
    "STRONG_SELL": "\033[91m",
}
RESET = "\033[0m"


def _paint(verdict: str) -> str:
    if not sys.stdout.isatty():
        return verdict
    return f"{BAR.get(verdict, '')}{verdict}{RESET}"


def _cell(value: object) -> str:
    """Missing numbers come back as None; format them without blowing up."""
    return "-" if value is None else str(value)


def _print_one(result: dict) -> None:
    if "error" in result:
        print(f"{result['symbol']}: {result['message']}")
        return
    print(f"\n{result['symbol']}  ({result['mode']})")
    print(f"  verdict    {_paint(result['verdict'])}  score {result['score']:+.3f}")
    print(f"  confidence {result['confidence']}  —  {result['agreement']}")
    print(f"  price      {result['last_price']}")
    print("\n  timeframe  rating        score    rsi     osc/ma")
    for frame in result["timeframes"]:
        if "error" in frame:
            print(f"  {frame['timeframe']:<10} unavailable ({frame['error'][:40]})")
            continue
        print(
            f"  {frame['timeframe']:<10} {frame['rating']:<13} {frame['score']:+.3f}"
            f"   {_cell(frame['rsi']):<7} {frame['oscillators']}/{frame['moving_averages']}"
        )
    print(f"\n  {result['how_to_read']}")


def _print_scan(result: dict) -> None:
    print(
        f"\n{result['exchange']} {result['mode']} — top {result['direction']} candidates "
        f"({result['universe_matched']} stocks passed the liquidity filter)\n"
    )
    print(f"  {'ticker':<20} {'verdict':<12} {'score':>7} {'price':>10} {'chg%':>7} {'rsi':>6} {'relvol':>7}")
    for row in result["results"]:
        painted = _paint(row["verdict"])
        pad = len(painted) - len(row["verdict"])  # keep colour codes out of the column width
        print(
            f"  {row['ticker']:<20} {painted:<{12 + pad}} {row['score']:+7.3f} "
            f"{_cell(row['price']):>10} {_cell(row['change_pct']):>7} "
            f"{_cell(row['rsi']):>6} {_cell(row['rel_volume']):>7}"
        )
    print(f"\n  {result['how_to_read']}")


def _print_window(result: dict) -> None:
    market = result["market"]
    state = "OPEN" if market["open"] else f"CLOSED ({market['reason']})"
    print(f"\n{result['symbol']}  —  market {state}, {market['ist_time']}")
    print(f"  {result['headline']}\n")
    print(f"  verdict {result['verdict']}  score {result['score']:+.3f}  "
          f"price {result['price']}  daily RSI {_cell(result['daily_rsi'])}")
    for side in ("buy", "sell"):
        print(f"\n  {side} window conditions:")
        for name, ok in result["checks"][side].items():
            print(f"    [{'x' if ok else ' '}] {name}")
    if not market["open"]:
        print(f"\n  Note: {market['note']} No alert is raised while the market is shut.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="india-signals", description="Live NSE/BSE buy/sell signals."
    )
    parser.add_argument("symbol", nargs="?", help="Bare ticker, e.g. RELIANCE")
    parser.add_argument("--scan", action="store_true", help="Scan the whole exchange")
    parser.add_argument(
        "--window", action="store_true", help="Check for an open buy/sell window"
    )
    parser.add_argument(
        "--peek",
        action="store_true",
        help="With --window, do not record state (leaves a running watch untouched)",
    )
    parser.add_argument("--mode", choices=["intraday", "longterm"], default="intraday")
    parser.add_argument("--direction", choices=["buy", "sell"], default="buy")
    parser.add_argument("--exchange", choices=["NSE", "BSE"], default="NSE")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--json", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    if args.window:
        if not args.symbol:
            parser.error("--window needs a SYMBOL")
        result = window_check(
            symbol=args.symbol, exchange=args.exchange, record=not args.peek
        )
        printer = _print_window
    elif args.scan:
        result = scan(
            mode=args.mode, direction=args.direction, exchange=args.exchange, limit=args.limit
        )
        printer = _print_scan
    elif args.symbol:
        result = analyse(symbol=args.symbol, mode=args.mode, exchange=args.exchange)
        printer = _print_one
    else:
        parser.error("give a SYMBOL or use --scan")

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    printer(result)
    print(f"\n  {result.get('disclaimer', DISCLAIMER)}\n")
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
