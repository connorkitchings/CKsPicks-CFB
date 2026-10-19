import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import nodeModule from "node:module";
import test from "node:test";
import { fileURLToPath } from "node:url";
import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

type LoadResult = { format?: string; source?: string; shortCircuit?: boolean };
type LoadHook = (url: string, context: object, nextLoad: (url: string, context: object) => LoadResult) => LoadResult;
// `registerHooks` (Node 22.15+) postdates the project's @types/node 20.
const { registerHooks } = nodeModule as unknown as { registerHooks(hooks: { load: LoadHook }): void };

// Node strips types but cannot compile JSX, so transpile .tsx modules on import.
registerHooks({
  load(url, context, nextLoad) {
    if (!url.endsWith(".tsx")) return nextLoad(url, context);
    const { outputText } = ts.transpileModule(readFileSync(fileURLToPath(url), "utf8"), {
      compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    });
    return { format: "module", source: outputText, shortCircuit: true };
  },
});

const { SegmentedControl } = await import("./SegmentedControl.tsx");

const options = [
  { value: "grid", label: "Grid", testId: "layout-grid" },
  { value: "list", label: "List", testId: "layout-list" },
] as const;

function compact(onChange: (value: "grid" | "list") => void = () => {}) {
  return SegmentedControl({ label: "Layout", value: "list", onChange, options, size: "sm", testId: "layout-switcher" });
}

function buttonClasses(markup: string): string[] {
  return [...markup.matchAll(/<button[^>]*class="([^"]*)"/g)].map((match) => match[1]);
}

test("compact segments never wrap and keep the 30px Charts height", () => {
  const classes = buttonClasses(renderToStaticMarkup(compact()));
  assert.equal(classes.length, 2);
  for (const className of classes) {
    const tokens = className.split(" ");
    assert.ok(tokens.includes("whitespace-nowrap"));
    assert.ok(tokens.includes("min-h-7.5"));
    assert.ok(!tokens.includes("min-h-11"), "compact segments skip the phone touch-target height");
    assert.ok(!tokens.some((token) => token === "break-words" || token === "flex-1"));
  }
});

test("default segments are 44px on phones, 36px from sm, and stay on one line", () => {
  const [className] = buttonClasses(renderToStaticMarkup(SegmentedControl({ label: "Layout", value: "grid", onChange: () => {}, options })));
  const tokens = className.split(" ");
  for (const token of ["whitespace-nowrap", "min-h-11", "sm:min-h-9"]) assert.ok(tokens.includes(token), token);
  assert.ok(!tokens.includes("flex-1"), "only filled groups stretch");
});

test("compact group exposes its label, test ids and only the selected option as pressed", () => {
  const markup = renderToStaticMarkup(compact());
  assert.match(markup, /^<div role="group" aria-label="Layout" data-testid="layout-switcher"/);
  assert.match(markup, /<button type="button" aria-pressed="false" data-testid="layout-grid"[^>]*>Grid<\/button>/);
  assert.match(markup, /<button type="button" aria-pressed="true" data-testid="layout-list"[^>]*>List<\/button>/);
});

test("clicking a segment reports its value", () => {
  const chosen: string[] = [];
  const buttons = compact((value) => chosen.push(value)).props.children as ReactElement<{ onClick: () => void }>[];
  buttons[0].props.onClick();
  assert.deepEqual(chosen, ["grid"]);
});
