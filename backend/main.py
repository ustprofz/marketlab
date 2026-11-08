"""Read-only Yahoo Finance adapter for an educational GitHub Pages front end.

Run: uvicorn backend.main:app --host 0.0.0.0 --port 3000
No credentials, trading endpoints, or student records are used.
"""
from __future__ import annotations

import copy
import csv
import io
import logging
import math
import os
import re
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

LOG = logging.getLogger("market_lab")
ROOT = Path(__file__).resolve().parents[1]
RANGES = {"1D": ("1d", "1m"), "5D": ("5d", "15m"), "1M": ("1mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1d")}
CATALOG = [
    {"symbol": "AAPL", "name": "Apple", "category": "Technology"},
    {"symbol": "MSFT", "name": "Microsoft", "category": "Technology"},
    {"symbol": "NKE", "name": "Nike", "category": "Consumer brands"},
    {"symbol": "DIS", "name": "The Walt Disney Company", "category": "Entertainment"},
    {"symbol": "TGT", "name": "Target", "category": "Retail"},
    {"symbol": "NVDA", "name": "NVIDIA", "category": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet", "category": "Technology"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "category": "Broad-market ETF"},
]
SYMBOL_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.^=\-]{0,23}$")
TTL_INTRADAY = 60
TTL_DAILY = 300
MAX_CACHE = 64
cache: OrderedDict = OrderedDict()
cache_lock = threading.RLock()
fetch_locks = [threading.Lock() for _ in range(32)]
upstream_slots = threading.BoundedSemaphore(2)
rate_lock = threading.Lock()
request_times: OrderedDict = OrderedDict()
app = FastAPI(title="Market Lab API", version="1.0.0")

# GET-only, credential-free access. Set ALLOWED_ORIGINS to the Pages origin
# (e.g. https://yourname.github.io) to restrict browser access to your own site.
origins = [s.strip() for s in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if s.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=[], allow_credentials=False)


@app.middleware("http")
async def limit_requests(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with rate_lock:
            recent = request_times.setdefault(key, deque())
            request_times.move_to_end(key)
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= 120:
                return JSONResponse(status_code=429, content={"detail": "Too many requests. Please wait a minute."}, headers={"Retry-After": "60"})
            recent.append(now)
            while len(request_times) > 2000:
                request_times.popitem(last=False)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError, OverflowError):
        return None


def valid_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(symbol):
        raise HTTPException(422, "Enter a ticker of up to 24 letters/numbers, optionally including ., -, ^ or =.")
    return symbol


def normalize_history(frame: pd.DataFrame) -> list[dict]:
    """Keep Yahoo's Close and Adj Close distinct; never auto-adjust silently."""
    bars = []
    for timestamp, row in frame.iterrows():
        close = number(row.get("Close"))
        if close is None:
            continue
        stamp = pd.Timestamp(timestamp)
        if pd.isna(stamp):
            continue
        bars.append({
            "time": stamp.isoformat(),
            "open": number(row.get("Open")), "high": number(row.get("High")),
            "low": number(row.get("Low")), "close": close,
            "adj_close": number(row.get("Adj Close")),
            "volume": number(row.get("Volume")),
            "dividends": number(row.get("Dividends")),
            "stock_splits": number(row.get("Stock Splits")),
        })
    return sorted({row["time"]: row for row in bars}.values(), key=lambda row: pd.Timestamp(row["time"]).value)


def fetch_yahoo(symbol: str, selected_range: str) -> dict:
    period, interval = RANGES[selected_range]
    ticker = yf.Ticker(symbol)
    history = ticker.history(period=period, interval=interval, auto_adjust=False,
                             actions=True, prepost=False, timeout=12, raise_errors=True)
    bars = normalize_history(history)
    if not bars:
        raise ValueError("No usable price bars returned")
    try:
        metadata = ticker.get_history_metadata() or {}
    except Exception:
        metadata = {}
    entry = next((item for item in CATALOG if item["symbol"] == symbol), {})
    quote = number(metadata.get("regularMarketPrice"))
    quote_time = number(metadata.get("regularMarketTime"))
    quote_kind = "regular_market_quote" if quote is not None and quote_time is not None else "last_returned_bar"
    if quote_kind == "last_returned_bar":
        quote = bars[-1]["close"]
        quote_as_of = bars[-1]["time"]
    else:
        quote_as_of = datetime.fromtimestamp(quote_time, timezone.utc).isoformat()
    return {
        "schema_version": 1, "symbol": symbol,
        "name": str(metadata.get("longName") or metadata.get("shortName") or entry.get("name") or symbol)[:120],
        "currency": metadata.get("currency") or None,
        "exchange": metadata.get("exchangeName") or None,
        "timezone": metadata.get("exchangeTimezoneName") or str(history.index.tz or "Unknown"),
        "range": selected_range, "interval": interval,
        "source": {"kind": "yahoo_yfinance", "label": "Yahoo Finance via yfinance", "simulated": False},
        "fetched_at": utc_now(), "as_of": bars[-1]["time"],
        "quote": {"price": quote, "as_of": quote_as_of, "kind": quote_kind},
        "notice": "Quotes may be delayed. Refreshing does not guarantee exchange-level real-time prices.",
        "price_basis": "auto_adjust=False: separate Yahoo Close and Adj Close fields", "bars": bars,
    }


