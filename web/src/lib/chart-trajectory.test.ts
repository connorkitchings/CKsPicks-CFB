import assert from "node:assert/strict";
import test from "node:test";
import { layoutTrajectoryEndpoints } from "./chart-trajectory-layout.ts";

test("trajectory endpoint logos: ties are deterministic, bounded and separated even at plot edges", () => {
  for (const y of [18, 250, 548]) {
    const endpoints = Array.from({ length: 20 }, (_, i) => ({ team: `Team ${String(i).padStart(2, "0")}`, y, size: i === 0 ? 30 : 20 }));
    const layout = layoutTrajectoryEndpoints(endpoints, 18, 548);
    assert.deepEqual(layout, layoutTrajectoryEndpoints([...endpoints].reverse(), 18, 548));
    const positions = [...layout.values()];
    assert.ok(positions[0].y - positions[0].size / 2 >= 18);
    assert.ok(positions.at(-1)!.y + positions.at(-1)!.size / 2 <= 548);
    for (let i = 1; i < positions.length; i++) {
      assert.ok(positions[i].y - positions[i].size / 2 >= positions[i - 1].y + positions[i - 1].size / 2 + 4);
      assert.equal(positions[i].size, 20);
    }
  }
});

test("trajectory endpoint logos: oversized groups fit the rail without overlapping", () => {
  const endpoints = Array.from({ length: 138 }, (_, i) => ({ team: `Team ${i}`, y: 250, size: 20 }));
  const positions = [...layoutTrajectoryEndpoints(endpoints, 18, 548).values()];
  assert.ok(positions[0].y - positions[0].size / 2 >= 18 - 1e-9);
  assert.ok(positions.at(-1)!.y + positions.at(-1)!.size / 2 <= 548 + 1e-9);
  for (let i = 1; i < positions.length; i++) {
    assert.ok(positions[i].y - positions[i].size / 2 >= positions[i - 1].y + positions[i - 1].size / 2);
  }
});
