const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const state = {
  tab: "discover",
  leaderboard: [],
  watchlist: [],
  alerts: [],
  smartTrades: [],
  lastAlertId: null,
  drawerAddr: null,
  chart: null,
  tracked: new Set(),
  paused: false,
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function shortAddr(a) {
  return a ? a.slice(0, 6) + "…" + a.slice(-4) : "";
}
function fmtUsd(x, compact = true) {
  if (x == null || isNaN(x)) return "—";
  const sign = x < 0 ? "-" : "";
  const v = Math.abs(x);
  if (compact) {
    if (v >= 1e6) return `${sign}$${(v / 1e6).toFixed(2)}M`;
    if (v >= 1e3) return `${sign}$${(v / 1e3).toFixed(1)}K`;
  }
  return `${sign}$${v.toFixed(2)}`;
}
function fmtPct(x, digits = 1) {
  if (x == null || isNaN(x)) return "—";
  return `${(x * 100).toFixed(digits)}%`;
}
function signedClass(x) {
  return x > 0 ? "pos" : x < 0 ? "neg" : "";
}
function relTime(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
function sideCls(side) {
  return side === "long" || side === "Long" ? "side-long" : "side-short";
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

/* ---------- tabs ---------- */
$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => b.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
    state.tab = btn.dataset.tab;
    if (state.tab === "discover") renderLeaderboard();
    if (state.tab === "watchlist") renderWatchlist();
    if (state.tab === "alerts") renderAlerts();
    if (state.tab === "feed") renderFeed();
  });
});

/* ---------- leaderboard ---------- */
function renderLeaderboard() {
  const q = ($("#lb-search").value || "").toLowerCase();
  const openOnly = $("#lb-open-only").checked;
  const tbody = $("#lb-table tbody");
  const rows = state.leaderboard.filter((r) => {
    const hay = `${r.trader_address_label || ""} ${r.trader_address}`.toLowerCase();
    if (q && !hay.includes(q)) return false;
    if (openOnly && !(r.top_positions || []).length) return false;
    return true;
  });
  tbody.innerHTML = rows
    .map((r, i) => {
      const isTracked = state.tracked.has(r.trader_address);
      const chips = (r.top_positions || [])
        .slice(0, 3)
        .map((p) => `<span class="mono">${esc(p.coin)} <span class="${sideCls(p.side)}">${p.side === "long" ? "L" : "S"}</span> ${fmtUsd(p.position_value_usd)}</span>`)
        .join(" · ");
      return `<tr>
        <td class="dim">${i + 1}</td>
        <td><b>${esc(r.trader_address_label || shortAddr(r.trader_address))}</b><br><span class="mono dim addr">${shortAddr(r.trader_address)}</span></td>
        <td class="num ${signedClass(r.total_pnl)}">${fmtUsd(r.total_pnl)}</td>
        <td class="num ${signedClass(r.roi)}">${fmtPct(r.roi)}</td>
        <td class="num">${fmtUsd(r.volume_usd)}</td>
        <td class="num dim">${r.total_trades ?? "—"}</td>
        <td class="num">${fmtUsd(r.account_value)}</td>
        <td>${chips || '<span class="dim">—</span>'}</td>
        <td>${isTracked ? '<button class="track-btn tracked">Tracking</button>' : `<button class="track-btn" data-addr="${r.trader_address}">Track</button>`}</td>
      </tr>`;
    })
    .join("");
  tbody.querySelectorAll(".track-btn[data-addr]").forEach((b) =>
    b.addEventListener("click", () => trackTrader(b.dataset.addr))
  );
}
$("#lb-search").addEventListener("input", renderLeaderboard);
$("#lb-open-only").addEventListener("change", renderLeaderboard);

async function trackTrader(addr) {
  if (state.tracked.has(addr)) return;
  try {
    await api("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ address: addr }),
    });
    state.tracked.add(addr);
    renderLeaderboard();
    toast(`Tracking ${shortAddr(addr)} — fetching positions & history`, "info");
  } catch (e) {
    toast(`Failed to track: ${e.message}`, "danger");
  }
}

