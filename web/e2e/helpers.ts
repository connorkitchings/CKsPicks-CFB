import { expect, type Page } from "@playwright/test";

/** Switches the chart to its table view, retrying a click that landed before hydration. */
export async function openTable(page: Page): Promise<void> {
  const toggle = page.getByTestId("table-toggle");
  await expect(async () => {
    // Re-click only while still closed so a slow re-render never toggles the table back off.
    if ((await toggle.getAttribute("aria-pressed")) === "false") await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true", { timeout: 500 });
  }).toPass();
}