def get_series(symbol: str, selected_range: str) -> dict:
    symbol = valid_symbol(symbol)
    if selected_range not in RANGES:
        raise HTTPException(422, "Choose 1D, 5D, 1M, 6M, 1Y or 5Y.")
    key = (symbol, selected_range)
    ttl = TTL_INTRADAY if selected_range in ("1D", "5D") else TTL_DAILY

    def cached():
        now = time.monotonic()
        with cache_lock:
            entry = cache.get(key)
            if entry and now - entry[0] < entry[1]:
                cache.move_to_end(key)
                if "error" in entry[2]:
                    raise HTTPException(503, entry[2]["error"], headers={"Retry-After": "30"})
                data = copy.deepcopy(entry[2])
                data["cache"] = {"hit": True, "age_seconds": round(now - entry[0], 1), "ttl_seconds": ttl}
                return data
        return None

    existing = cached()
    if existing:
        return existing
    with fetch_locks[hash(key) % len(fetch_locks)]:
        existing = cached()
        if existing:
            return existing
        if not upstream_slots.acquire(timeout=2):
            raise HTTPException(503, "The data service is busy. Please try again shortly.", headers={"Retry-After": "10"})
        try:
            data = fetch_yahoo(symbol, selected_range)
        except Exception as error:
            LOG.warning("Yahoo retrieval failed for %s (%s)", symbol, type(error).__name__)
            message = "Yahoo data is unavailable for this symbol/range right now. Check the ticker, try later, or switch to clearly labelled practice data."
            with cache_lock:
                cache[key] = (time.monotonic(), 30, {"error": message})
                while len(cache) > MAX_CACHE:
                    cache.popitem(last=False)
            raise HTTPException(503, message, headers={"Retry-After": "30"}) from None
        finally:
            upstream_slots.release()
        with cache_lock:
            cache[key] = (time.monotonic(), ttl, copy.deepcopy(data))
            cache.move_to_end(key)
            while len(cache) > MAX_CACHE:
                cache.popitem(last=False)
        data["cache"] = {"hit": False, "age_seconds": 0, "ttl_seconds": ttl}
        return data


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": "yfinance", "version": yf.__version__,
            "intraday_cache_seconds": TTL_INTRADAY, "daily_cache_seconds": TTL_DAILY,
            "notice": "Service health does not guarantee Yahoo availability or real-time quotes."}


@app.get("/api/catalog")
def catalog():
    return CATALOG


@app.get("/api/search")
def search(q: str = Query(min_length=1, max_length=64)):
    q = q.strip()
    local = [item for item in CATALOG if q.lower() in (item["symbol"] + " " + item["name"]).lower()]
    if local:
        return {"results": local, "source": "starter_catalog"}
    if not upstream_slots.acquire(timeout=2):
        raise HTTPException(503, "Search is busy. Try entering the ticker directly.")
    try:
        results = yf.Search(q, max_results=8, news_count=0, timeout=10).quotes
        filtered = [{"symbol": item["symbol"], "name": str(item.get("longname") or item.get("shortname") or item["symbol"])[:120],
                     "category": str(item.get("quoteType") or "Security")[:40]}
                    for item in results if SYMBOL_RE.fullmatch(str(item.get("symbol", "")))]
        return {"results": filtered[:8], "source": "Yahoo Finance via yfinance"}
    except Exception:
        raise HTTPException(503, "Yahoo search is unavailable. Try a ticker symbol directly.") from None
    finally:
        upstream_slots.release()


@app.get("/api/series")
def series(symbol: str = Query(max_length=24), range: str = "1Y"):
    return get_series(symbol, range.upper())


def spreadsheet_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def to_csv(data: dict) -> str:
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(["Timestamp", "Ticker", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits", "Currency", "Interval", "Exchange Timezone", "Data Source", "Fetched At"])
    for bar in data["bars"]:
        writer.writerow([spreadsheet_safe(value) for value in [bar["time"], data["symbol"], bar["open"], bar["high"], bar["low"], bar["close"], bar["adj_close"], bar["volume"], bar["dividends"], bar["stock_splits"], data["currency"], data["interval"], data["timezone"], data["source"]["label"], data["fetched_at"]]])
    return out.getvalue()


@app.get("/api/download.csv")
def download_csv(symbol: str = Query(max_length=24), range: str = "1Y"):
    data = get_series(symbol, range.upper())
    name = re.sub(r"[^A-Z0-9_-]", "_", data["symbol"]) + "_" + data["range"] + ".csv"
    return Response("\ufeff" + to_csv(data), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# Local preview / optional all-in-one hosting uses the same backend and front end.
# GitHub Pages instead serves docs/config.js with the deployed service URL.
@app.get("/config.js", include_in_schema=False)
def local_config():
    return Response('window.MARKET_LAB_CONFIG = {apiBase: window.location.origin, refreshMs: 60000};', media_type="application/javascript")


if (ROOT / "docs").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "docs", html=True), name="site")