/* ---------- watchlist ---------- */
function sparkline(values) {
  if (!values || values.length < 2) return "";
  const w = 280;
  const hgt = 34;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values
    .map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(hgt - 3 - ((v - min) / range) * (hgt - 6)).toFixed(1)}`)
    .join(" ");
  const color = values[values.length - 1] >= values[0] ? "var(--green)" : "var(--red)";
  return `<svg class="spark" viewBox="0 0 ${w} ${hgt}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
}

function renderConsensus(rows) {
  const box = $("#consensus");
  if (!rows || !rows.length) {
    box.innerHTML = `<span class="muted" style="font-size:12px">No open positions across tracked traders yet.</span>`;
    return;
  }
  box.innerHTML = rows
    .map(
      (r) => `<span class="chip"><b>${esc(r.coin)}</b>
        <span class="side-long">▲${r.longs}</span><span class="side-short">▼${r.shorts}</span>
        <span class="${signedClass(r.net)}">${fmtUsd(r.net)}</span></span>`
    )
    .join("");
}

function renderBasket(b) {
  const box = $("#basket");
  if (!b || !b.closed_trades) {
    box.innerHTML = `<span class="muted" style="font-size:12px">Copy basket: collecting trade history for tracked traders…</span>`;
    return;
  }
  box.innerHTML = `<span class="chip"><b>COPY BASKET · 30d</b>
    <span class="${signedClass(b.total_closed_pnl)}">${fmtUsd(b.total_closed_pnl)}</span> closed PnL
    <span class="dim">across ${b.closed_trades} trades · ${fmtPct(b.win_rate)} blend win rate · ${b.traders} traders</span>
    <span class="dim" title="Naive estimate: sums each tracked trader's actual closed PnL over 30d; not position-sized">(naive estimate)</span></span>`;
}

function renderWatchlist() {
  const grid = $("#watch-grid");
  const csScore = (t) => (t.copy_score ? t.copy_score.score : -1);
  const list = [...state.watchlist].sort((a, b) => csScore(b) - csScore(a));
  if (!list.length) {
    grid.innerHTML = `<div class="muted" style="padding:30px">No traders tracked yet — pick some from the Discover tab.</div>`;
    return;
  }
  grid.innerHTML = list
    .map((t) => {
      const wr = t.win_rate;
      const pf = t.profit_factor;
      const cs = t.copy_score;
      return `<div class="card" data-addr="${t.address}">
        <div class="card-top">
          <div>
            <h3>${esc(t.label)}</h3>
            <div class="mono dim addr">${shortAddr(t.address)}</div>
          </div>
          <div class="badges">
            ${cs ? `<span class="tier-badge ${TIER_CLASS[cs.tier]}" title="Copy Score">CS ${cs.score} ${cs.tier}</span>` : ""}
            <span class="risk-badge risk-${t.risk.level}">RISK ${t.risk.score}</span>
          </div>
        </div>
        <div class="card-stats">
          <div class="card-stat"><div class="label">Win rate</div><div class="value">${fmtPct(wr)}</div></div>
          <div class="card-stat"><div class="label">Profit factor</div><div class="value ${pf != null && pf >= 1 ? "pos" : "neg"}">${pf ?? "—"}</div></div>
          <div class="card-stat"><div class="label">30d closed PnL</div><div class="value ${signedClass(t.total_closed_pnl)}">${fmtUsd(t.total_closed_pnl)}</div></div>
          <div class="card-stat"><div class="label">Open pos</div><div class="value">${t.open_positions} <span class="dim">/ ${fmtUsd(t.total_notional)}</span></div></div>
        </div>
        <div class="card-foot">
          <span>7d: <span class="${signedClass(t.lb_pnl_7d)}">${fmtUsd(t.lb_pnl_7d)}</span> · ROI ${fmtPct(t.lb_roi_7d)}</span>
          <span>${t.updated_at ? relTime(t.updated_at) : "loading…"}</span>
        </div>
        ${sparkline(t.equity)}
      </div>`;
    })
    .join("");
  grid.querySelectorAll(".card").forEach((c) =>
    c.addEventListener("click", () => openDrawer(c.dataset.addr))
  );
}

