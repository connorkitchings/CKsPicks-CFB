"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { MatchupData } from "@/lib/matchup";
import { ShareCard, SHARE_CARD_HEIGHT, SHARE_CARD_WIDTH } from "./ShareCard";

type Action = "share" | "copy" | "download";

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

function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export function shareFileName(matchup: Pick<MatchupData, "awayTeam" | "homeTeam" | "season" | "week">): string {
  return `ckspicks-${slug(matchup.awayTeam)}-at-${slug(matchup.homeTeam)}-${matchup.season}-week-${matchup.week}.png`;
}

/** Wait for fonts and for every image in the card, so the capture is not taken half-loaded. */
async function settle(node: HTMLElement): Promise<void> {
  await document.fonts?.ready;
  await Promise.all(
    Array.from(node.querySelectorAll("img")).map((img) =>
      img.complete
        ? img.decode().catch(() => undefined)
        : new Promise<void>((done) => {
            img.addEventListener("load", () => done(), { once: true });
            img.addEventListener("error", () => done(), { once: true });
          }),
    ),
  );
}

async function renderPng(node: HTMLElement): Promise<Blob> {
  await settle(node);
  const { toBlob } = await import("html-to-image");
  const options = {
    pixelRatio: 2,
    width: SHARE_CARD_WIDTH,
    height: SHARE_CARD_HEIGHT,
    backgroundColor: "#0b0b0d",
  };
  // Safari draws images and fonts only on a second pass.
  if (/^((?!chrome|android).)*safari/i.test(navigator.userAgent)) await toBlob(node, options);
  const blob = await toBlob(node, options);
  if (!blob) throw new Error("The card could not be rendered");
  return blob;
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
const canShareFiles = () =>
  typeof navigator.canShare === "function" &&
  navigator.canShare({ files: [new File([""], "probe.png", { type: "image/png" })] });
const canCopyImages = () => typeof ClipboardItem !== "undefined" && Boolean(navigator.clipboard?.write);

const buttonClass =
  "inline-flex items-center rounded-lg border border-line bg-surface-elevated px-2.5 py-1 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink disabled:cursor-wait disabled:opacity-60";

/**
 * Exports the matchup as one fixed-size image (see ShareCard). The card is only
 * mounted while an image is being made, so the page itself is unchanged.
 */
export function ShareButton({ matchup }: { matchup: MatchupData }) {
  const [job, setJob] = useState<Action | null>(null);
  const [status, setStatus] = useState("");
  const [ready, setReady] = useState<File | null>(null);
  const caps = {
    share: useSyncExternalStore(subscribeNever, canShareFiles, serverFalse),
    copy: useSyncExternalStore(subscribeNever, canCopyImages, serverFalse),
  };
  const cardRef = useRef<HTMLDivElement>(null);
  const pending = useRef<Deferred<Blob> | null>(null);
  const filename = shareFileName(matchup);

  const rendered = useRef<Deferred<Blob> | null>(null);

  useEffect(() => {
    const done = pending.current;
    if (!job || !cardRef.current || !done || rendered.current === done) return; // strict mode runs effects twice
    rendered.current = done;
    renderPng(cardRef.current)
      .then((blob) => done?.resolve(blob))
      .catch((error) => done?.reject(error));
  }, [job]);

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
        return;
      }
      const blob = await render.promise;
      if (action === "download") {
        saveBlob(blob, filename);
        setStatus("Image saved");
        return;
      }
      const file = new File([blob], filename, { type: "image/png" });
      try {
        await navigator.share({ files: [file], title: `${matchup.awayTeam} at ${matchup.homeTeam}` });
        setStatus("");
      } catch (error) {
        if ((error as Error).name === "AbortError") {
          setStatus("");
        } else {
          // Some browsers only share inside a fresh tap: keep the image and let the next tap share it.
          setReady(file);
          setStatus("Image ready: tap Share again");
        }
      }
    } catch {
      setStatus("Could not create the image");
    } finally {
      setJob(null);
      pending.current = null;
    }
  }

  async function shareReady() {
    if (!ready) return;
    try {
      await navigator.share({ files: [ready], title: `${matchup.awayTeam} at ${matchup.homeTeam}` });
      setStatus("");
    } catch {
      saveBlob(ready, filename);
      setStatus("Image saved");
    }
    setReady(null);
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="share-controls">
      {caps.share && (
        <button
          type="button"
          className={buttonClass}
          data-testid="share-button"
          disabled={job !== null}
          onClick={() => (ready ? void shareReady() : void run("share"))}
        >
          Share
        </button>
      )}
      {!caps.share && caps.copy && (
        <button
          type="button"
          className={buttonClass}
          data-testid="share-copy"
          disabled={job !== null}
          onClick={() => void run("copy")}
        >
          Copy image
        </button>
      )}
      <button
        type="button"
        className={buttonClass}
        data-testid="share-download"
        disabled={job !== null}
        onClick={() => void run("download")}
      >
        Download PNG
      </button>
      <span role="status" aria-live="polite" className="text-[11px] text-ink-faint">
        {status}
      </span>
      {job && (
        <div aria-hidden style={{ position: "fixed", left: -100000, top: 0, pointerEvents: "none" }}>
          <ShareCard ref={cardRef} matchup={matchup} />
        </div>
      )}
    </div>
  );
}
