import asyncio
import hashlib
import random
import time
from datetime import datetime, timedelta, timezone

COINS = {
    "BTC": 114000.0,
    "ETH": 4480.0,
    "SOL": 231.5,
    "HYPE": 38.4,
    "DOGE": 0.238,
    "AVAX": 37.9,
    "XRP": 2.95,
    "LINK": 21.7,
}
COIN_VOL = {"BTC": 0.004, "ETH": 0.006, "SOL": 0.010, "HYPE": 0.016, "DOGE": 0.012, "AVAX": 0.010, "XRP": 0.009, "LINK": 0.011}
LABELS = ["Smart HL Perps Trader", "Fund IV", "0xQuant", "Perp Whale", "Basis Desk", "MM Bot", "HL Sniper"]

_POOL = []


def _addr(i: int) -> str:
    h = hashlib.sha256(f"perppilot-demo-{i}".encode()).hexdigest()
    return "0x" + h[:40]


def _rng(*key) -> random.Random:
    return random.Random(hashlib.sha256(":".join(str(k) for k in key).encode()).hexdigest())


def _label_for(address: str) -> str:
    r = _rng("label", address)
    if r.random() < 0.55:
        return LABELS[0]
    return r.choice(LABELS[1:])


def _is_smart(address: str) -> bool:
    return _rng("smart", address).random() < 0.6


for _i in range(48):
    _POOL.append(_addr(_i))


def _mk_leaderboard_row(address: str, r: random.Random) -> dict:
    smart = _is_smart(address)
    pnl = r.uniform(40_000, 2_400_000) * (1.6 if smart else 1.0)
    roi = r.uniform(0.04, 2.8) * (1.3 if smart else 1.0)
    vol = pnl / max(roi, 0.02) * r.uniform(0.8, 1.4)
    n_trades = int(r.uniform(60, 4200))
    positions = []
    n_pos = r.randint(0, 4)
    for _ in range(n_pos):
        coin = r.choice(list(COINS))
        side = r.choice(["long", "short"])
        val = r.uniform(8_000, 900_000)
        entry = COINS[coin] * r.uniform(0.93, 1.07)
        positions.append(
            {
                "coin": coin,
                "side": side,
                "size_base": round(val / entry, 4),
                "position_value_usd": round(val, 2),
                "entry_price": round(entry, 6),
                "unrealized_pnl_usd": round(val * r.uniform(-0.12, 0.18), 2),
            }
        )
    positions.sort(key=lambda p: -p["position_value_usd"])
    return {
        "trader_address": address,
        "trader_address_label": _label_for(address),
        "total_pnl": round(pnl, 2),
        "realized_pnl_usd": round(pnl * r.uniform(0.5, 0.95), 2),
        "unrealized_pnl_usd": round(pnl * r.uniform(0.05, 0.5), 2),
        "roi": round(roi, 4),
        "volume_usd": round(vol, 2),
        "total_trades": n_trades,
        "top_positions": positions,
        "account_value": round(pnl / max(roi, 0.02) * r.uniform(0.6, 2.2) + 25_000, 2),
    }


def _leaderboard(payload: dict) -> dict:
    date = payload.get("date") or {}
    rkey = f"{date.get('from')}..{date.get('to')}"
    rows = [_mk_leaderboard_row(a, _rng("lb", a, rkey)) for a in _POOL]
    rows.sort(key=lambda x: -x["total_pnl"])
    per_page = int((payload.get("pagination") or {}).get("per_page", 10))
    page = int((payload.get("pagination") or {}).get("page", 1))
    start = (page - 1) * per_page
    chunk = rows[start : start + per_page]
    return {
        "data": chunk,
        "pagination": {"page": page, "per_page": per_page, "is_last_page": start + per_page >= len(rows)},
    }