/* ---------- alerts ---------- */
const TYPE_ICON = { OPEN: "▲", CLOSE: "▼", FLIP: "⇅", INCREASE: "+", DECREASE: "−", NEAR_LIQ: "⚠", CONFLUENCE: "⇉", PAUSED: "‖" };
const TIER_CLASS = { ELITE: "tier-ELITE", STRONG: "tier-STRONG", MODERATE: "tier-MODERATE", WEAK: "tier-WEAK" };
function renderAlerts() {
  const feed = $("#alert-feed");
  if (!state.alerts.length) {
    feed.innerHTML = `<li class="empty">No alerts yet — they fire when tracked traders change positions.</li>`;
    return;
  }
  feed.innerHTML = state.alerts
    .map(
      (a) => `<li class="sev-${a.severity}">
        <span class="t">${relTime(a.at)}</span>
        <span>${TYPE_ICON[a.type] || "•"}</span>
        <span><span class="who">${esc(a.label)}</span> <span class="msg">${esc(a.message)}</span></span>
      </li>`
    )
    .join("");
}

function toast(msg, severity) {
  const box = $("#toasts");
  while (box.children.length >= 4) box.firstChild.remove();
  const el = document.createElement("div");
  el.className = `toast sev-${severity || "info"}`;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

/* ---------- alert sound ---------- */
state.soundOn = localStorage.getItem("pp-sound") === "on";
let audioCtx = null;
function beep() {
  if (!state.soundOn) return;
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(760, audioCtx.currentTime);
    o.frequency.setValueAtTime(980, audioCtx.currentTime + 0.09);
    g.gain.setValueAtTime(0.05, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.3);
    o.connect(g).connect(audioCtx.destination);
    o.start();
    o.stop(audioCtx.currentTime + 0.32);
  } catch {}
}
function renderSoundBtn() {
  const b = $("#sound-toggle");
  b.textContent = state.soundOn ? "SND ON" : "SND OFF";
  b.classList.toggle("on", state.soundOn);
}
$("#sound-toggle").addEventListener("click", () => {
  state.soundOn = !state.soundOn;
  localStorage.setItem("pp-sound", state.soundOn ? "on" : "off");
renderSoundBtn();

/* ---------- api pause ---------- */
$("#pause-btn").addEventListener("click", async () => {
  try {
    const r = await api("/api/pause", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paused: !state.paused }),
    });
    state.paused = r.paused;
    toast(r.paused ? "Nansen API paused — zero credit burn" : "Nansen API resumed", r.paused ? "warn" : "trade");
    pollHealth();
  } catch (e) {
    toast(e.message, "danger");
  }
});
});
renderSoundBtn();

/* ---------- smart money feed ---------- */
function renderFeed() {
  const tbody = $("#sm-table tbody");
  tbody.innerHTML = state.smartTrades
    .map((t) => {
      const side = t.side || (t.action && t.action.includes("Long") ? "Long" : "Short");
      return `<tr>
        <td class="dim mono">${new Date(t.block_timestamp).toLocaleTimeString()}</td>
        <td><b>${esc(t.trader_address_label)}</b> ${t.watched ? '<span class="watched-tag">● TRACKED</span>' : ""}<br><span class="mono dim addr">${shortAddr(t.trader_address)}</span></td>
        <td class="mono">${esc(t.token_symbol)}</td>
        <td>${esc(t.action)}</td>
        <td class="${sideCls(side)}">${side}</td>
        <td class="num">${t.token_amount != null ? Number(t.token_amount).toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}</td>
        <td class="num">${t.price_usd != null ? "$" + Number(t.price_usd).toLocaleString(undefined, { maximumFractionDigits: 4 }) : "—"}</td>
        <td class="num">${fmtUsd(t.value_usd)}</td>
        <td class="dim">${esc(t.type || "")}</td>
      </tr>`;
    })
    .join("");
}

