/**
 * Build the self-hosted team logo set (contract: docs/plans/2026-10-01/07).
 *
 *   node --env-file=../.env scripts/build-team-logos.mjs --dry-run   # inspect first
 *   node --env-file=../.env scripts/build-team-logos.mjs             # download + build
 *
 * Flags: --dry-run  print the plan, download nothing
 *        --year N   CFBD season (default 2026)
 *
 * Output (staged, then swapped in): public/logos/v2/{96,256 -> sm,lg}/{light,dark}/<id>.webp,
 * public/logos/v2/manifest.json, src/lib/team-logos.generated.ts, logo-report.json on failure.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import {
  SIZES,
  THEMES,
  assetPath,
  buildGeneratedTs,
  buildManifest,
  parseTeams,
  sha256,
} from "./team-logos-lib.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(here, "..");
const OUT = path.join(WEB, "public", "logos", "v2");
const STAGE = `${OUT}.staging`;
const GENERATED = path.join(WEB, "src", "lib", "team-logos.generated.ts");
const REPORT = path.join(WEB, "logo-report.json");

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const yearIdx = args.indexOf("--year");
const year = yearIdx >= 0 ? Number(args[yearIdx + 1]) : 2026;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchWithRetry(url, init = {}, tries = 3) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { ...init, signal: AbortSignal.timeout(20_000) });
      if (res.ok) return res;
      last = new Error(`HTTP ${res.status} for ${url}`);
      if (res.status === 404) break;
    } catch (err) {
      last = err;
    }
    await sleep(500 * 2 ** i);
  }
  throw last;
}

async function main() {
  const key = process.env.CFBD_API_KEY;
  if (!key) throw new Error("CFBD_API_KEY is not set (use --env-file=../.env)");
  const res = await fetchWithRetry(`https://api.collegefootballdata.com/teams/fbs?year=${year}`, {
    headers: { Authorization: `Bearer ${key}`, Accept: "application/json" },
  });
  const teams = parseTeams(await res.json());
  const noLogos = teams.filter((t) => t.usedFallback).map((t) => t.school);
  console.log(`[logos] ${teams.length} FBS teams for ${year}`);
  console.log("[logos] first three:", JSON.stringify(teams.slice(0, 3), null, 2));
  console.log(`[logos] teams without CFBD logos (ESPN fallback): ${noLogos.length}`, noLogos);
  if (dryRun) return;
  if (teams.length < 100) throw new Error(`only ${teams.length} teams parsed; refusing to build`);

  fs.rmSync(STAGE, { recursive: true, force: true });
  const failures = [];
  const entries = [];
  const retrieved = new Date().toISOString().slice(0, 10);

  for (const team of teams) {
    try {
      const sources = { light: team.light, dark: team.dark };
      const files = {};
      let darkFallbackToLight = false;
      const buffers = {};
      buffers.light = Buffer.from(await (await fetchWithRetry(team.light)).arrayBuffer());
      try {
        if (!team.dark) throw new Error("no dark url");
        buffers.dark = Buffer.from(await (await fetchWithRetry(team.dark)).arrayBuffer());
      } catch {
        buffers.dark = buffers.light;
        darkFallbackToLight = true;
      }
      for (const theme of THEMES) {
        for (const [size, px] of Object.entries(SIZES)) {
          const rel = assetPath(size, theme, team.id);
          const dest = path.join(STAGE, rel);
          fs.mkdirSync(path.dirname(dest), { recursive: true });
          const out = await sharp(buffers[theme])
            .resize(px, px, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
            .webp({ quality: 90, alphaQuality: 100 })
            .toBuffer();
          fs.writeFileSync(dest, out);
          files[rel] = sha256(out);
        }
      }
      entries.push({ id: team.id, school: team.school, sources, darkFallbackToLight, files });
      await sleep(100);
    } catch (err) {
      failures.push({ id: team.id, school: team.school, error: String(err) });
      console.warn(`[logos] FAILED ${team.school}: ${err}`);
    }
  }

  if (failures.length) {
    fs.writeFileSync(REPORT, JSON.stringify({ failures }, null, 2));
    fs.rmSync(STAGE, { recursive: true, force: true });
    throw new Error(`${failures.length} team(s) failed; see logo-report.json (nothing was swapped in)`);
  }

  fs.writeFileSync(
    path.join(STAGE, "manifest.json"),
    JSON.stringify(buildManifest(entries, retrieved), null, 2) + "\n",
  );
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.renameSync(STAGE, OUT);
  fs.writeFileSync(GENERATED, buildGeneratedTs(entries));
  fs.rmSync(REPORT, { force: true });
  console.log(`[logos] wrote ${entries.length} teams to ${OUT}`);
}

main().catch((err) => {
  console.error(`[logos] ${err.message ?? err}`);
  process.exit(1);
});
