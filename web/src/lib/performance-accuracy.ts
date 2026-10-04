export type AccuracyResult = "win" | "loss" | "push" | null;

export function accuracyRecord(results: AccuracyResult[]) {
  let win = 0, loss = 0, push = 0;
  for (const result of results) {
    if (result === "win") win++;
    else if (result === "loss") loss++;
    else if (result === "push") push++;
  }
  return { win, loss, push, winRate: win + loss ? 100 * win / (win + loss) : null };
}
