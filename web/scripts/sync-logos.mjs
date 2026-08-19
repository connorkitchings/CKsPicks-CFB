/**
 * Copy team logos from ../assets/logos/ into ./public/logos/ so they're served
 * statically by Next.js at /logos/<Team>.png.
 *
 * Runs automatically via the `predev` and `prebuild` npm scripts.
 *
 * Safety: public/logos/ is also checked into git as the deployment fallback
 * (Vercel builds have no ../assets). Never wipe the destination unless the
 * source contains PNGs; copy to a staging directory and swap atomically.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SOURCE = path.resolve(__dirname, "..", "..", "assets", "logos");
const DEST = path.resolve(__dirname, "..", "public", "logos");
const STAGE = `${DEST}.staging`;

if (!fs.existsSync(SOURCE)) {
  console.warn(
    `[sync-logos] source not found: ${SOURCE} — keeping existing public/logos/`,
  );
  process.exit(0);
}

const pngs = fs
  .readdirSync(SOURCE)
  .filter((file) => file.toLowerCase().endsWith(".png"));

if (pngs.length === 0) {
  console.warn(
    `[sync-logos] source has no PNGs: ${SOURCE} — keeping existing public/logos/`,
  );
  process.exit(0);
}

fs.rmSync(STAGE, { recursive: true, force: true });
fs.mkdirSync(STAGE, { recursive: true });
for (const file of pngs) {
  fs.copyFileSync(path.join(SOURCE, file), path.join(STAGE, file));
}
fs.rmSync(DEST, { recursive: true, force: true });
fs.renameSync(STAGE, DEST);
console.log(`[sync-logos] copied ${pngs.length} logos -> public/logos/`);
