"""Live NSE/BSE technical signal engine.

Two entry points:

``analyse``  one symbol, read across several timeframes, one verdict.
``scan``     the whole exchange in a single upstream request, ranked.

Both take a ``mode`` of ``intraday`` or ``longterm``, which decides *which*
timeframes are consulted and how heavily each one counts.

Data comes from TradingView's public scanner endpoints via ``tradingview_ta``
and ``tradingview_screener``. No account, no API key.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from tradingview_ta import Interval, TA_Handler
from tradingview_screener import Query, col

Mode = Literal["intraday", "longterm"]
Exchange = Literal["NSE", "BSE"]

SCREENER = "india"

INTERVALS: dict[str, str] = {
    "5m": Interval.INTERVAL_5_MINUTES,
    "15m": Interval.INTERVAL_15_MINUTES,
    "1h": Interval.INTERVAL_1_HOUR,
    "4h": Interval.INTERVAL_4_HOURS,
    "1D": Interval.INTERVAL_1_DAY,
    "1W": Interval.INTERVAL_1_WEEK,
    "1M": Interval.INTERVAL_1_MONTH,
}

# Intraday leans on the fast frames but keeps a daily term so a scalp signal
# can't fully ignore the prevailing trend. Long term inverts that emphasis.
WEIGHTS: dict[str, dict[str, float]] = {
    "intraday": {"5m": 0.20, "15m": 0.30, "1h": 0.30, "1D": 0.20},
    "longterm": {"1D": 0.30, "1W": 0.40, "1M": 0.30},
}

# TradingView's own rating cutoffs, applied to a [-1, 1] score.
BANDS: list[tuple[float, str]] = [
    (0.5, "STRONG_BUY"),
    (0.1, "BUY"),
    (-0.1, "NEUTRAL"),
    (-0.5, "SELL"),
]

DISCLAIMER = (
    "Mechanical aggregation of technical indicators, not investment advice. "
    "Indicator ratings describe current price structure; they do not predict "
    "returns. Backtest and size positions before acting."
)


def _verdict(score: float) -> str:
    """Map a [-1, 1] score onto a rating label."""
    if not _is_number(score):
        return "NO_DATA"
    for threshold, label in BANDS:
        if score >= threshold:
            return label
    return "STRONG_SELL"


def _score_from_summary(summary: dict[str, Any]) -> float:
    """Net bullish share of the indicator panel, in [-1, 1]."""
    buy, sell, neutral = summary["BUY"], summary["SELL"], summary["NEUTRAL"]
    total = buy + sell + neutral
    return (buy - sell) / total if total else 0.0


def _read_timeframe(symbol: str, exchange: str, label: str) -> dict[str, Any]:
    """Pull one timeframe's analysis. Never raises — failures become a row."""
    try:
        analysis = TA_Handler(
            symbol=symbol,
            screener=SCREENER,
            exchange=exchange,
            interval=INTERVALS[label],
        ).get_analysis()
    except Exception as exc:  # upstream is a public endpoint; treat any failure as missing
        return {"timeframe": label, "error": f"{type(exc).__name__}: {exc}"}

    summary = analysis.summary
    indicators = analysis.indicators
    return {
        "timeframe": label,
        "rating": summary["RECOMMENDATION"],
        "score": round(_score_from_summary(summary), 4),
        "counts": {"buy": summary["BUY"], "sell": summary["SELL"], "neutral": summary["NEUTRAL"]},
        "oscillators": analysis.oscillators["RECOMMENDATION"],
        "moving_averages": analysis.moving_averages["RECOMMENDATION"],
        "close": indicators.get("close"),
        "change_pct": _round(indicators.get("change")),
        "rsi": _round(indicators.get("RSI")),
        "macd_hist": _round(
            (indicators.get("MACD.macd") or 0) - (indicators.get("MACD.signal") or 0), 4
        ),
        "ema20": _round(indicators.get("EMA20")),
        "ema50": _round(indicators.get("EMA50")),
        "ema200": _round(indicators.get("EMA200")),
        "volume": indicators.get("volume"),
    }


