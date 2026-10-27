import assert from "node:assert/strict";
import test from "node:test";
import { isShareCancellation, reusablePreparedImage, sameShareImageIdentity, type ShareImageIdentity } from "./share-image.ts";

const base: ShareImageIdentity = {
  contentKey: "week 3|all|",
  filename: "stratum-efficiency-2026-through-week-3.png",
  title: "Efficiency vs explosiveness",
  width: 1000,
  height: 562,
  background: "",
  theme: "light",
};

test("a prepared image is reused only when every identity field matches", () => {
  const prepared = { identity: base, file: "png" };
  assert.equal(reusablePreparedImage(prepared, { ...base }), "png");
  const changes: Partial<ShareImageIdentity>[] = [
    { contentKey: "week 3|all|Michigan" },
    { filename: "other.png" },
    { title: "Other" },
    { width: 1200 },
    { height: 600 },
    { background: "#0b0b0d" },
    { theme: "dark" },
  ];
  for (const change of changes) {
    assert.equal(reusablePreparedImage(prepared, { ...base, ...change }), null, JSON.stringify(change));
    assert.equal(sameShareImageIdentity(base, { ...base, ...change }), false);
  }
});

test("no prepared image yields nothing to reuse", () => {
  assert.equal(reusablePreparedImage(null, base), null);
});

test("only an AbortError counts as share cancellation", () => {
  assert.equal(isShareCancellation(new DOMException("dismissed", "AbortError")), true);
  assert.equal(isShareCancellation({ name: "AbortError" }), true);
  assert.equal(isShareCancellation(new DOMException("expired", "NotAllowedError")), false);
  assert.equal(isShareCancellation(new Error("boom")), false);
  assert.equal(isShareCancellation(null), false);
});
