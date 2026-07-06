/**
 * Copy team logos from ../Logos/ into ./public/logos/ so they're served
 * statically by Next.js at /logos/<Team>.png.
 *
 * Runs automatically via the `predev` and `prebuild` npm scripts.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const SOURCE = path.resolve(__dirname, "..", "..", "Logos");
const DEST = path.resolve(__dirname, "..", "public", "logos");

if (!fs.existsSync(SOURCE)) {
  console.warn(`[sync-logos] source not found: ${SOURCE} — skipping`);
  process.exit(0);
}

fs.rmSync(DEST, { recursive: true, force: true });
fs.mkdirSync(DEST, { recursive: true });

let count = 0;
for (const file of fs.readdirSync(SOURCE)) {
  if (!file.toLowerCase().endsWith(".png")) continue;
  fs.copyFileSync(path.join(SOURCE, file), path.join(DEST, file));
  count++;
}
console.log(`[sync-logos] copied ${count} logos -> public/logos/`);
