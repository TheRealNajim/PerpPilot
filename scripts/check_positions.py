import asyncio
import json
import sys

sys.path.insert(0, ".")
from app.config import NANSEN_API_KEY
import httpx

ADDR = sys.argv[1] if len(sys.argv) > 1 else "0x382bf59b250a3167a8b86862c2c56cd870353e39"


async def main():
    async with httpx.AsyncClient(timeout=45) as c:
        r = await c.post(
            "https://api.nansen.ai/api/v1/profiler/perp-positions",
            headers={"apikey": NANSEN_API_KEY, "Content-Type": "application/json"},
            json={"address": ADDR},
        )
        print("status:", r.status_code)
        print("credits-used:", r.headers.get("X-Nansen-Credits-Used"))
        body = r.json()
        print("top-level keys:", list(body.keys()))
        data = body.get("data") or {}
        print("data keys:", list(data.keys()) if isinstance(data, dict) else type(data))
        aps = data.get("asset_positions") if isinstance(data, dict) else None
        print("asset_positions count:", len(aps) if aps is not None else None)
        if aps:
            print("first raw entry:")
            print(json.dumps(aps[0], indent=2)[:1800])
        else:
            print("account value:", data.get("margin_summary_account_value_usd") if isinstance(data, dict) else None)


asyncio.run(main())
