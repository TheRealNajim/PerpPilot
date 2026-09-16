import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import httpx

from . import demo
from .config import AUTO_PAUSE_CALLS, DEMO_MODE, NANSEN_API_KEY, POLL_LEADERBOARD_SEC, POLL_POSITIONS_SEC, POLL_SMART_SEC, POLL_TRADES_SEC, STATE_DIR
from .nansen import NansenClient

log = logging.getLogger("perppilot.engine")

WATCHLIST_FILE = STATE_DIR / "watchlist.json"
PAUSED_FILE = STATE_DIR / "paused.json"
SETTINGS_FILE = STATE_DIR / "settings.json"

EP_LEADERBOARD = "/api/v1/perp-leaderboard"
EP_POSITIONS = "/api/v1/profiler/perp-positions"
EP_TRADES = "/api/v1/profiler/perp-trades"
EP_SMART = "/api/v1/smart-money/perp-trades"

SMART_LABELS = ["Smart HL Perps Trader"]


def now_utc():
    return datetime.now(timezone.utc)


def fmt_usd(x: float) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"{sign}${x/1_000:.1f}K"
    return f"{sign}${x:.2f}"


def normalize_position(asset_position: dict) -> dict | None:
    pos = asset_position.get("position") or {}
    try:
        size = float(pos.get("size") or 0)
        entry = float(pos.get("entry_price_usd") or 0)
        upnl = float(pos.get("unrealized_pnl_usd") or 0)
        liq = float(pos.get("liquidation_price_usd") or 0)
        value = abs(float(pos.get("position_value_usd") or 0))
        margin_used = float(pos.get("margin_used_usd") or 0)
        lev = int(pos.get("leverage_value") or 0)
    except (TypeError, ValueError):
        return None
    if not pos.get("token_symbol"):
        return None
    side = "short" if size < 0 else "long"
    raw_mark = entry + (upnl / size if size else 0)
    if entry > 0 and not (0 < raw_mark < entry * 100):
        raw_mark = entry
    mark = raw_mark if raw_mark > 0 else None
    liq_dist = None
    if liq > 0 and mark and value >= 100:
        liq_dist = abs(mark - liq) / mark
    return {
        "coin": pos["token_symbol"],
        "side": side,
        "size": abs(size),
        "value": value,
        "entry": entry,
        "mark": mark,
        "liq": liq,
        "liq_dist": liq_dist,
        "leverage": lev,
        "leverage_type": pos.get("leverage_type", "cross"),
        "margin_used": margin_used,
        "upnl": upnl,
    }


