# PerpPilot — demo video script (45s) & X post draft

Buildathon: Nansen Meridian Buildathon — submit before Sep 27, 23:59 UTC.
Requirements on screen: built with Nansen API, 1,000+ calls (header meter), tag @nansen_ai, repo link.

## Shot list (45–60s)

1. **0:00–0:05** — Terminal: `start.bat` → dashboard loads, LIVE · NANSEN badge visible.
   Voiceover: "PerpPilot — a copy-trading co-pilot for Hyperliquid, built on the Nansen API."
2. **0:05–0:15** — Discover tab: top HL perps traders (Smart HL Perps Trader cohort), 7d PnL + top positions.
   Click Track on 3 traders.
3. **0:15–0:30** — Watchlist: Copy Scores, win rates, profit factors, equity sparklines, risk badges.
   Point at consensus strip: "the whole watchlist's net positioning per coin."
4. **0:30–0:42** — Alerts firing live: trader opens $1M long → toast + sound; confluence alert when
   two tracked traders pile into the same side. Trader drawer: skill-by-coin table.
5. **0:42–0:50** — Smart Money feed + header meter: "1,000+ Nansen API calls, every metric above is Nansen data."
6. **0:50–0:55** — End card: PerpPilot logo + repo link + "Built for the Nansen Meridian Buildathon."

## X post draft

> Copilot for Hyperliquid perps, powered by @nansen_ai.
>
> Tracks the Smart HL Perps Trader cohort, scores who's actually worth copying (win rate, profit factor, risk), and pings you the second they open / flip / get near liquidation — on the dashboard or your phone via webhook.
>
> 1,000+ Nansen API calls, built for the Meridian Buildathon.
>
> Repo: <link> #Hyperliquid #Nansen

## Recording tips

- Temporarily set `POLL_POSITIONS_SEC=60` in `.env` before recording so alerts fire fast; restore after.
- Demo mode (`DEMO_MODE=1`) fires alerts predictably if live markets are quiet — but record the LIVE badge if possible.
