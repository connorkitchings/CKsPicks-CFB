#!/usr/bin/env node
// Time to first byte per route, cold (first request) and warm (median and p90 of the
// following requests), against a local `next start` or a Preview URL.
//
//   node web/scripts/measure-routes.mjs <baseUrl> [--runs N] [--route /path ...]
//
// TTFB is the time until response headers arrive. Routes with a loading.tsx stream a
// shell immediately, so headers say little about data cost; "total" is the time until the
// whole body has arrived, and is the number to compare. Body size is also reported. The matchup route is discovered from the first /matchup/<id> link in the cold response of the first route (no extra request, so nothing is warmed). Any status other than 200 marks the row as an error and the exit code is 1; /stats is skipped with a note when it returns 404.
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
  const total = performance.now() - start;
  return { ttfb, total, status: response.status, bytes: Buffer.byteLength(body), body };
}

const quantile = (sorted, q) => sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)];

const explicit = flag("--route");
const routes = explicit.length ? [...explicit] : ["/", "/ratings", "/model", "/model/method", "/stats"];
const discover = !explicit.length;

const rows = [];
let failed = false;
let first = true;
for (let index = 0; index < routes.length; index++) {
  const route = routes[index];
  try {
    // The very first request is the cold measurement of the first route; nothing precedes it.
    const cold = await timed(route);
    if (first && discover) {
      first = false;
      const matchup = cold.body.match(/\/matchup\/(\d+)/)?.[0];
      if (matchup) routes.push(matchup);
      else console.warn(`No /matchup/<id> link found on ${route}; skipping the matchup route`);
    }
    if (route === "/stats" && cold.status === 404 && discover) {
      console.warn("/stats returned 404 (not published); skipping");
      continue;
    }
    if (cold.status !== 200) throw new Error(`unexpected status ${cold.status}`);
    const warm = [];
    const warmTotal = [];
    for (let i = 0; i < runs - 1; i++) {
      const result = await timed(route);
      if (result.status !== 200) throw new Error(`unexpected status ${result.status} on a warm run`);
      warm.push(result.ttfb);
      warmTotal.push(result.total);
    }
    warm.sort((a, b) => a - b);
    warmTotal.sort((a, b) => a - b);
    rows.push({
      route,
      status: cold.status,
      "cold ms": Math.round(cold.ttfb),
      "warm median ms": Math.round(quantile(warm, 0.5)),
      "warm p90 ms": Math.round(quantile(warm, 0.9)),
      "cold total ms": Math.round(cold.total),
      "warm total median ms": Math.round(quantile(warmTotal, 0.5)),
      "warm total p90 ms": Math.round(quantile(warmTotal, 0.9)),
      "html KB": Math.round(cold.bytes / 1024),
    });
  } catch (error) {
    failed = true;
    rows.push({ route, status: `error: ${error.message}` });
  }
}
console.table(rows);
if (failed) process.exit(1);
