import Image from "next/image";
import type { Lean } from "@/lib/picks-proto";
import { logoUrl } from "@/lib/teams";

/**
 * Direction marker for a lean: the backed team's logo for a spread, and an
 * up/down arrow for a total (over / under).
 */
export function LeanMarker({ lean }: { lean: Lean }) {
  if (lean.kind === "total") {
    return (
      <span aria-hidden className="w-4 shrink-0 text-center text-xs leading-none text-accent">
        {lean.dir === "over" ? "▲" : "▼"}
      </span>
    );
  }
  return (
    <Image
      src={logoUrl(lean.team ?? "")}
      alt=""
      width={16}
      height={16}
      className="shrink-0 object-contain"
      style={{ width: 16, height: 16 }}
      unoptimized
    />
  );
}