def _is_number(value: Any) -> bool:
    """True for a real, finite number. The scanner returns NaN for fields a
    stock has no data for, and NaN silently poisons both sorting and the
    verdict bands (every comparison is False, so it lands on STRONG_SELL)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _round(value: Any, digits: int = 2) -> Any:
    return round(value, digits) if _is_number(value) else None


def analyse(symbol: str, mode: Mode = "intraday", exchange: Exchange = "NSE") -> dict[str, Any]:
    """Read one symbol across the timeframes that matter for ``mode``.

    Returns a composite verdict plus the per-timeframe breakdown it was built
    from, so the reasoning is auditable rather than a bare BUY/SELL.
    """
    symbol = symbol.strip().upper().removeprefix(f"{exchange}:")
    exchange = exchange.strip().upper()
    if mode not in WEIGHTS:
        raise ValueError(f"mode must be 'intraday' or 'longterm', got {mode!r}")
    if exchange not in ("NSE", "BSE"):
        raise ValueError(f"exchange must be 'NSE' or 'BSE', got {exchange!r}")

    weights = WEIGHTS[mode]
    with ThreadPoolExecutor(max_workers=len(weights)) as pool:
        frames = list(pool.map(lambda tf: _read_timeframe(symbol, exchange, tf), weights))

    usable = [f for f in frames if "error" not in f]
    if not usable:
        return {
            "symbol": f"{exchange}:{symbol}",
            "mode": mode,
            "error": "NO_DATA",
            "message": (
                f"No timeframe returned data for {exchange}:{symbol}. Check the ticker "
                f"spelling — use the bare NSE/BSE symbol, e.g. 'RELIANCE', not 'RELIANCE.NS'."
            ),
            "timeframes": frames,
        }

    # Re-normalise over the frames that actually answered, so a single dead
    # timeframe shifts confidence rather than silently dragging the score to 0.
    live_weight = sum(weights[f["timeframe"]] for f in usable)
    composite = sum(f["score"] * weights[f["timeframe"]] for f in usable) / live_weight

    agree = sum(
        1
        for f in usable
        if (f["score"] > 0.1) == (composite > 0.1) and (f["score"] < -0.1) == (composite < -0.1)
    )
    agreement = agree / len(usable)

    return {
        "symbol": f"{exchange}:{symbol}",
        "mode": mode,
        "verdict": _verdict(composite),
        "score": round(composite, 4),
        "confidence": _confidence(agreement, len(usable), len(weights)),
        "agreement": f"{agree}/{len(usable)} timeframes aligned",
        "last_price": usable[0].get("close"),
        "timeframes": frames,
        "weights": weights,
        "how_to_read": _explain(mode),
        "disclaimer": DISCLAIMER,
    }


def _confidence(agreement: float, live: int, expected: int) -> str:
    if live < expected:
        return "low (missing timeframes)"
    if agreement >= 0.99:
        return "high"
    if agreement >= 0.6:
        return "medium"
    return "low (timeframes conflict)"


def _explain(mode: Mode) -> str:
    if mode == "intraday":
        return (
            "5m/15m/1h drive the call; the daily term is a trend filter. Conflicting "
            "timeframes mean no clean intraday setup — sit out rather than force it."
        )
    return (
        "Weekly carries the most weight, with monthly for regime and daily for timing. "
        "A long-term BUY on a conflicted daily is an accumulation zone, not an entry trigger."
    )


# ---------------------------------------------------------------------------
# Whole-market scan
# ---------------------------------------------------------------------------

# Per-timeframe rating columns, in TradingView's suffix notation.
RATING_COLUMNS: dict[str, str] = {
    "5m": "Recommend.All|5",
    "15m": "Recommend.All|15",
    "1h": "Recommend.All|60",
    "4h": "Recommend.All|240",
    "1D": "Recommend.All",
    "1W": "Recommend.All|1W",
    "1M": "Recommend.All|1M",
}


def scan(
    mode: Mode = "intraday",
    direction: Literal["buy", "sell"] = "buy",
    exchange: Exchange = "NSE",
    limit: int = 15,
    min_market_cap: float = 5e10,
    min_volume: int = 200_000,
) -> dict[str, Any]:
    """Rank the whole exchange by composite rating in one upstream request.

    ``min_market_cap`` (INR) and ``min_volume`` keep illiquid microcaps out of
    intraday results, where a good-looking rating you cannot actually fill is
    worse than no result.
    """
    if mode not in WEIGHTS:
        raise ValueError(f"mode must be 'intraday' or 'longterm', got {mode!r}")
    if direction not in ("buy", "sell"):
        raise ValueError(f"direction must be 'buy' or 'sell', got {direction!r}")

    weights = WEIGHTS[mode]
    rating_cols = [RATING_COLUMNS[tf] for tf in weights]
    lead = RATING_COLUMNS["15m" if mode == "intraday" else "1W"]

    query = (
        Query()
        .set_markets(SCREENER)
        .select(
            "name",
            "close",
            "change",
            "volume",
            "market_cap_basic",
            "RSI",
            "relative_volume_10d_calc",
            *rating_cols,
        )
        .where(
            col("exchange") == exchange.upper(),
            col("market_cap_basic") > min_market_cap,
            col("volume") > min_volume,
        )
        .order_by(lead, ascending=(direction == "sell"))
        .limit(max(limit * 4, 50))
    )

    matched, frame = query.get_scanner_data()

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict("records"):
        scores = {
            tf: record[RATING_COLUMNS[tf]]
            for tf in weights
            if _is_number(record.get(RATING_COLUMNS[tf]))
        }
        # Require every weighted timeframe, otherwise a stock rated on one
        # frame outranks one rated on all of them.
        if len(scores) < len(weights):
            continue
        live_weight = sum(weights[tf] for tf in scores)
        composite = sum(scores[tf] * weights[tf] for tf in scores) / live_weight
        rows.append(
            {
                "ticker": record.get("ticker"),
                "symbol": record.get("name"),
                "verdict": _verdict(composite),
                "score": round(composite, 4),
                "price": _round(record.get("close")),
                "change_pct": _round(record.get("change")),
                "rsi": _round(record.get("RSI")),
                "rel_volume": _round(record.get("relative_volume_10d_calc")),
                "by_timeframe": {tf: round(v, 4) for tf, v in scores.items()},
            }
        )

    rows.sort(key=lambda r: r["score"], reverse=(direction == "buy"))
    return {
        "mode": mode,
        "direction": direction,
        "exchange": exchange.upper(),
        "universe_matched": matched,
        "filters": {"min_market_cap_inr": min_market_cap, "min_volume": min_volume},
        "weights": weights,
        "results": rows[:limit],
        "how_to_read": _explain(mode),
        "disclaimer": DISCLAIMER,
    }
