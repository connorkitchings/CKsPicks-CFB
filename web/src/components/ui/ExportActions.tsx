"use client";

import clsx from "clsx";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { isShareCancellation, reusablePreparedImage, type PreparedShareImage, type ShareImageIdentity } from "@/lib/share-image";

type Action = "download" | "copy" | "share";
type Outcome = "done" | "failed";
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
 * Wait for fonts and for every image of the card. SVGImageElement has no decode(), so each
 * SVG `image` href (and `img` src) is preloaded through `new Image()` and decoded; failures
 * are ignored.
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

async function renderPng(
  node: HTMLElement,
  width: number,
  height: number,
  backgroundColor: string | undefined,
): Promise<{ blob: Blob; report: ExportReport }> {
  // html-to-image deep-clones SVG roots without copying computed styles of
  // descendants. Bake each logo variant's visibility into the temporary export
  // card: ancestor-dependent dark: utilities cannot survive that SVG clone.
  for (const image of node.querySelectorAll("image")) image.style.display = getComputedStyle(image).display;
  const { logos, decoded } = await settleImages(node);
  const { toBlob } = await import("html-to-image");
  const options = { pixelRatio: 2, width, height, backgroundColor: backgroundColor ?? getComputedStyle(node).backgroundColor };
  // Safari draws images and fonts only on a second pass.
  if (/^((?!chrome|android).)*safari/i.test(navigator.userAgent)) await toBlob(node, options);
  const blob = await toBlob(node, options);
  if (!blob) throw new Error("The image could not be rendered");
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

// Capability checks run in the browser only; the server and first paint assume none, so there is no hydration mismatch.
const subscribeNever = () => () => {};
const serverFalse = () => false;
const canCopyImages = () => typeof ClipboardItem !== "undefined" && Boolean(navigator.clipboard?.write);
/** The page theme decides which logo and `dark:` variants the card is drawn with. */
const subscribeTheme = (onChange: () => void) => {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
};
const currentTheme = (): "light" | "dark" => (document.documentElement.classList.contains("dark") ? "dark" : "light");
const serverTheme = (): "light" | "dark" => "light";
const canShareFiles = () =>
  typeof navigator.canShare === "function" &&
  navigator.canShare({ files: [new File([""], "probe.png", { type: "image/png" })] });

/** 44px touch targets on phones, the compact 36px from the sm breakpoint up. */
const buttonClass =
  "inline-flex size-11 items-center justify-center rounded-lg border border-line bg-surface-card text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60 sm:size-9";

const ICON_PATHS: Record<Action | Outcome, string> = {
  download: "M12 4v11m-4.5-4.5L12 15l4.5-4.5M5 19h14",
  copy: "M9 9h10v10H9zM5 15V5h10",
  share: "M12 15V4m0 0L8.5 7.5M12 4l3.5 3.5M5 13v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5",
  done: "M5 12.5l4.5 4.5L19 7",
  failed: "M12 7v6m0 4h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
};

const LABELS: Record<Action, string> = { download: "Download PNG", copy: "Copy image", share: "Share" };
/** Tooltips open toward the inside of the button group, so they never push past the viewport edge. */
const TOOLTIP_POSITION = { left: "left-0", center: "left-1/2 -translate-x-1/2", right: "right-0" } as const;

/** Announced (not a failure) when the inputs changed under a running export; the user taps again. */
const STALE_TEXT = "The chart changed. Tap again.";
const READY_TEXT = "Image ready: tap Share again";

/** How long a finished export keeps its outcome icon and tooltip text. */
const FEEDBACK_MS = 2500;

export type ExportTestIds = {
  /** Wrapper; also carries `data-last-export` (the last image's size and logo counts). */
  container: string;
  download: string;
  copy: string;
  share: string;
};

/**
 * Icon-only action named by `aria-label`, with a visible tooltip on hover and keyboard focus.
 * Right after its export finishes, the icon shows the outcome and the tooltip the status text,
 * which the parent's live region also announces.
 */
function ActionButton({ action, testId, outcome, tip, tooltipAlign, disabled, onClick }: {
  action: Action;
  testId: string;
  outcome: Outcome | null;
  tip: string;
  tooltipAlign: "left" | "center" | "right";
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <span className="group relative inline-flex">
      <button type="button" aria-label={LABELS[action]} className={buttonClass} data-testid={testId} disabled={disabled} onClick={onClick}>
        <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <path d={ICON_PATHS[outcome ?? action]} />
        </svg>
      </button>
      <span
        aria-hidden
        className={`pointer-events-none absolute top-full z-20 mt-1.5 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-[11px] font-medium text-surface-card opacity-0 shadow-sm transition-opacity group-hover:opacity-100 group-has-[:focus-visible]:opacity-100 ${outcome ? "opacity-100" : ""} ${TOOLTIP_POSITION[tooltipAlign]}`}
        data-testid={`${testId}-tooltip`}
      >
        {tip}
      </span>
    </span>
  );
}

/**
 * The one set of export actions for every shareable image on the site (the chart exports and
 * the matchup card): Download, Copy (where the clipboard takes images) and Share (where the
 * browser shares files). The card (`children`, laid out at `width` x `height` CSS pixels and
 * captured at 2x) is mounted off-screen only while an image is being made, so the page itself
 * is unchanged.
 */
export function ExportActions({
  filename,
  shareTitle,
  width,
  height,
  backgroundColor,
  contentKey = "",
  disabled = false,
  disabledReason,
  compactReason = false,
  tooltipAlign = "right",
  atRightEdge = false,
  testIds,
  children,
}: {
  filename: string;
  shareTitle: string;
  width: number;
  height: number;
  /** Image background; defaults to the card's computed background. */
  backgroundColor?: string;
  /** Fingerprint of what the card shows beyond the filename and title (filters, highlight, metric...); a change discards a prepared image. */
  contentKey?: string;
  disabled?: boolean;
  /** Shown beside the disabled buttons so they are never silently inert. */
  disabledReason?: string;
  /** Phones: show a short visible "Unavailable" (the full reason stays for assistive tech and as a hover title). */
  compactReason?: boolean;
  tooltipAlign?: "left" | "right";
  /** The group ends at the viewport's content edge: every tooltip opens leftward, however many buttons show. */
  atRightEdge?: boolean;
  testIds: ExportTestIds;
  children: ReactNode;
}) {
  const [job, setJob] = useState<Action | null>(null);
  const [status, setStatus] = useState("");
  const [report, setReport] = useState<ExportReport | null>(null);
  /** The finished export whose outcome its button shows for `FEEDBACK_MS`. */
  const [feedback, setFeedback] = useState<{ action: Action; outcome: Outcome } | null>(null);
  /** An image kept for a second tap, for browsers that only share inside a fresh gesture, with what it was made from. */
  const [ready, setReady] = useState<PreparedShareImage<File> | null>(null);
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, serverTheme);
  const identity: ShareImageIdentity = { contentKey, filename, title: shareTitle, width, height, background: backgroundColor ?? "", theme };
  const identityKey = JSON.stringify(identity);
  const identityRef = useRef(identity);
  /** Bumped whenever the inputs change; a render or share started under an older value is obsolete. */
  const generation = useRef(0);
  const jobGeneration = useRef(0);
  /** False once the component has left the page: no export may save, share, copy or update state after that. */
  const mounted = useRef(false);
  const caps = {
    copy: useSyncExternalStore(subscribeNever, canCopyImages, serverFalse),
    share: useSyncExternalStore(subscribeNever, canShareFiles, serverFalse),
  };
  const cardRef = useRef<HTMLDivElement>(null);
  const pending = useRef<Deferred<Blob> | null>(null);
  const rendered = useRef<Deferred<Blob> | null>(null);

  // Setup sets the flag again, so React strict mode's mount/unmount/mount ends mounted; cleanup also obsoletes any running export.
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
    };
  }, []);

  useEffect(() => {
    identityRef.current = JSON.parse(identityKey) as ShareImageIdentity;
    generation.current += 1;
  }, [identityKey]);

  useEffect(() => {
    const done = pending.current;
    if (!job || !cardRef.current || !done || rendered.current === done) return; // strict mode runs effects twice
    rendered.current = done;
    const started = jobGeneration.current;
    renderPng(cardRef.current, width, height, backgroundColor)
      .then(({ blob, report: made }) => {
        if (!mounted.current) return done.reject(new Error("The export was left before the image finished"));
        if (started !== generation.current) return done.reject(new Error("The inputs changed while the image was rendering"));
        setReport(made);
        done.resolve(blob);
      })
      .catch((error) => done.reject(error));
  }, [job, width, height, backgroundColor]);

  useEffect(() => {
    if (!feedback) return;
    const timer = setTimeout(() => setFeedback(null), FEEDBACK_MS);
    return () => clearTimeout(timer);
  }, [feedback]);

  const finish = (action: Action, outcome: Outcome, text: string) => {
    setStatus(text);
    setFeedback(outcome === "failed" || text ? { action, outcome } : null);
  };

  /** The inputs changed under a running export: nothing was saved or shared; say so without an outcome icon. */
  const discard = () => {
    setStatus(STALE_TEXT);
    setFeedback(null);
  };

  async function run(action: Action) {
    if (job) return;
    const render = deferred<Blob>();
    pending.current = render;
    const started = generation.current;
    jobGeneration.current = started;
    setStatus("Creating image…");
    setFeedback(null);
    setJob(action);
    try {
      if (action === "copy") {
        // Created inside the click so Safari keeps the user gesture; the image resolves later.
        await navigator.clipboard.write([new ClipboardItem({ "image/png": render.promise })]);
        if (!mounted.current) return;
        finish(action, "done", "Image copied");
        return;
      }
      const blob = await render.promise;
      if (!mounted.current) return;
      if (started !== generation.current) throw new Error("obsolete");
      if (action === "download") {
        saveBlob(blob, filename);
        finish(action, "done", "Image saved");
        return;
      }
      const made = identityRef.current;
      const file = new File([blob], made.filename, { type: "image/png" });
      try {
        await navigator.share({ files: [file], title: made.title });
        if (mounted.current) finish(action, "done", "");
      } catch (error) {
        if (!mounted.current) return;
        if (isShareCancellation(error)) {
          finish(action, "done", "");
        } else if (started === generation.current) {
          setReady({ identity: made, file });
          finish(action, "done", READY_TEXT);
        } else {
          discard();
        }
      }
    } catch {
      if (!mounted.current) return;
      // An obsolete render is dropped, never saved or shared: the next tap prepares an image from the current inputs.
      if (started !== generation.current) discard();
      else finish(action, "failed", "Could not create the image");
    } finally {
      if (mounted.current) setJob(null);
      if (pending.current === render) pending.current = null;
    }
  }

  async function shareReady(file: File) {
    setReady(null);
    try {
      await navigator.share({ files: [file], title: identityRef.current.title });
      if (mounted.current) finish("share", "done", "");
    } catch (error) {
      if (!mounted.current) return;
      if (isShareCancellation(error)) {
        finish("share", "done", "");
        return;
      }
      saveBlob(file, file.name);
      finish("download", "done", "Image saved");
    }
  }

  function onShare() {
    const usable = reusablePreparedImage(ready, identityRef.current);
    if (usable) return void shareReady(usable);
    if (ready) setReady(null); // outdated: prepare a new image from the current inputs
    void run("share");
  }

  // A kept image belongs to the inputs it was made from: once they change, its "tap Share again" text is withdrawn too.
  const shownStatus = status === READY_TEXT && !reusablePreparedImage(ready, identity) ? "" : status;
  const busy = disabled || job !== null;
  const visible: Action[] = ["download", ...(caps.copy ? (["copy"] as const) : []), ...(caps.share ? (["share"] as const) : [])];
  const buttonProps = (action: Action) => {
    const outcome = feedback?.action === action ? feedback.outcome : null;
    const index = visible.indexOf(action);
    // A lone button follows the caller's choice; otherwise first opens left, last right, middle centered.
    const align = atRightEdge ? "right" : visible.length === 1 ? tooltipAlign : index === 0 ? "left" : index === visible.length - 1 ? "right" : "center";
    return { action, testId: testIds[action], outcome, tip: outcome && shownStatus ? shownStatus : LABELS[action], tooltipAlign: align, disabled: busy } as const;
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5" title={disabled && compactReason ? disabledReason : undefined} data-testid={testIds.container} data-last-export={report ? JSON.stringify(report) : undefined}>
      <ActionButton {...buttonProps("download")} onClick={() => void run("download")} />
      {caps.copy && <ActionButton {...buttonProps("copy")} onClick={() => void run("copy")} />}
      {caps.share && <ActionButton {...buttonProps("share")} onClick={onShare} />}
      {disabled && disabledReason && <span className={clsx("text-xs text-ink-muted", compactReason && "max-sm:sr-only")}>{disabledReason}</span>}
      {disabled && disabledReason && compactReason && <span aria-hidden className="text-xs text-ink-muted sm:hidden">Unavailable</span>}
      {/* Announced only: the buttons show the outcome, and visible text here would reflow the controls row. */}
      <span role="status" aria-live="polite" className="sr-only">
        {shownStatus}
      </span>
      {job && (
        <div aria-hidden style={{ position: "fixed", left: -100000, top: 0, pointerEvents: "none" }}>
          <div ref={cardRef} style={{ width, height, backgroundColor }} className="bg-surface-card text-ink">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}
