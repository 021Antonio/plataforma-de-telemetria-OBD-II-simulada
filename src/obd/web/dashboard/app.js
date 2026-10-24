"use strict";
// Dashboard: WebSocket /ws/stream com reconexão, mostradores SVG, gráfico de 60 s, DTCs e eventos.

const G = window.Gauges;
const $ = (id) => document.getElementById(id);

const RPM_MAX = 8000;
const RPM_REDLINE = 6000; // faixa vermelha configurável
const MAP_MIN_BAR = -1;
const MAP_MAX_BAR = 1.5;
const WINDOW_S = 60;
const RATE_WINDOW_S = 3;
const BACKOFF_S = [1, 2, 4, 8, 16, 30];
const COLORS = { ok: "var(--ok)", warn: "var(--warn)", bad: "var(--bad)" };
const ZONES = {
  coolant: [{ max: 60, color: "warn" }, { max: 105, color: "ok" }, { max: Infinity, color: "bad" }],
  fuel: [{ max: 10, color: "bad" }, { max: 25, color: "warn" }, { max: Infinity, color: "ok" }],
  speed: [{ max: 120, color: "ok" }, { max: Infinity, color: "warn" }],
};
const BARS = {
  throttle: { min: 0, max: 100, fmt: (v) => v.toFixed(0) + " %" },
  load: { min: 0, max: 100, fmt: (v) => v.toFixed(0) + " %" },
  short_fuel_trim: { min: -100, max: 100, fmt: (v) => v.toFixed(1) + " %", id: "trim" },
  voltage: { min: 9, max: 16, fmt: (v) => v.toFixed(2) + " V" },
};

const state = {
  ws: null, open: false, attempt: 0, lastSampleAt: null, lastSeq: null,
  times: [], series: {}, tab: "rpm", descriptions: {}, errors: { timeouts: 0, invalid: 0 }, latest: {},
};

function polar(angleDeg, r) {
  const a = (angleDeg * Math.PI) / 180;
  return [r * Math.sin(a), -r * Math.cos(a)];
}

function drawTicks(groupId, min, max, step, label) {
  const g = $(groupId);
  for (let v = min; v <= max + 1e-9; v += step) {
    const ang = G.needleAngle(v, min, max);
    const [x1, y1] = polar(ang, 84);
    const [x2, y2] = polar(ang, 76);
    const [tx, ty] = polar(ang, 64);
    g.insertAdjacentHTML("beforeend",
      `<line class="gtick" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>` +
      `<text class="gnum" x="${tx}" y="${ty + 3}" text-anchor="middle">${label(v)}</text>`);
  }
}

function drawRedline() {
  const [x1, y1] = polar(G.needleAngle(RPM_REDLINE, 0, RPM_MAX), 90);
  const [x2, y2] = polar(120, 90);
  $("rpm-redline").setAttribute("d", `M${x1} ${y1} A90 90 0 0 1 ${x2} ${y2}`);
}

function setNeedle(id, angle) {
  $(id).style.transform = `rotate(${angle}deg)`;
}

function val(latest, name) {
  const v = latest[name];
  return v === undefined ? null : v.value;
}

// Esmaece o mostrador cujo valor passou de 5 s sem atualização.
function markStale(latest, name, id, now) {
  $(id).closest(".medida, label, section").classList.toggle("defasado", G.freshness(latest, name, now) === "stale");
}

function setBar(name, v) {
  const cfg = BARS[name];
  const id = cfg.id || name;
  const frac = G.clamp((v - cfg.min) / (cfg.max - cfg.min), 0, 1);
  const bar = $("bar-" + id);
  if (cfg.min < 0) { // barra centrada no zero
    bar.style.left = (frac < 0.5 ? frac : 0.5) * 100 + "%";
    bar.style.width = Math.abs(frac - 0.5) * 100 + "%";
  } else {
    bar.style.width = frac * 100 + "%";
  }
  $("val-" + id).textContent = cfg.fmt(v);
}

function setDigit(id, v, zones) {
  const el = $(id);
  el.textContent = v === null ? "–" : v.toFixed(0);
  el.style.color = v === null || !zones ? "" : COLORS[G.zoneColor(v, zones)];
}

function render(latest, now) {
  const rpm = val(latest, "rpm");
  if (rpm !== null) {
    setNeedle("rpm-needle", G.needleAngle(rpm, 0, RPM_MAX));
    $("rpm-text").textContent = rpm.toFixed(0) + " rpm";
  }
  const map = val(latest, "map");
  if (map !== null) {
    const bar = G.mapRelativeBar(map);
    setNeedle("map-needle", G.needleAngle(bar, MAP_MIN_BAR, MAP_MAX_BAR));
    $("map-text").textContent = bar.toFixed(2) + " bar";
  }
  setDigit("speed", val(latest, "speed"), ZONES.speed);
  setDigit("coolant", val(latest, "coolant"), ZONES.coolant);
  setDigit("fuel", val(latest, "fuel_level"), ZONES.fuel);
  for (const name of Object.keys(BARS)) {
    const v = val(latest, name);
    if (v !== null) setBar(name, v);
    markStale(latest, name, "bar-" + (BARS[name].id || name), now);
  }
  markStale(latest, "speed", "speed", now);
  markStale(latest, "coolant", "coolant", now);
  markStale(latest, "fuel_level", "fuel", now);
}

