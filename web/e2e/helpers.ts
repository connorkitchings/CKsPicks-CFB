import { expect, type Page } from "@playwright/test";

/** Navigates and waits for React to hydrate, so clicks on server-rendered controls are not dropped. */
export async function gotoHydrated(page: Page, url: string): Promise<void> {
  await page.goto(url);
  await page.locator('html[data-hydrated="true"]').waitFor({ state: "attached" });
}

/** Switches the chart to its table view, retrying a click that landed before hydration. */
export async function openTable(page: Page): Promise<void> {
  const toggle = page.getByTestId("table-toggle");
  await expect(async () => {
    // Re-click only while still closed so a slow re-render never toggles the table back off.
    if ((await toggle.getAttribute("aria-pressed")) === "false") await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true", { timeout: 500 });
  }).toPass();
}

/**
 * Makes the browser report Web Share support for files and records what is shared, so the
 * Share action can be exercised: read it back with `sharedFiles`.
 */
export async function stubWebShare(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const shared: { name: string; type: string; title: string }[] = [];
    Object.assign(window, { __shared: shared });
    Object.defineProperty(navigator, "canShare", { value: () => true, configurable: true });
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: async (data: { files?: File[]; title?: string }) => {
        for (const file of data.files ?? []) shared.push({ name: file.name, type: file.type, title: data.title ?? "" });
      },
    });
  });
}

export async function sharedFiles(page: Page): Promise<{ name: string; type: string; title: string }[]> {
  return page.evaluate(() => (window as unknown as { __shared: { name: string; type: string; title: string }[] }).__shared ?? []);
}
