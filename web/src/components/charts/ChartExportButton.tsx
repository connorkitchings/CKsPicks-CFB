"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

type Action = "download" | "copy";
export type ExportReport = { width: number; height: number; logos: number; decoded: number };

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/**
 * Wait for fonts and for every image of the card. ShareButton's settle step only sees HTML
 * `img` elements and SVGImageElement has no decode(), so each SVG `image` href (and
 * `img` src) is preloaded through `new Image()` and decoded; failures are ignored.
 */
export async function settleImages(node: Element): Promise<{ logos: number; decoded: number }> {
  await document.fonts?.ready;
  const sources = new Set<string>();
  for (const image of node.querySelectorAll("image")) {
    const href = image.getAttribute("href") ?? image.getAttribute("xlink:href");
    if (href) sources.add(new URL(href, document.baseURI).href);
  }
  for (const image of node.querySelectorAll("img")) if (image.src) sources.add(image.src);
  const results = await Promise.all(
    [...sources].map(async (src) => {
      const image = new Image();
      image.src = src;
      try {
        await image.decode();
        return true;
      } catch {
        return false;
      }
    }),
  );
  return { logos: sources.size, decoded: results.filter(Boolean).length };
}

async function renderPng(node: HTMLElement, width: number, height: number): Promise<{ blob: Blob; report: ExportReport }> {
  const { logos, decoded } = await settleImages(node);
  const { toBlob } = await import("html-to-image");
  const background = getComputedStyle(node).backgroundColor;
  const options = { pixelRatio: 2, width, height, backgroundColor: background };
  // Safari draws images and fonts only on a second pass.
  if (/^((?!chrome|android).)*safari/i.test(navigator.userAgent)) await toBlob(node, options);
  const blob = await toBlob(node, options);
  if (!blob) throw new Error("The chart could not be rendered");
  return { blob, report: { width: width * 2, height: height * 2, logos, decoded } };
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

const subscribeNever = () => () => {};
const serverFalse = () => false;
const canCopyImages = () => typeof ClipboardItem !== "undefined" && Boolean(navigator.clipboard?.write);

const buttonClass =
  "inline-flex min-h-10 items-center rounded-lg border border-line bg-surface-card px-3 py-2 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-wait disabled:opacity-60";

/**
 * Exports the chart as one fixed-size image. The export card (`children`, laid out at
 * `width` x `height` CSS pixels and captured at 2x) is mounted off-screen only while an
 * image is being made, so the page itself is unchanged.
 */
export function ChartExportButton({
  filename,
  width,
  height,
  children,
}: {
  filename: string;
  width: number;
  height: number;
  children: ReactNode;
}) {
  const [job, setJob] = useState<Action | null>(null);
  const [status, setStatus] = useState("");
  const [report, setReport] = useState<ExportReport | null>(null);
  const canCopy = useSyncExternalStore(subscribeNever, canCopyImages, serverFalse);
  const cardRef = useRef<HTMLDivElement>(null);
  const pending = useRef<Deferred<Blob> | null>(null);
  const rendered = useRef<Deferred<Blob> | null>(null);

  useEffect(() => {
    const done = pending.current;
    if (!job || !cardRef.current || !done || rendered.current === done) return; // strict mode runs effects twice
    rendered.current = done;
    renderPng(cardRef.current, width, height)
      .then(({ blob, report: made }) => {
        setReport(made);
        done.resolve(blob);
      })
      .catch((error) => done.reject(error));
  }, [job, width, height]);

  async function run(action: Action) {
    if (job) return;
    const render = deferred<Blob>();
    pending.current = render;
    setStatus("Creating image…");
    setJob(action);
    try {
      if (action === "copy") {
        // Created inside the click so Safari keeps the user gesture; the image resolves later.
        await navigator.clipboard.write([new ClipboardItem({ "image/png": render.promise })]);
        setStatus("Image copied");
      } else {
        saveBlob(await render.promise, filename);
        setStatus("Image saved");
      }
    } catch {
      setStatus("Could not create the image");
    } finally {
      setJob(null);
      pending.current = null;
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="chart-export" data-last-export={report ? JSON.stringify(report) : undefined}>
      <button type="button" className={buttonClass} data-testid="chart-download" disabled={job !== null} onClick={() => void run("download")}>
        Download PNG
      </button>
      {canCopy && (
        <button type="button" className={buttonClass} data-testid="chart-copy" disabled={job !== null} onClick={() => void run("copy")}>
          Copy image
        </button>
      )}
      <span role="status" aria-live="polite" className="text-[11px] text-ink-faint">
        {status}
      </span>
      {job && (
        <div aria-hidden style={{ position: "fixed", left: -100000, top: 0, pointerEvents: "none" }}>
          <div ref={cardRef} style={{ width, height }} className="bg-surface-card text-ink">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}