function drawChart() {
  const pts = state.series[state.tab] || [];
  const now = Date.now() / 1000;
  if (pts.length < 2) {
    for (const id of ["chart-line", "chart-area"]) $(id).setAttribute("points", "");
    $("chart-max").textContent = $("chart-min").textContent = "–";
    return;
  }
  const vs = pts.map((p) => p.v);
  const lo = Math.min(...vs), hi = Math.max(...vs);
  const span = hi - lo || 1;
  const xy = pts.map((p) =>
    [600 * (1 - (now - p.t) / WINDOW_S), 140 - 130 * (p.v - lo) / span]);
  const line = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  $("chart-line").setAttribute("points", line);
  $("chart-area").setAttribute("points", `${xy[0][0].toFixed(1)},140 ${line} ${xy[xy.length - 1][0].toFixed(1)},140`);
  const dec = span < 10 ? 1 : 0;
  $("chart-max").textContent = hi.toFixed(dec);
  $("chart-min").textContent = lo.toFixed(dec);
}

function addEvent(text) {
  const li = document.createElement("li");
  li.textContent = new Date().toLocaleTimeString("pt-BR") + "  " + text;
  const list = $("events");
  list.prepend(li);
  while (list.children.length > 50) list.lastChild.remove();
}

function onSample(sample) {
  const now = Date.now() / 1000;
  if (state.lastSeq !== null && sample.seq <= state.lastSeq) return; // repetição do replay
  state.lastSeq = sample.seq;
  state.lastSampleAt = now;
  state.latest = G.mergeSample(state.latest, sample.values, now);
  state.times.push(now);
  state.times = state.times.filter((t) => now - t <= RATE_WINDOW_S);
  for (const [name, v] of Object.entries(sample.values)) {
    state.series[name] = G.pushWindow(state.series[name] || [], now, v.value, WINDOW_S);
  }
  const err = sample.errors || { timeouts: 0, invalid: 0 };
  if (err.timeouts > state.errors.timeouts) addEvent("timeout de leitura (" + err.timeouts + " no total)");
  if (err.invalid > state.errors.invalid) addEvent("quadro inválido (" + err.invalid + " no total)");
  state.errors = err;
  $("cycle").textContent = sample.cycle_ms.toFixed(1);
  $("latency").textContent = Math.max(0, (now - sample.ts) * 1000).toFixed(0);
  render(state.latest, now);
}

function onDtc(report) {
  const mil = $("mil");
  mil.className = "mil " + (report.mil ? "on" : "off");
  const list = $("dtc-list");
  list.replaceChildren();
  $("dtc-desc").textContent = "";
  if (!report.codes.length) {
    list.innerHTML = '<li class="muted">Nenhum DTC</li>';
    return;
  }
  for (const c of report.codes) {
    const li = document.createElement("li");
    li.textContent = c.code + " (" + c.status + ")";
    li.addEventListener("click", () => { $("dtc-desc").textContent = c.code + ": " + c.description; });
    list.appendChild(li);
  }
}

function refreshState() {
  const now = Date.now() / 1000;
  const st = G.connState(state.open, now, state.lastSampleAt);
  const pill = $("conn-state");
  pill.className = "pill " + st;
  pill.textContent = { connected: "conectado", reconnecting: "reconectando", nodata: "sem dados" }[st];
  const overlay = $("overlay");
  overlay.hidden = st === "connected";
  overlay.className = "overlay " + st;
  overlay.textContent = st === "reconnecting" ? "Reconectando: valores ocultos" : "Sem dados: valores ocultos";
  document.body.classList.toggle("stale", st !== "connected");
  $("rate").textContent = G.rateHz(state.times, now, RATE_WINDOW_S).toFixed(1);
  if (st !== "connected") {
    $("latency").textContent = "–";
    $("cycle").textContent = "–";
  }
  render(state.latest, now);
  drawChart();
}

function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(proto + "//" + location.host + "/ws/stream");
  state.ws = ws;
  ws.onopen = () => {
    state.open = true;
    state.attempt = 0;
    state.lastSeq = null; // o servidor reenvia os últimos 60 s
    addEvent("conectado");
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "sample") onSample(msg.data);
    else if (msg.type === "dtc") onDtc(msg.data);
  };
  ws.onclose = () => {
    if (state.open) addEvent("conexão perdida, reconectando");
    state.open = false;
    const delay = BACKOFF_S[Math.min(state.attempt++, BACKOFF_S.length - 1)];
    setTimeout(connect, delay * 1000);
  };
  ws.onerror = () => ws.close();
}

drawTicks("rpm-ticks", 0, RPM_MAX, 1000, (v) => v / 1000);
drawTicks("map-ticks", MAP_MIN_BAR, MAP_MAX_BAR, 0.5, (v) => v.toFixed(1));
drawRedline();
setNeedle("rpm-needle", G.needleAngle(0, 0, RPM_MAX));
setNeedle("map-needle", G.needleAngle(0, MAP_MIN_BAR, MAP_MAX_BAR));
$("chart-tabs").addEventListener("click", (ev) => {
  const tab = ev.target.closest("[data-series]");
  if (!tab) return;
  state.tab = tab.dataset.series;
  for (const t of $("chart-tabs").children) t.setAttribute("aria-selected", String(t === tab));
  drawChart();
});
setInterval(refreshState, 500);
refreshState();
connect();