/* ---------- drawer ---------- */
async function openDrawer(addr) {
  state.drawerAddr = addr;
  $("#drawer").classList.add("open");
  try {
    const d = await api(`/api/traders/${addr}`);
    $("#d-label").textContent = d.label;
    $("#d-addr").textContent = d.address;
    $("#d-addr").href = `https://hyperdash.info/trader/${d.address}`;
    const risk = d.risk;
    $("#d-summary").innerHTML = `
      <div class="d-sum"><div class="label">Win rate (30d)</div><div class="value">${fmtPct(d.win_rate)}</div></div>
      <div class="d-sum"><div class="label">Profit factor</div><div class="value ${d.profit_factor != null && d.profit_factor >= 1 ? "pos" : "neg"}">${d.profit_factor ?? "—"}</div></div>
      <div class="d-sum"><div class="label">Closed PnL (30d)</div><div class="value ${signedClass(d.total_closed_pnl)}">${fmtUsd(d.total_closed_pnl)}</div></div>
      <div class="d-sum"><div class="label">Avg win / loss</div><div class="value">${fmtUsd(d.avg_win)} / ${fmtUsd(d.avg_loss)}</div></div>
      <div class="d-sum"><div class="label">Max lev</div><div class="value">${risk.max_leverage || 0}x</div></div>
      <div class="d-sum"><div class="label">Account value</div><div class="value">${fmtUsd(d.account_value)}</div></div>`;
    const tbody = $("#d-pos tbody");
    tbody.innerHTML = (d.positions || [])
      .map(
        (p) => `<tr>
        <td class="mono"><b>${esc(p.coin)}</b></td>
        <td class="${sideCls(p.side)}">${p.side.toUpperCase()}</td>
        <td class="num">${Number(p.size).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
        <td class="num">${fmtUsd(p.value)}</td>
        <td class="num">${p.entry.toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
        <td class="num">${p.mark ? p.mark.toLocaleString(undefined, { maximumFractionDigits: 4 }) : "—"}</td>
        <td class="num dim">${p.liq ? p.liq.toLocaleString(undefined, { maximumFractionDigits: 4 }) : "—"}</td>
        <td class="num">${p.leverage}x</td>
        <td class="num ${signedClass(p.upnl)}">${fmtUsd(p.upnl)}</td>
      </tr>`
      )
      .join("") || `<tr><td colspan="9" class="dim">No open positions</td></tr>`;
    $("#d-skills tbody").innerHTML =
      (d.coin_skills || [])
        .map(
          (s) => `<tr>
        <td class="mono"><b>${esc(s.coin)}</b></td>
        <td class="num">${s.trades}</td>
        <td class="num ${s.win_rate >= 0.5 ? "pos" : "neg"}">${fmtPct(s.win_rate)}</td>
        <td class="num ${signedClass(s.pnl)}">${fmtUsd(s.pnl)}</td>
      </tr>`
        )
        .join("") || `<tr><td colspan="4" class="dim">No closed-trade history yet</td></tr>`;
    $("#d-alerts").innerHTML =
      (d.alerts || [])
        .map(
          (a) => `<li class="sev-${a.severity}"><span class="t">${relTime(a.at)}</span><span class="msg">${esc(a.message)}</span></li>`
        )
        .join("") || `<li class="empty">No alerts for this trader yet.</li>`;
    renderChart(d.metrics && d.metrics.equity_curve);
  } catch (e) {
    toast(e.message, "danger");
  }
}

function renderChart(curve) {
  const ctx = $("#d-chart");
  if (state.chart) state.chart.destroy();
  if (!curve || !curve.length) return;
  const grad = ctx.getContext("2d");
  const chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: curve.map((p) => (p.t || "").slice(5, 10)),
      datasets: [
        {
          label: "Cumulative closed PnL (30d)",
          data: curve.map((p) => p.cum_pnl),
          borderColor: "#4f8cff",
          backgroundColor: "rgba(79,140,255,.12)",
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.25,
        },
      ],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#7d8aa3", maxTicksLimit: 8 }, grid: { display: false } },
        y: { ticks: { color: "#7d8aa3", callback: (v) => fmtUsd(v) }, grid: { color: "#1a2131" } },
      },
    },
  });
  state.chart = chart;
}

$("#d-close").addEventListener("click", () => {
  $("#drawer").classList.remove("open");
  state.drawerAddr = null;
});
$("#d-remove").addEventListener("click", async () => {
  if (!state.drawerAddr) return;
  await api(`/api/watchlist/${state.drawerAddr}`, { method: "DELETE" });
  state.tracked.delete(state.drawerAddr);
  $("#drawer").classList.remove("open");
  state.drawerAddr = null;
  toast("Removed from watchlist", "info");
});

