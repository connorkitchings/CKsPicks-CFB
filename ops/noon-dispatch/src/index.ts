// Cloudflare Worker: dispatches the weekly season update workflow at noon Eastern.
// GitHub Actions `schedule` runs arrive hours late or are dropped, so this
// worker calls the workflow_dispatch API on time instead.

export type Mode = "close-week" | "market-refresh";

export interface Env {
  GITHUB_TOKEN: string;
}

type FetchLike = (url: string, init: RequestInit) => Promise<Response>;

const DISPATCH_URL =
  "https://api.github.com/repos/connorkitchings/CKsPicks-CFB/actions/workflows/weekly-season-update.yml/dispatches";
const VARIABLE_URL =
  "https://api.github.com/repos/connorkitchings/CKsPicks-CFB/actions/variables/CFB_WEEKLY_AUTOMATION_ENABLED";
const RETRY_DELAY_MS = 5000;
const MAX_BODY_CHARS = 500;

/** Pure decision: which mode to dispatch at `now`, or null when it is not noon ET on Sunday/Monday. */
export function dispatchPlan(now: Date): { mode: Mode } | null {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const weekday = parts.find((p) => p.type === "weekday")?.value;
  const hour = parts.find((p) => p.type === "hour")?.value;
  if (hour !== "12") return null;
  if (weekday === "Sun") return { mode: "close-week" };
  if (weekday === "Mon") return { mode: "market-refresh" };
  return null;
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const githubHeaders = (token: string): Record<string, string> => ({
  Authorization: `Bearer ${token}`,
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "noon-dispatch-worker",
});

/** Kill switch: null when automation is enabled, otherwise the reason to skip. Unknown means off. */
async function disabledReason(token: string, fetchImpl: FetchLike): Promise<string | null> {
  try {
    const response = await fetchImpl(VARIABLE_URL, { method: "GET", headers: githubHeaders(token) });
    if (response.status === 404) return "CFB_WEEKLY_AUTOMATION_ENABLED is not set";
    if (!response.ok) return `reading CFB_WEEKLY_AUTOMATION_ENABLED failed with status ${response.status}`;
    const { value } = (await response.json()) as { value?: unknown };
    return value === "true" ? null : "CFB_WEEKLY_AUTOMATION_ENABLED is not \"true\"";
  } catch (err) {
    return `reading CFB_WEEKLY_AUTOMATION_ENABLED threw: ${err instanceof Error ? err.name : "error"}`;
  }
}

function post(token: string, mode: Mode, fetchImpl: FetchLike): Promise<Response> {
  return fetchImpl(DISPATCH_URL, {
    method: "POST",
    headers: { ...githubHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs: { mode } }),
  });
}

/**
 * Dispatches when the plan says so and the kill-switch variable is "true". Returns the mode sent,
 * or null when skipped (the reason is logged). Throws on dispatch failure.
 */
export async function runDispatch(
  now: Date,
  token: string,
  fetchImpl: FetchLike = fetch,
  delayMs: number = RETRY_DELAY_MS,
  log: (message: string) => void = console.log,
): Promise<Mode | null> {
  const plan = dispatchPlan(now);
  if (!plan) return null;
  const reason = await disabledReason(token, fetchImpl);
  if (reason) {
    log(`dispatch skipped: ${reason}`);
    return null;
  }
  let response = await post(token, plan.mode, fetchImpl);
  if (response.status >= 500) {
    await sleep(delayMs);
    response = await post(token, plan.mode, fetchImpl);
  }
  if (response.status !== 204) {
    const body = (await response.text()).slice(0, MAX_BODY_CHARS);
    throw new Error(`GitHub dispatch failed: ${response.status} ${body}`);
  }
  return plan.mode;
}

export default {
  async scheduled(event: { scheduledTime: number }, env: Env, _ctx: unknown): Promise<void> {
    const mode = await runDispatch(new Date(event.scheduledTime), env.GITHUB_TOKEN);
    console.log(mode ? `dispatched ${mode}` : "no dispatch (see skip reason above if any)");
  },
  async fetch(): Promise<Response> {
    return new Response("Not found", { status: 404 });
  },
};
