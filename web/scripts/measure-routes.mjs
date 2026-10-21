#!/usr/bin/env node
// Time to first byte per route, cold (first request) and warm (median and p90 of the
// following requests), against a local `next start` or a Preview URL.
//
//   node web/scripts/measure-routes.mjs <baseUrl> [--runs N] [--route /path ...]
//
// TTFB is the time until response headers arrive; the body is then drained and its
// size reported. The matchup route is discovered from the first /matchup/<id> link on `/`.
const args = process.argv.slice(2);
const baseUrl = args.find((arg) => /^https?:\/\//.test(arg));
if (!baseUrl) {
  console.error("Usage: node web/scripts/measure-routes.mjs <baseUrl> [--runs N] [--route /path ...]");
  process.exit(64);
}
const flag = (name) => args.flatMap((arg, i) => (arg === name ? [args[i + 1]] : []));
const runs = Number(flag("--runs")[0] ?? 8);
if (!Number.isInteger(runs) || runs < 2) {
  console.error("--runs must be an integer >= 2");
  process.exit(64);
}
const origin = baseUrl.replace(/\/+$/, "");

async function timed(path) {
  const start = performance.now();
  const response = await fetch(origin + path, { redirect: "manual", headers: { "cache-control": "no-cache" } });
  const ttfb = performance.now() - start;
  const body = await response.text();
  return { ttfb, status: response.status, bytes: Buffer.byteLength(body), body };
}

const quantile = (sorted, q) => sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)];

async function discoverMatchup() {
  try {
    const { body } = await timed("/");
    return body.match(/\/matchup\/(\d+)/)?.[0] ?? null;
  } catch {
    return null;
  }
}

const explicit = flag("--route");
const routes = explicit.length ? explicit : ["/", "/ratings", "/results", "/performance", "/methodology"];
if (!explicit.length) {
  const matchup = await discoverMatchup();
  if (matchup) routes.splice(4, 0, matchup);
  else console.warn("No /matchup/<id> link found on /; skipping the matchup route");
}

const rows = [];
for (const route of routes) {
  try {
    const cold = await timed(route);
    const warm = [];
    for (let i = 0; i < runs - 1; i++) warm.push((await timed(route)).ttfb);
    warm.sort((a, b) => a - b);
    rows.push({
      route,
      status: cold.status,
      "cold ms": Math.round(cold.ttfb),
      "warm median ms": Math.round(quantile(warm, 0.5)),
      "warm p90 ms": Math.round(quantile(warm, 0.9)),
      "html KB": Math.round(cold.bytes / 1024),
    });
  } catch (error) {
    rows.push({ route, status: `error: ${error.message}` });
  }
}
console.table(rows);
