"""
Free Public API integrations — CoinGecko, Mempool, Fear & Greed Index
All endpoints: no auth, no key, CORS-friendly.
"""
import urllib.request
import json
import time

_cache = {}
_CACHE_TTL = 120  # seconds — CoinGecko free tier: ~10-30 req/min


def _fetch(url: str, timeout: int = 8) -> dict:
    """Simple cached JSON fetch with 429 handling."""
    now = time.time()
    hit = _cache.get(url)
    if hit and (now - hit[0]) < _CACHE_TTL:
        return hit[1]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TradingView-Analyzer/1.0"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        _cache[url] = (now, data)
        return data
    except urllib.error.HTTPError as e:
        if e.code == 429 and hit:
            return hit[1]  # Return cached data on rate limit
        return hit[1] if hit else {}
    except Exception:
        return hit[1] if hit else {}


# ═══════════════════════════════════════════════════════════════
#  CoinGecko — Free crypto market data
# ═══════════════════════════════════════════════════════════════
COINGECKO_IDS = {
    "BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana",
    "BNBUSDT": "binancecoin", "XRPUSDT": "ripple", "ADAUSDT": "cardano",
    "DOGEUSDT": "dogecoin", "DOTUSDT": "polkadot", "AVAXUSDT": "avalanche-2",
    "LINKUSDT": "chainlink",
}


def fetch_coingecko(symbol: str = "bitcoin") -> dict:
    """Fetch crypto price, market cap, 24h change from CoinGecko."""
    cg_id = COINGECKO_IDS.get(symbol.upper(), symbol.lower())
    url = (
        f"https://api.coingecko.com/api/v3/simple/price"
        f"?ids={cg_id}&vs_currencies=usd"
        f"&include_24hr_change=true&include_market_cap=true"
        f"&include_24hr_vol=true"
    )
    data = _fetch(url)
    info = data.get(cg_id, {})
    if not info:
        return {}
    return {
        "price": info.get("usd", 0),
        "change_24h": round(info.get("usd_24h_change", 0), 2),
        "market_cap": info.get("usd_market_cap", 0),
        "volume_24h": info.get("usd_24h_vol", 0),
    }


def fetch_coingecko_global() -> dict:
    """Fetch global crypto market stats."""
    url = "https://api.coingecko.com/api/v3/global"
    data = _fetch(url)
    g = data.get("data", {})
    if not g:
        return {}
    return {
        "total_market_cap": g.get("total_market_cap", {}).get("usd", 0),
        "total_volume": g.get("total_volume", {}).get("usd", 0),
        "btc_dominance": round(g.get("market_cap_percentage", {}).get("btc", 0), 1),
        "eth_dominance": round(g.get("market_cap_percentage", {}).get("eth", 0), 1),
        "active_cryptos": g.get("active_cryptocurrencies", 0),
    }


# ═══════════════════════════════════════════════════════════════
#  Mempool.space — Bitcoin network health
# ═══════════════════════════════════════════════════════════════
def fetch_mempool() -> dict:
    """Fetch Bitcoin mempool size, tx count, and recommended fees."""
    pool = _fetch("https://mempool.space/api/mempool")
    fees = _fetch("https://mempool.space/api/v1/fees/recommended")
    if not pool and not fees:
        return {}
    return {
        "tx_count": pool.get("count", 0),
        "vsize_mb": round(pool.get("vsize", 0) / 1e6, 1),
        "total_fee_btc": round(pool.get("total_fee", 0) / 1e8, 4),
        "fastest_fee": fees.get("fastestFee", 0),
        "half_hour_fee": fees.get("halfHourFee", 0),
        "hour_fee": fees.get("hourFee", 0),
        "economy_fee": fees.get("economyFee", 0),
    }


# ═══════════════════════════════════════════════════════════════
#  Fear & Greed Index — Market sentiment
# ═══════════════════════════════════════════════════════════════
def fetch_fear_greed() -> dict:
    """Fetch current Fear & Greed Index (crypto market sentiment)."""
    data = _fetch("https://api.alternative.me/fng/?limit=1")
    items = data.get("data", [])
    if not items:
        return {}
    item = items[0]
    return {
        "value": int(item.get("value", 50)),
        "classification": item.get("value_classification", "Neutral"),
    }


# ═══════════════════════════════════════════════════════════════
#  Combined fetch
# ═══════════════════════════════════════════════════════════════
def fetch_all_market_data(symbol: str = "bitcoin") -> dict:
    """Fetch all free API data. Each API is independent — failures don't block others."""
    result = {}
    try:
        result["coingecko"] = fetch_coingecko(symbol)
    except Exception:
        result["coingecko"] = {}
    try:
        result["global"] = fetch_coingecko_global()
    except Exception:
        result["global"] = {}
    try:
        result["mempool"] = fetch_mempool()
    except Exception:
        result["mempool"] = {}
    try:
        result["fear_greed"] = fetch_fear_greed()
    except Exception:
        result["fear_greed"] = {}
    return result
