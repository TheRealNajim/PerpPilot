import asyncio
import json
import logging

import httpx

from .config import NANSEN_API_KEY, STATE_DIR

log = logging.getLogger("perppilot.nansen")

BASE_URL = "https://api.nansen.ai"
CALLS_FILE = STATE_DIR / "calls.json"


class NansenClient:
    def __init__(self):
        self.total_calls = 0
        self.calls_by_endpoint = {}
        self.credits_remaining = None
        self.out_of_credits = False
        self._load()
        self._client = httpx.AsyncClient(timeout=45.0)

    def _load(self):
        if CALLS_FILE.exists():
            try:
                data = json.loads(CALLS_FILE.read_text(encoding="utf-8"))
                self.total_calls = int(data.get("total", 0))
                self.calls_by_endpoint = data.get("endpoints", {})
            except Exception:
                pass

    def _save(self):
        try:
            CALLS_FILE.write_text(
                json.dumps({"total": self.total_calls, "endpoints": self.calls_by_endpoint}),
                encoding="utf-8",
            )
        except Exception:
            pass

    def record_call(self, endpoint: str):
        self.total_calls += 1
        self.calls_by_endpoint[endpoint] = self.calls_by_endpoint.get(endpoint, 0) + 1
        if self.total_calls % 10 == 0:
            self._save()

    async def close(self):
        self._save()
        await self._client.aclose()

    async def post(self, endpoint: str, payload: dict) -> dict:
        headers = {"Content-Type": "application/json", "apikey": NANSEN_API_KEY}
        for attempt in range(3):
            self.record_call(endpoint)
            resp = await self._client.post(f"{BASE_URL}{endpoint}", headers=headers, json=payload)
            remaining = resp.headers.get("X-Nansen-Credits-Remaining")
            if remaining is not None:
                try:
                    self.credits_remaining = float(remaining)
                except ValueError:
                    pass
            if resp.status_code == 403:
                self.out_of_credits = True
            elif resp.status_code < 400:
                self.out_of_credits = False
            if resp.status_code == 429:
                retry_after = 5.0
                try:
                    retry_after = float(resp.json().get("retry_after", 5))
                except Exception:
                    retry_after = float(resp.headers.get("Retry-After", 5))
                log.warning("429 on %s, retrying in %.0fs", endpoint, retry_after)
                await asyncio.sleep(min(retry_after, 60.0))
                continue
            if resp.status_code >= 500:
                await asyncio.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()
