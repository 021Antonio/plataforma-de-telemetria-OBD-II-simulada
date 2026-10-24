"use strict";
// Funções puras do dashboard (sem DOM): testáveis com Node.

const SWEEP_DEG = 120; // ponteiro vai de -120° a +120°
const ATM_KPA = 101.325;

function clamp(x, lo, hi) {
  return Math.min(hi, Math.max(lo, x));
}

function needleAngle(value, min, max) {
  const frac = clamp((value - min) / (max - min), 0, 1);
  return -SWEEP_DEG + 2 * SWEEP_DEG * frac;
}

// MAP absoluto (kPa) -> bar relativo à atmosfera; vácuo fica negativo.
function mapRelativeBar(kpa) {
  return Math.round(((kpa - ATM_KPA) / 100) * 1000) / 1000;
}

function zoneColor(value, zones) {
  for (const z of zones) {
    if (value <= z.max) return z.color;
  }
  return zones[zones.length - 1].color;
}

function pushWindow(series, t, v, windowS) {
  const next = series.concat([{ t, v }]);
  return next.filter((p) => t - p.t <= windowS);
}

// Amostras por segundo nos últimos `windowS` segundos (timestamps em s).
function rateHz(times, now, windowS) {
  const n = times.filter((t) => now - t <= windowS).length;
  return n / windowS;
}

// Nunca mostra valor antigo sem marca: sem amostra recente vira "nodata".
function connState(wsOpen, now, lastSampleAt, staleS = 3) {
  if (!wsOpen) return "reconnecting";
  if (lastSampleAt === null || now - lastSampleAt > staleS) return "nodata";
  return "connected";
}

// Guarda o último valor de cada PID: a amostra só traz os lidos naquele ciclo. Não altera `latest`.
function mergeSample(latest, values, now) {
  const next = Object.assign({}, latest);
  for (const [name, v] of Object.entries(values)) {
    next[name] = { value: v.value, unit: v.unit, at: now };
  }
  return next;
}

// "missing" só se nunca chegou; "stale" quando passou de `staleS` sem atualização.
function freshness(latest, name, now, staleS = 5) {
  const e = latest[name];
  if (e === undefined) return "missing";
  return now - e.at > staleS ? "stale" : "fresh";
}

const api = { mergeSample, freshness, needleAngle, mapRelativeBar, zoneColor, pushWindow, rateHz, connState, clamp };
if (typeof module !== "undefined") module.exports = api;
else window.Gauges = api;
