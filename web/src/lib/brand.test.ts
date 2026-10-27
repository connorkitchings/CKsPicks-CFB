import assert from "node:assert/strict";
import test from "node:test";
import { BRAND_NAME, BRAND_SUFFIX, BRAND_FULL, BRAND_MONOGRAM, EXPORT_PREFIX, SITE_URL } from "./brand.ts";

test("public identity and existing site address", () => {
  assert.equal(BRAND_NAME, "Stratum");
  assert.equal(BRAND_SUFFIX, "CFB");
  assert.equal(BRAND_FULL, "Stratum CFB");
  assert.equal(BRAND_MONOGRAM, "S");
  assert.equal(EXPORT_PREFIX, "stratum");
  assert.equal(SITE_URL, "https://c-ks-picks-cfb.vercel.app");
});