/* ---------- settings ---------- */
async function loadSettings() {
  try {
    const s = await api("/api/settings");
    $("#set-webhook").value = s.webhook_url || "";
    $("#set-chatid").value = s.telegram_chat_id || "";
  } catch {}
}
$("#set-save").addEventListener("click", async () => {
  try {
    await api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ webhook_url: $("#set-webhook").value, telegram_chat_id: $("#set-chatid").value }),
    });
    toast("Webhook settings saved", "trade");
  } catch (e) {
    toast(e.message, "danger");
  }
});
loadSettings();

/* ---------- polling ---------- */
async function pollHealth() {
  try {
    const h = await api("/api/health");
    $("#calls-value").textContent = h.total_calls.toLocaleString();
    $("#calls-meter").style.width = Math.min(100, (h.total_calls / 1000) * 100) + "%";
    $("#credits-value").textContent = h.credits_remaining != null ? `credits left: ${Math.round(h.credits_remaining).toLocaleString()}` : "";
    $("#watch-count").textContent = h.watchlist_size;
    $("#alert-count").textContent = h.alerts;
    $("#tab-watch-count").textContent = h.watchlist_size;
    $("#tab-alert-count").textContent = h.alerts;
    document.title = h.alerts > 0 ? `(${h.alerts}) PerpPilot` : "PerpPilot — Hyperliquid Copy-Trading Co-Pilot";
    const dot = $("#live-dot");
    state.paused = !!h.paused;
    const pb = $("#pause-btn");
    pb.textContent = h.paused ? "RESUME" : "PAUSE";
    pb.classList.toggle("on", !h.paused);
    pb.classList.toggle("off", h.paused);
    dot.classList.toggle("err", !!h.last_error && !h.paused);
    dot.classList.toggle("off", !!h.paused);
    dot.title = h.paused ? "API paused — no Nansen calls being made" : h.last_error ? `Last API error: ${h.last_error}` : "engine status: OK";
    $("#api-banner").classList.toggle("hidden", !h.out_of_credits);
    const badge = $("#mode-badge");
    badge.textContent = h.paused ? "PAUSED" : h.demo_mode ? "DEMO DATA" : "LIVE · NANSEN";
    badge.className = `mode-badge ${h.paused ? "paused" : h.demo_mode ? "demo" : "live"}`;
    if (h.demo_mode) {
      badge.title = "Demo mode — add NANSEN_API_KEY to .env for live Nansen data";
    }
  } catch {}
}

async function pollAll() {
  try {
    const [lb, wl, al, sm, cons, bs] = await Promise.all([
      api("/api/leaderboard"),
      api("/api/watchlist"),
      api("/api/alerts?limit=200"),
      api("/api/smart-trades?limit=150"),
      api("/api/consensus").catch(() => ({ data: [] })),
      api("/api/basket").catch(() => null),
    ]);
    state.leaderboard = lb.data || [];
    if (lb.updated_at) $("#lb-updated").textContent = `updated ${relTime(lb.updated_at)}`;
    state.watchlist = wl.data || [];
    state.watchlist.forEach((t) => state.tracked.add(t.address));
    const newAlerts = (al.data || []).filter((a) => a.id !== state.lastAlertId);
    if (state.lastAlertId && newAlerts.length && state.tab !== "alerts") {
      newAlerts.slice(0, 3).forEach((a) => toast(`${a.label}: ${a.message}`, a.severity));
      beep();
    }
    if (al.data && al.data.length) state.lastAlertId = al.data[0].id;
    state.alerts = al.data || [];
    state.smartTrades = sm.data || [];
    renderConsensus(cons.data || []);
    renderBasket(bs);
    if (state.tab === "discover") renderLeaderboard();
    if (state.tab === "watchlist") renderWatchlist();
    if (state.tab === "alerts") renderAlerts();
    if (state.tab === "feed") renderFeed();
    if (state.drawerAddr) openDrawer(state.drawerAddr);
  } catch {}
}

$("#lb-search").addEventListener("keydown", (e) => e.stopPropagation());
pollHealth();
pollAll();
setInterval(pollHealth, 5000);
setInterval(pollAll, 6000);
