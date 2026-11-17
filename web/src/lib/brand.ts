/** Site identity. Change the brand here; every user-facing name and export prefix reads from this module. */
export const BRAND_NAME = "Stratum";
export const BRAND_SUFFIX = "CFB";
export const BRAND_FULL = "Stratum CFB";
import pkg from "../../package.json" with { type: "json" };

/** Site version: one source of truth, `web/package.json` (semver; weekly data releases do not bump it). */
export const APP_VERSION: string = pkg.version;
export const BRAND_MONOGRAM = "S";
export const SITE_URL = "https://c-ks-picks-cfb.vercel.app";
export const EXPORT_PREFIX = "stratum";