def compute_metrics(trades: list[dict]) -> dict:
    closed = []
    for t in trades:
        try:
            pnl = float(t.get("closed_pnl") or 0)
        except (TypeError, ValueError):
            continue
        if pnl == 0:
            continue
        closed.append((t, pnl))
    wins = [p for _, p in closed if p > 0]
    losses = [p for _, p in closed if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    total = len(closed)
    fees = 0.0
    for t, _ in closed:
        try:
            fees += float(t.get("fee_usd") or 0)
        except (TypeError, ValueError):
            pass
    curve = []
    cum = 0.0
    for t, p in sorted(closed, key=lambda x: x[0].get("timestamp", "")):
        cum += p
        curve.append({"t": t.get("timestamp"), "cum_pnl": round(cum, 2)})
    return {
        "closed_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / total, 4) if total else None,
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else (None if not gross_win else 99.0),
        "avg_win": round(gross_win / len(wins), 2) if wins else None,
        "avg_loss": round(gross_loss / len(losses), 2) if losses else None,
        "total_closed_pnl": round(sum(p for _, p in closed), 2),
        "fees_usd": round(fees, 2),
        "best_trade": round(max((p for _, p in closed), default=0), 2),
        "worst_trade": round(min((p for _, p in closed), default=0), 2),
        "equity_curve": curve,
    }


def compute_risk(positions: list[dict], account_value: float) -> dict:
    if not positions:
        return {"score": 0, "level": "LOW", "max_leverage": 0, "min_liq_dist": None, "concentration": 0, "margin_usage": 0}
    max_lev = max(p["leverage"] for p in positions)
    liq_dists = [p["liq_dist"] for p in positions if p["liq_dist"] is not None]
    min_liq = min(liq_dists) if liq_dists else None
    av = account_value or 0
    largest = max(p["value"] for p in positions)
    total_notional = sum(p["value"] for p in positions)
    margin_used = sum(p["margin_used"] for p in positions)
    conc = min(20, largest / av * 20) if av else 10
    margin = min(25, margin_used / av * 25) if av else 10
    lev_score = min(30, max_lev * 2.5)
    liq_score = 25 * max(0, 1 - min_liq) if min_liq is not None else 10
    score = round(min(100, lev_score + liq_score + conc + margin))
    level = "HIGH" if score >= 65 else ("MEDIUM" if score >= 35 else "LOW")
    return {
        "score": score,
        "level": level,
        "max_leverage": max_lev,
        "min_liq_dist": round(min_liq, 4) if min_liq is not None else None,
        "concentration": round(largest / av, 4) if av else None,
        "margin_usage": round(margin_used / av, 4) if av else None,
        "total_notional": round(total_notional, 2),
    }


def compute_copy_score(win_rate, pf, closed_trades, lb_roi_7d, risk_score) -> dict | None:
    if win_rate is None or pf is None:
        return None
    score = 0.0
    score += min(max(win_rate, 0), 1) * 30
    score += min(pf, 3) / 3 * 25
    score += min(closed_trades or 0, 100) / 100 * 15
    score += min(max(lb_roi_7d or 0, 0), 2) / 2 * 15
    score -= (risk_score / 100) * 15
    score = round(max(0, min(100, score)))
    tier = "ELITE" if score >= 75 else ("STRONG" if score >= 60 else ("MODERATE" if score >= 45 else "WEAK"))
    return {"score": score, "tier": tier}


def coin_skills(trades: list[dict]) -> list[dict]:
    agg: dict[str, dict] = {}
    for t in trades:
        try:
            pnl = float(t.get("closed_pnl") or 0)
        except (TypeError, ValueError):
            continue
        if pnl == 0:
            continue
        coin = t.get("token_symbol") or "?"
        a = agg.setdefault(coin, {"coin": coin, "trades": 0, "wins": 0, "pnl": 0.0})
        a["trades"] += 1
        a["wins"] += 1 if pnl > 0 else 0
        a["pnl"] += pnl
    rows = []
    for v in agg.values():
        rows.append(
            {
                "coin": v["coin"],
                "trades": v["trades"],
                "win_rate": round(v["wins"] / v["trades"], 3),
                "pnl": round(v["pnl"], 2),
            }
        )
    rows.sort(key=lambda x: -x["trades"])
    return rows[:8]


class Engine:
    def __init__(self):
        self.client = NansenClient()
        self.leaderboard: list[dict] = []
        self.leaderboard_updated: str | None = None
        self.watchlist: dict[str, dict] = {}
        self.snapshots: dict[str, dict[str, dict]] = {}
        self.account_values: dict[str, float] = {}
        self.metrics: dict[str, dict] = {}
        self.trades: dict[str, list[dict]] = {}
        self.positions: dict[str, list[dict]] = {}
        self.updated_at: dict[str, str] = {}
        self.alerts: deque = deque(maxlen=400)
        self.smart_trades: deque = deque(maxlen=400)
        self._smart_seen: set = set()
        self._rr_index = 0
        self._confluence_sent: dict = {}
        self.api_errors = 0
        self.last_error: str | None = None
        self.paused = False
        self.settings: dict = {}
        self._task = None
        self.started = time.time()

    # ---------- pause ----------

    def _load_paused(self):
        if PAUSED_FILE.exists():
            try:
                self.paused = bool(json.loads(PAUSED_FILE.read_text(encoding="utf-8")).get("paused"))
            except Exception:
                pass

    def _load_settings(self):
        if SETTINGS_FILE.exists():
            try:
                self.settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.settings = {}

    def set_settings(self, webhook_url: str | None, telegram_chat_id: str | None):
        if webhook_url is not None:
            self.settings["webhook_url"] = webhook_url.strip()
        if telegram_chat_id is not None:
            self.settings["telegram_chat_id"] = telegram_chat_id.strip()
        try:
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except Exception:
            pass

    def set_paused(self, value: bool):
        self.paused = bool(value)
        try:
            PAUSED_FILE.write_text(json.dumps({"paused": self.paused}), encoding="utf-8")
        except Exception:
            pass
        log.info("API polling %s", "PAUSED" if self.paused else "RESUMED")

    async def _pause_gate(self):
        while self.paused:
            await asyncio.sleep(3)

    # ---------- persistence ----------

    def _load_watchlist(self):
        if WATCHLIST_FILE.exists():
            try:
                items = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
                for item in items:
                    addr = item.get("address")
                    if addr:
                        self.watchlist[addr] = item
            except Exception:
                pass

    def _save_watchlist(self):
        try:
            WATCHLIST_FILE.write_text(
                json.dumps(list(self.watchlist.values()), indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ---------- api ----------

    async def _post(self, endpoint: str, payload: dict) -> dict:
        try:
            if DEMO_MODE:
                self.client.record_call(endpoint)
                resp = await demo.post(endpoint, payload)
            else:
                resp = await self.client.post(endpoint, payload)
        except Exception as e:
            self.api_errors += 1
            self.last_error = f"{endpoint}: {type(e).__name__} {e}"
            raise
        if AUTO_PAUSE_CALLS and not DEMO_MODE and not self.paused and self.client.total_calls >= AUTO_PAUSE_CALLS:
            self.set_paused(True)
            self.add_alert(
                "PAUSED", "", "PerpPilot",
                f"Auto-paused at {self.client.total_calls} API calls (target {AUTO_PAUSE_CALLS})",
                "warn",
            )
        return resp

    def _maybe_confluence(self, address: str, label: str, coin: str, side: str):
        cutoff = now_utc() - timedelta(minutes=15)
        distinct = {a["address"] for a in self.alerts if a["type"] == "OPEN" and a.get("coin") == coin and a.get("side") == side and a["at"] >= cutoff.isoformat()}
        distinct.add(address)
        key = (coin, side)
        last_sent = self._confluence_sent.get(key)
        if last_sent and time.time() - last_sent < 3600:
            return
        if len(distinct) >= 2:
            self._confluence_sent[key] = time.time()
            self.add_alert(
                "CONFLUENCE", address, label,
                f"{len(distinct)} tracked traders opened {side.upper()} {coin} within 15 min — flock signal",
                "warn", {"coin": coin, "side": side},
            )

    # ---------- alerts ----------

    def add_alert(self, atype: str, address: str, label: str, message: str, severity: str = "info", extra: dict | None = None):
        entry = {
            "id": f"{time.time_ns()}",
            "type": atype,
            "address": address,
            "label": label,
            "message": message,
            "severity": severity,
            "at": now_utc().isoformat(),
            **(extra or {}),
        }
        self.alerts.appendleft(entry)
        self._dispatch_webhook(entry)

    def _dispatch_webhook(self, alert: dict):
        url = self.settings.get("webhook_url")
        if not url:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        asyncio.create_task(self._send_webhook(url, alert))

    async def _send_webhook(self, url: str, alert: dict):
        text = f"PerpPilot [{alert['type']}] {alert['label']}: {alert['message']}"
        payload = {"text": text}
        if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
            payload = {"content": text, "username": "PerpPilot"}
        elif "api.telegram.org" in url:
            chat_id = self.settings.get("telegram_chat_id")
            if not chat_id:
                return
            payload = {"chat_id": chat_id, "text": text}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                await c.post(url, json=payload)
        except Exception:
            pass

    def _diff_positions(self, address: str, label: str, prev: dict[str, dict], curr: dict[str, dict]):
        for coin, cur in curr.items():
            old = prev.get(coin)
            if old is None:
                self.add_alert(
                    "OPEN", address, label,
                    f"Opened {cur['side'].upper()} {fmt_usd(cur['value'])} {coin} @ {cur['entry']:,.4f} ({cur['leverage']}x)",
                    "trade", {"coin": coin, "side": cur["side"]},
                )
                self._maybe_confluence(address, label, coin, cur["side"])
            else:
                if old["side"] != cur["side"]:
                    self.add_alert(
                        "FLIP", address, label,
                        f"Flipped {coin} from {old['side'].upper()} to {cur['side'].upper()} ({fmt_usd(cur['value'])})",
                        "warn", {"coin": coin, "side": cur["side"]},
                    )
                elif old["size"] > 0:
                    ratio = cur["size"] / old["size"]
                    if ratio >= 1.2:
                        self.add_alert(
                            "INCREASE", address, label,
                            f"Added to {cur['side'].upper()} {coin}: {fmt_usd(old['value'])} -> {fmt_usd(cur['value'])}",
                            "trade", {"coin": coin, "side": cur["side"]},
                        )
                    elif ratio <= 0.8:
                        self.add_alert(
                            "DECREASE", address, label,
                            f"Reduced {cur['side'].upper()} {coin}: {fmt_usd(old['value'])} -> {fmt_usd(cur['value'])}",
                            "info", {"coin": coin, "side": cur["side"]},
                        )
                prev_near = old.get("liq_dist") is not None and old["liq_dist"] < 0.06
                if cur["liq_dist"] is not None and cur["liq_dist"] < 0.06 and not prev_near:
                    self.add_alert(
                        "NEAR_LIQ", address, label,
                        f"{coin} {cur['side'].upper()} {cur['leverage']}x only {cur['liq_dist']*100:.1f}% from liquidation",
                        "danger", {"coin": coin, "side": cur["side"]},
                    )
        for coin, old in prev.items():
            if coin not in curr:
                pnl_txt = f" (last uPnL {fmt_usd(old['upnl'])})" if old.get("upnl") else ""
                self.add_alert("CLOSE", address, label, f"Closed {old['side'].upper()} {coin} {fmt_usd(old['value'])}{pnl_txt}", "trade", {"coin": coin, "side": old["side"]})

    # ---------- loops ----------

    async def start(self):
        self._load_paused()
        self._load_settings()
        self._load_watchlist()
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        await asyncio.gather(
            self._leaderboard_loop(),
            self._positions_loop(),
            self._trades_loop(),
            self._smart_loop(),
        )

    async def _leaderboard_loop(self):
        while True:
            await self._pause_gate()
            try:
                to_d = now_utc().date()
                from_d = to_d - timedelta(days=7)
                payload = {
                    "date": {"from": from_d.isoformat(), "to": to_d.isoformat()},
                    "pagination": {"page": 1, "per_page": 50},
                    "filters": {"include_smart_money_labels": SMART_LABELS},
                    "order_by": [{"field": "total_pnl", "direction": "DESC"}],
                }
                try:
                    resp = await self._post(EP_LEADERBOARD, payload)
                    rows = resp.get("data", [])
                except Exception:
                    if DEMO_MODE:
                        raise
                    payload["filters"] = {}
                    resp = await self._post(EP_LEADERBOARD, payload)
                    rows = resp.get("data", [])
                self.leaderboard = rows
                self.leaderboard_updated = now_utc().isoformat()
                log.info("leaderboard refreshed: %d traders", len(rows))
            except Exception:
                log.exception("leaderboard refresh failed")
            await asyncio.sleep(POLL_LEADERBOARD_SEC)

    async def _positions_loop(self):
        await asyncio.sleep(2)
        while True:
            await self._pause_gate()
            try:
                addresses = list(self.watchlist.keys())
                for addr in addresses:
                    await self._refresh_positions(addr)
                    await asyncio.sleep(0.4)
            except Exception:
                log.exception("positions loop error")
            await asyncio.sleep(POLL_POSITIONS_SEC)

    async def _refresh_positions(self, address: str):
        label = self.watchlist.get(address, {}).get("label", address[:10])
        try:
            resp = await self._post(EP_POSITIONS, {"address": address})
        except Exception:
            log.exception("positions fetch failed for %s", address)
            return
        data = resp.get("data", {})
        raw = data.get("asset_positions") or data.get("assetPositions") or []
        curr: dict[str, dict] = {}
        for ap in raw:
            norm = normalize_position(ap)
            if norm:
                curr[norm["coin"]] = norm
        try:
            av = float(data.get("margin_summary_account_value_usd") or 0)
        except (TypeError, ValueError):
            av = 0
        self.account_values[address] = av
        prev = self.snapshots.get(address, {})
        if prev:
            self._diff_positions(address, label, prev, curr)
        self.snapshots[address] = curr
        self.positions[address] = sorted(curr.values(), key=lambda p: -p["value"])
        self.updated_at[address] = now_utc().isoformat()

    async def _trades_loop(self):
        await asyncio.sleep(6)
        while True:
            await self._pause_gate()
            try:
                addresses = list(self.watchlist.keys())
                if addresses:
                    addr = addresses[self._rr_index % len(addresses)]
                    self._rr_index += 1
                    await self._refresh_trades(addr)
            except Exception:
                log.exception("trades loop error")
            await asyncio.sleep(POLL_TRADES_SEC)

    async def _refresh_trades(self, address: str):
        to_d = now_utc()
        from_d = to_d - timedelta(days=30)
        payload = {
            "address": address,
            "date": {"from": from_d.isoformat(), "to": to_d.isoformat()},
            "pagination": {"page": 1, "per_page": 500},
            "order_by": [{"field": "timestamp", "direction": "DESC"}],
        }
        try:
            resp = await self._post(EP_TRADES, payload)
        except Exception:
            log.exception("trades fetch failed for %s", address)
            return
        trades = resp.get("data", [])
        self.trades[address] = trades
        self.metrics[address] = compute_metrics(trades)

    async def _smart_loop(self):
        await asyncio.sleep(4)
        while True:
            await self._pause_gate()
            try:
                payload = {
                    "lookback_hours": 2,
                    "pagination": {"page": 1, "per_page": 60},
                    "order_by": [{"field": "block_timestamp", "direction": "DESC"}],
                }
                resp = await self._post(EP_SMART, payload)
                watched = set(self.watchlist.keys())
                for t in resp.get("data", []):
                    key = (t.get("transaction_hash"), t.get("trader_address"), t.get("token_symbol"))
                    if key in self._smart_seen:
                        continue
                    self._smart_seen.add(key)
                    t["watched"] = t.get("trader_address") in watched
                    self.smart_trades.appendleft(t)
                if len(self._smart_seen) > 4000:
                    self._smart_seen = set(list(self._smart_seen)[-2000:])
            except Exception:
                log.exception("smart money feed error")
            await asyncio.sleep(POLL_SMART_SEC)

    # ---------- public api ----------

    def add_to_watchlist(self, address: str, label: str | None = None):
        if address not in self.watchlist:
            lb = next((r for r in self.leaderboard if r["trader_address"] == address), None)
            self.watchlist[address] = {
                "address": address,
                "label": label or (lb or {}).get("trader_address_label") or f"{address[:8]}…{address[-6:]}",
                "added_at": now_utc().isoformat(),
                "leaderboard": lb,
            }
            self._save_watchlist()

    def remove_from_watchlist(self, address: str):
        self.watchlist.pop(address, None)
        self.snapshots.pop(address, None)
        self.metrics.pop(address, None)
        self.trades.pop(address, None)
        self.positions.pop(address, None)
        self._save_watchlist()

    @staticmethod
    def _downsample(points: list, n: int = 48) -> list:
        if len(points) <= n:
            return points
        step = len(points) / n
        return [points[int(i * step)] for i in range(n)]

    def trader_summary(self, address: str) -> dict:
        w = self.watchlist.get(address, {})
        m = self.metrics.get(address) or {}
        risk = compute_risk(self.positions.get(address, []), self.account_values.get(address, 0))
        lb = w.get("leaderboard") or {}
        curve = m.get("equity_curve") or []
        equity = [p["cum_pnl"] for p in self._downsample(curve)]
        return {
            "address": address,
            "label": w.get("label", address),
            "copy_score": compute_copy_score(
                m.get("win_rate"), m.get("profit_factor"), m.get("closed_trades", 0), lb.get("roi"), risk["score"]
            ),
            "win_rate": m.get("win_rate"),
            "profit_factor": m.get("profit_factor"),
            "total_closed_pnl": m.get("total_closed_pnl"),
            "closed_trades": m.get("closed_trades", 0),
            "avg_win": m.get("avg_win"),
            "avg_loss": m.get("avg_loss"),
            "risk": risk,
            "open_positions": len(self.positions.get(address, [])),
            "total_notional": risk.get("total_notional", 0),
            "account_value": self.account_values.get(address),
            "lb_pnl_7d": lb.get("total_pnl"),
            "lb_roi_7d": lb.get("roi"),
            "lb_volume_7d": lb.get("volume_usd"),
            "updated_at": self.updated_at.get(address),
            "equity": equity,
            "has_metrics": bool(m),
        }

    def consensus(self) -> list[dict]:
        agg: dict[str, dict] = {}
        for positions in self.positions.values():
            for p in positions:
                a = agg.setdefault(
                    p["coin"],
                    {"coin": p["coin"], "longs": 0, "shorts": 0, "long_notional": 0.0, "short_notional": 0.0},
                )
                if p["side"] == "long":
                    a["longs"] += 1
                    a["long_notional"] += p["value"]
                else:
                    a["shorts"] += 1
                    a["short_notional"] += p["value"]
        rows = sorted(agg.values(), key=lambda x: -(x["long_notional"] + x["short_notional"]))
        for r in rows:
            r["traders"] = r["longs"] + r["shorts"]
            r["net"] = round(r["long_notional"] - r["short_notional"], 2)
        return rows

    def trader_detail(self, address: str) -> dict:
        m = self.metrics.get(address) or {}
        return {
            **self.trader_summary(address),
            "positions": self.positions.get(address, []),
            "metrics": m or None,
            "coin_skills": coin_skills(self.trades.get(address) or []),
            "recent_trades": (self.trades.get(address) or [])[:40],
            "alerts": [a for a in self.alerts if a["address"] == address][:40],
        }

    def basket(self) -> dict:
        pnl = 0.0
        trades = 0
        wins = 0
        for ts in self.trades.values():
            for t in ts:
                try:
                    p = float(t.get("closed_pnl") or 0)
                except (TypeError, ValueError):
                    continue
                if p == 0:
                    continue
                pnl += p
                trades += 1
                wins += 1 if p > 0 else 0
        return {
            "traders": len(self.watchlist),
            "closed_trades": trades,
            "total_closed_pnl": round(pnl, 2),
            "win_rate": round(wins / trades, 3) if trades else None,
        }

    def stats(self) -> dict:
        return {
            "demo_mode": DEMO_MODE,
            "api_key_set": bool(NANSEN_API_KEY),
            "total_calls": self.client.total_calls,
            "calls_by_endpoint": dict(self.client.calls_by_endpoint),
            "credits_remaining": self.client.credits_remaining,
            "out_of_credits": self.client.out_of_credits and not DEMO_MODE,
            "api_errors": self.api_errors,
            "last_error": self.last_error,
            "watchlist_size": len(self.watchlist),
            "poll_intervals": {
                "positions_sec": POLL_POSITIONS_SEC,
                "trades_sec": POLL_TRADES_SEC,
                "smart_sec": POLL_SMART_SEC,
                "leaderboard_sec": POLL_LEADERBOARD_SEC,
            },
            "alerts": len(self.alerts),
            "smart_trades": len(self.smart_trades),
            "uptime_sec": round(time.time() - self.started),
            "paused": self.paused,
        }


engine = Engine()
