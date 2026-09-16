import asyncio
import sys

sys.path.insert(0, ".")
from app.config import NANSEN_API_KEY
import httpx


async def main():
    async with httpx.AsyncClient(timeout=45) as c:
        for ep, payload in [
            ("/api/v1/profiler/perp-positions", {"address": "0x382bf59b250a3167a8b86862c2c56cd870353e39"}),
            ("/api/v1/perp-leaderboard", {"date": {"from": "2026-09-09", "to": "2026-09-16"}}),
        ]:
            r = await c.post(
                f"https://api.nansen.ai{ep}",
                headers={"apikey": NANSEN_API_KEY, "Content-Type": "application/json"},
                json=payload,
            )
            print(f"{ep} -> {r.status_code}")
            print("  credits-remaining:", r.headers.get("X-Nansen-Credits-Remaining"))
            print("  credits-used:", r.headers.get("X-Nansen-Credits-Used"))
            body = r.json()
            err = body.get("error") or body.get("detail")
            print("  body:", str(err)[:300])


asyncio.run(main())