def _positions(address: str) -> dict:
    bucket = int(time.time() // 90)
    r = _rng("pos", address, bucket)
    prev_r = _rng("pos", address, bucket - 1)
    asset_positions = []
    n = r.randint(1, 6)
    prev_coins = []
    pn = prev_r.randint(1, 6)
    for _ in range(pn):
        prev_coins.append((prev_r.choice(list(COINS)), prev_r.choice(["long", "short"])))
    for i in range(n):
        if i < len(prev_coins) and r.random() < 0.75:
            coin, side = prev_coins[i]
        else:
            coin, side = r.choice(list(COINS)), r.choice(["long", "short"])
        base = COINS[coin]
        drift = 1.0 + r.uniform(-COIN_VOL[coin] * 6, COIN_VOL[coin] * 6)
        entry = base * (1 + r.uniform(-0.05, 0.05))
        mark = entry * drift
        lev = r.randint(2, 25)
        size_usd = r.uniform(10_000, 1_400_000)
        size_base = size_usd / mark
        signed = size_base if side == "long" else -size_base
        upnl = signed * (mark - entry)
        liq = entry * (1 - 0.92 / lev) if side == "long" else entry * (1 + 0.92 / lev)
        asset_positions.append(
            {
                "position": {
                    "token_symbol": coin,
                    "size": f"{signed:.6f}",
                    "position_value_usd": f"{abs(size_usd):.2f}",
                    "entry_price_usd": f"{entry:.6f}",
                    "liquidation_price_usd": f"{liq:.6f}",
                    "leverage_value": lev,
                    "leverage_type": r.choice(["cross", "isolated"]),
                    "margin_used_usd": f"{abs(size_usd) / max(lev, 1):.2f}",
                    "unrealized_pnl_usd": f"{upnl:.2f}",
                },
                "position_type": "oneWay",
            }
        )
    account_value = r.uniform(30_000, 4_200_000)
    return {"data": {"asset_positions": asset_positions, "margin_summary_account_value_usd": f"{account_value:.2f}", "withdrawable_usd": f"{account_value * 0.3:.2f}", "timestamp": int(time.time() * 1000)}}


def _trades(payload: dict) -> dict:
    address = payload["address"]
    r = _rng("trades", address)
    n = r.randint(90, 260)
    win_rate = r.uniform(0.42, 0.78) * (1.08 if _is_smart(address) else 1.0)
    win_rate = min(win_rate, 0.82)
    avg_win = r.uniform(1_500, 22_000)
    avg_loss = r.uniform(900, 9_000)
    now = datetime.now(timezone.utc)
    from_date = payload.get("date", {}).get("from")
    if from_date:
        try:
            start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        except Exception:
            start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=30)
    span = (now - start).total_seconds()
    data = []
    for i in range(n):
        ts = start + timedelta(seconds=r.uniform(0, span))
        win = r.random() < win_rate
        pnl = abs(r.gauss(avg_win, avg_win * 0.55)) if win else -abs(r.gauss(avg_loss, avg_loss * 0.55))
        coin = r.choice(list(COINS))
        side = r.choice(["Long", "Short"])
        val = r.uniform(8_000, 700_000)
        data.append(
            {
                "timestamp": ts.isoformat().replace("+00:00", "Z"),
                "side": side,
                "action": "Close" if r.random() < 0.8 else "Reduce",
                "block_number": r.randint(1, 900_000_000),
                "token_symbol": coin,
                "price": round(COINS[coin] * r.uniform(0.9, 1.1), 6),
                "size": round(val / COINS[coin], 4),
                "value_usd": round(val, 2),
                "start_position": round(val / COINS[coin], 4),
                "closed_pnl": round(pnl, 2),
                "crossed": r.random() < 0.7,
                "fee_usd": round(val * 0.00045, 2),
                "fee_token_symbol": "USDC",
                "transaction_hash": "0x" + hashlib.sha256(f"{address}-{i}".encode()).hexdigest()[:62],
                "user": address,
                "oid": r.randint(10_000_000, 900_000_000),
            }
        )
    data.sort(key=lambda t: t["timestamp"], reverse=True)
    per_page = int((payload.get("pagination") or {}).get("per_page", 1000))
    return {
        "data": data[:per_page],
        "pagination": {"page": 1, "per_page": per_page, "is_last_page": len(data) <= per_page},
    }


def _smart_feed(payload: dict) -> dict:
    r = _rng("smartfeed", int(time.time() // 45))
    n = r.randint(18, 42)
    data = []
    now = datetime.now(timezone.utc)
    for i in range(n):
        address = r.choice(_POOL[:32])
        coin = r.choice(list(COINS))
        action = r.choice(["Buy - Open Long", "Sell - Open Short", "Buy - Add Long", "Sell - Add Short", "Buy - Close Short", "Sell - Close Long"])
        side = "Long" if "Long" in action else "Short"
        val = r.uniform(12_000, 800_000)
        ts = now - timedelta(seconds=r.uniform(0, 3600))
        data.append(
            {
                "trader_address_label": _label_for(address),
                "trader_address": address,
                "token_symbol": coin,
                "side": side,
                "action": action,
                "token_amount": round(val / COINS[coin], 4),
                "price_usd": round(COINS[coin] * (1 + r.uniform(-0.01, 0.01)), 6),
                "value_usd": round(val, 2),
                "type": r.choice(["Market", "Limit"]),
                "block_timestamp": ts.isoformat().replace("+00:00", "Z"),
                "transaction_hash": "0x" + hashlib.sha256(f"sm-{int(time.time() // 45)}-{i}".encode()).hexdigest()[:62],
            }
        )
    data.sort(key=lambda t: t["block_timestamp"], reverse=True)
    per_page = int((payload.get("pagination") or {}).get("per_page", 50))
    return {"data": data[:per_page], "pagination": {"page": 1, "per_page": per_page, "is_last_page": True}}


async def post(endpoint: str, payload: dict) -> dict:
    await asyncio.sleep(random.uniform(0.05, 0.15))
    if endpoint == "/api/v1/perp-leaderboard":
        return _leaderboard(payload)
    if endpoint == "/api/v1/profiler/perp-positions":
        return _positions(payload["address"])
    if endpoint == "/api/v1/profiler/perp-trades":
        return _trades(payload)
    if endpoint == "/api/v1/smart-money/perp-trades":
        return _smart_feed(payload)
    raise ValueError(f"demo: unknown endpoint {endpoint}")
