# Hyperframes Composition Brief: PerpPilot

## Objective
Create a short launch-style brag video for PerpPilot, a Hyperliquid copy-trading co-pilot built on the Nansen API.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1600x900
- Duration: 20.5 seconds

## Source Material
- Project root: `C:\Users\najim\Videos\Code\PerpPilot`
- Primary files read: `static/index.html`, `static/style.css`, `static/app.js`, `README.md`, `brag-output/brag-plan.md`
- Product name: PerpPilot
- Tagline / strongest claim: "One whale's ZEC long — $10,934,023 — tracked live."
- Key UI or visual moment to recreate: the dark trading-terminal dashboard — monospace PnL numerals, leaderboard rows with Track buttons, watchlist card with Copy Score / risk badges, alert toasts
- Copy that must appear verbatim:
  - "$10,934,023" / "one whale's ZEC long — tracked live"
  - "HL Perps Whale" · "cosmicvision.eth" · "Uses \"TRADEXYZ1\" HL Referral Code"
  - "CS 59 MODERATE" · "RISK 66 HIGH" · "Win rate 70.2%" · "Profit factor 1457"
  - "Opened SHORT $118K CC (3x)" · "2 tracked traders opened the same side within 15 min"
  - "Every number is Nansen data." · "Built for the Meridian Buildathon"

## Creative Direction
- Tone preset: polished
- Creative direction: "institutional trading-desk reel with a degen wink — the numbers do the bragging"
- Interpretation: fewer scenes, longer holds, confident restraint; monospace numerals and terminal colors; motion is precise (ticks, counters, glows), never chaotic
- Angle: the numbers brag for you — a $10.9M whale position tracked live, scored, and alerted
- Hook: monospace digits count up and slam into $10,934,023 with the caption typing in beneath
- Outro / punchline: "Every number is Nansen data." → logo lockup + buildathon tag
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Unrelated visual redesign

## Visual Identity
- Background: #0b0e14 (terminal grid overlay in rgba(79,140,255,.03), radial blue/violet washes)
- Text: #dbe4f3 (muted #7d8aa3)
- Accent: #4f8cff → #7b5cff gradient; positive #2ecc8f; negative #ff5c6c; warning #f5b04c
- Display font: "Segoe UI", system-ui, sans-serif (bold, tight tracking)
- Body/numerals font: "Cascadia Mono", Consolas, monospace (tabular numerals)
- Visual references from the project: alert toast (colored left border, icon, mono message), leaderboard row (label + addr + green PnL + Track button), watchlist card (badges + 4-stat grid + sparkline), header API-call meter, gradient logo mark (inline SVG recreation)

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook: the whale — 3.5s — digits count up to $10,934,023, caption types in
2. Discover → Track — 4.5s — 3 leaderboard rows slide in; cursor clicks Track; button flips to "Tracking"
3. The scores — 5s — watchlist card: badges pop, 4 stats count up, sparkline draws
4. The alert — 4s — two toasts slam in; feed rows cascade
5. Outro — 3.5s — "Every number is Nansen data." → logo lockup + buildathon tag

## Audio
- Audio role: cinematic support with restrained professional accents
- Audio arc: bed enters under the hook, swells at the whale slam, steady precision through the scores, lifts at the alert, fades out under the logo
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (polished/cinematic pick)
- Music treatment: volume 0.32, starts at 0, timeline-driven fade to 0 across 19.0→20.5s
- Music cue guidance: bundled preset at `brag skill assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.json` (109.96 BPM). Strong-cue locks: **8.74s** (watchlist card reveal), **13.11s** (toast slam), **17.47s** (logo landing). Beat-grid sequences: leaderboard rows at 3.82/4.39/4.91; stat count-ups at 9.29/9.83/10.37/10.93; second toast at 14.20.
- Audio-reactive treatment: subtle — hook number glow may breathe with music RMS/bass; no waveform/equalizer visuals. If extraction is unavailable, document and skip; do not block the render.
- Audio-coupled moments:
  - Scene 1 — digit count-up ticks (keyboard keypresses, randomized, low volume), deep soft hit on the number slam
  - Scene 2 — soft click on Track button click; row arrivals carry the bed (no extra SFX)
  - Scene 3 — counter ticks per stat (sparse, accent first/last)
  - Scene 4 — one crisp announcement cue on toast slam; softer double-tick on second toast
  - Scene 5 — none; music swell and fade carries the logo
- SFX selection guidance: polished tone = minimal but present; prefer `interface/bong_001`, `interface/drop_*`, `ui/mouseclick1`, sparse `keyboard/keypress-*` for the count-up. Nothing aggressive.
- SFX analysis guidance: `<skill-dir>/assets/sfx/sfx-analysis.md`
- Exact SFX choice: Hyperframes chooses filenames/timestamps/volume based on the implemented animation
- Audio files: copy chosen music + SFX into `brag-output/composition/assets/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`, `hyperframes-keyframes`, `hyperframes-cli`. /brag is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow.

Requirements:
- Show at least one real UI, copy, or visual element from the source project (the recreated terminal dashboard scenes)
- Keep all text readable in the final render
- Keep the video within 15-25 seconds (target 20.5s)
- Include the planned music/SFX layer
- Treat /brag audio notes as guidance, not a fixed cue sheet
- Major reveals may move toward nearby strong cues within ~0.15s; smaller entrances within ~0.10s; use only 1-3 strong cue locks (8.74, 13.11, 17.47)
- Audio-reactive: subtle RMS/bass glow on the hook number if extraction available; otherwise document and skip
- Use local assets for audio and runtime/media dependencies
- Run `hyperframes check` before render — it is brag's single gate
