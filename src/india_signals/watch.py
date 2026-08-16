"""Window detection — is there an actionable entry or exit right now?

A rating is not a window. CUPID sits at BUY for weeks on end; alerting on
"verdict == BUY" would fire every check and tell you nothing. A *window* is a
transition into a condition worth acting on, and it fires once when it opens.

Buy window (all must hold):
  - intraday composite >= +0.10 (BUY or better)
  - 5m and 15m both positive — the intraday tape is participating, so the
    signal isn't just inherited from a strong daily chart
  - daily RSI < 70 — not blown off; you're buying a pullback, not a top
  - daily close > daily EMA50 — the larger uptrend is still intact

Sell window (any one is enough):
  - intraday composite <= -0.10 (SELL or worse)
  - daily close < daily EMA20 — trend break
  - daily RSI > 80 AND 1h MACD histogram < 0 — exhaustion rollover, the
    specific risk in a name that has run far above its moving averages

State is written to disk so a window fires on the transition into it. Repeat
checks while the same window stays open stay silent.
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from india_signals.signals import Exchange, _is_number, _read_timeframe, analyse

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

DEFAULT_STATE = Path.home() / ".cache" / "india-signals" / "windows.json"

Thresholds = dict[str, float]
DEFAULTS: Thresholds = {
    "buy_score": 0.10,
    "buy_rsi_max": 70.0,
    "sell_score": -0.10,
    "sell_rsi_extreme": 80.0,
}


def market_status(now: datetime | None = None) -> dict[str, Any]:
    """Is NSE/BSE in session? Weekday and clock only — exchange holidays are
    not enumerated here, so a holiday reads as 'open' with stale prices."""
    now = (now or datetime.now(timezone.utc)).astimezone(IST)
    weekday = now.weekday() < 5
    in_hours = MARKET_OPEN <= now.time() <= MARKET_CLOSE
    return {
        "ist_time": now.strftime("%Y-%m-%d %H:%M (%A)"),
        "open": weekday and in_hours,
        "reason": (
            "in session"
            if weekday and in_hours
            else "weekend" if not weekday else "outside 9:15-15:30 IST"
        ),
        "note": "Exchange holidays are not tracked; prices will look live but be stale.",
    }


def _daily_frame(symbol: str, exchange: str) -> dict[str, Any]:
    return _read_timeframe(symbol, exchange, "1D")


def evaluate(
    symbol: str,
    exchange: Exchange = "NSE",
    thresholds: Thresholds | None = None,
) -> dict[str, Any]:
    """Evaluate window conditions without touching stored state."""
    cfg = {**DEFAULTS, **(thresholds or {})}
    reading = analyse(symbol=symbol, mode="intraday", exchange=exchange)
    if "error" in reading:
        return {"symbol": reading["symbol"], "window": None, "error": reading["error"]}

    frames = {f["timeframe"]: f for f in reading["timeframes"] if "error" not in f}
    daily = frames.get("1D") or _daily_frame(symbol.upper(), exchange.upper())
    score = reading["score"]

    fast = [frames[tf]["score"] for tf in ("5m", "15m") if tf in frames]
    fast_ok = bool(fast) and all(s > 0 for s in fast)

    rsi = daily.get("rsi")
    close = daily.get("close")
    ema20, ema50 = daily.get("ema20"), daily.get("ema50")
    macd_1h = frames.get("1h", {}).get("macd_hist")

    buy_checks = {
        f"composite >= {cfg['buy_score']:+.2f}": score >= cfg["buy_score"],
        "5m and 15m both positive": fast_ok,
        f"daily RSI < {cfg['buy_rsi_max']:.0f}": _is_number(rsi) and rsi < cfg["buy_rsi_max"],
        "close > daily EMA50": _is_number(close) and _is_number(ema50) and close > ema50,
    }
    sell_checks = {
        f"composite <= {cfg['sell_score']:+.2f}": score <= cfg["sell_score"],
        "close < daily EMA20": _is_number(close) and _is_number(ema20) and close < ema20,
        f"daily RSI > {cfg['sell_rsi_extreme']:.0f} with 1h MACD rolling over": (
            _is_number(rsi)
            and rsi > cfg["sell_rsi_extreme"]
            and _is_number(macd_1h)
            and macd_1h < 0
        ),
    }

    # Sell is evaluated first: an exit signal outranks an entry signal when both
    # somehow qualify.
    if any(sell_checks.values()):
        window: str | None = "SELL"
    elif all(buy_checks.values()):
        window = "BUY"
    else:
        window = None

    return {
        "symbol": reading["symbol"],
        "window": window,
        "verdict": reading["verdict"],
        "score": score,
        "confidence": reading["confidence"],
        "price": reading["last_price"],
        "daily_rsi": rsi,
        "checks": {"buy": buy_checks, "sell": sell_checks},
        "blocking": [name for name, ok in buy_checks.items() if not ok] if window != "BUY" else [],
        "triggered": [name for name, ok in sell_checks.items() if ok] if window == "SELL" else [],
        "timeframes": reading["timeframes"],
        "market": market_status(),
    }


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def check(
    symbol: str,
    exchange: Exchange = "NSE",
    state_path: Path | str = DEFAULT_STATE,
    thresholds: Thresholds | None = None,
    record: bool = True,
) -> dict[str, Any]:
    """Evaluate and report whether a window just *opened*.

    ``opened`` is True only on a transition, so polling this on a schedule
    produces one alert per window rather than one per check.
    """
    path = Path(state_path)
    result = evaluate(symbol=symbol, exchange=exchange, thresholds=thresholds)
    if "error" in result:
        return {**result, "opened": False, "alert": False}

    state = _load(path)
    key = result["symbol"]
    previous = state.get(key, {}).get("window")
    current = result["window"]
    opened = current is not None and current != previous

    if record:
        state[key] = {
            "window": current,
            "score": result["score"],
            "price": result["price"],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        _save(path, state)

    return {
        **result,
        "previous_window": previous,
        "opened": opened,
        "alert": opened and result["market"]["open"],
        "headline": _headline(result, opened, result["market"]["open"]),
    }


def _headline(result: dict[str, Any], opened: bool, market_open: bool) -> str:
    symbol, price = result["symbol"], result["price"]
    if not market_open:
        # Outside session the candles are the previous close, so nothing has
        # "opened" — say what the stale data shows without implying a trigger.
        state = result["window"] or "no"
        return (
            f"{symbol}: market closed — last session's candles show a {state} "
            f"window condition. Not actionable until the next open."
        )
    if not opened:
        if result["window"]:
            return f"{symbol}: {result['window']} window still open (no change since last check)."
        blocking = ", ".join(result["blocking"]) or "conditions not met"
        return f"{symbol}: no window. Waiting on — {blocking}."
    if result["window"] == "SELL":
        why = "; ".join(result["triggered"])
        return f"SELL WINDOW OPENED — {symbol} at {price}. Triggered by: {why}."
    return (
        f"BUY WINDOW OPENED — {symbol} at {price}, "
        f"score {result['score']:+.3f}, daily RSI {result['daily_rsi']}."
    )
