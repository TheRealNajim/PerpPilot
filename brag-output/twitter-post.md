# Twitter post kit — PerpPilot brag video

## Option A — Single tweet (fits 280 chars)

PerpPilot: a copy-trading co-pilot for Hyperliquid perps, built on the @nansen_ai API.

It finds the smart money, scores who's actually worth copying, and pings you the second a whale blinks.

One whale in my watchlist: long $10.9M of ZEC. Tracked live.

Repo + demo below. #MeridianBuildathon

---

## Option B — Long post (Premium / X long-form)

Built a thing for the @nansen_ai Meridian Buildathon: PerpPilot — a copy-trading co-pilot for Hyperliquid perps.

The idea: Nansen already labels the smart money. PerpPilot turns that into a terminal you can actually follow.

What it does:

- Discovers the top HL perps traders (7d, Smart HL Perps Trader cohort)
- Scores every tracked wallet: 30d win rate, profit factor, equity curve, and a 0-100 Copy Score
- Live risk scoring — leverage, liquidation proximity, concentration, margin
- Alerts the second a tracked whale opens, closes, flips, adds, reduces — or drifts near liquidation
- Flock signal: when 2+ tracked traders pile into the same side within 15 minutes, you hear about it
- Discord/Telegram webhooks so the alerts reach your phone

Right now it's watching a wallet running a $10.9M ZEC long with +$5.8M unrealized. If that position moves, I know within seconds.

Stack: Python/FastAPI polling engine + vanilla JS terminal UI, on the Nansen API (leaderboard, profiler positions/trades, smart money feed).

Repo: https://github.com/TheRealNajim/PerpPilot

---

## Option C — Thread (main tweet + 3 replies)

**1/ (main = Option A)**

**2/** How it works:
Discover tab ranks the top Hyperliquid perps traders from Nansen's Smart HL Perps Trader cohort. One click tracks any wallet. PerpPilot then pulls 30d trade history and computes win rate, profit factor and a Copy Score — plus a live risk score from leverage, liquidation distance and margin.

**3/** The payoff is the alert layer: every 60s it diffs live positions and fires on OPEN / CLOSE / FLIP / adds / reductions / near-liquidation. When 2+ tracked traders take the same side within 15 minutes you get a flock signal — on screen or via Telegram/Discord webhook.

**4/** Built for the Meridian Buildathon. Full source + setup:
https://github.com/TheRealNajim/PerpPilot
Thanks to @nansen_ai for the data layer.

---

## Posting notes

- Attach brag-output/brag.mp4 (native upload, not a link) — the poster frame is baked in
- Tag @nansen_ai in the main tweet (buildathon requirement)
- Reply to your own tweet with docs/demo-video.mp4 (the 63s narrated screen demo) as a follow-up
- Repo link goes in the main tweet or first reply (buildathon requirement)
- Suggested timing: after the API call counter crosses 1,000 (it auto-pauses there) so "1,000+ API calls" is true if you want to claim it — or keep the current wording, which doesn't claim a number
