"use client";

import { ExportActions } from "@/components/ui/ExportActions";
import type { MatchupData } from "@/lib/matchup";
import { ShareCard, SHARE_CARD_HEIGHT, SHARE_CARD_WIDTH } from "./ShareCard";

function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export function shareFileName(matchup: Pick<MatchupData, "awayTeam" | "homeTeam" | "season" | "week">): string {
  return `ckspicks-${slug(matchup.awayTeam)}-at-${slug(matchup.homeTeam)}-${matchup.season}-week-${matchup.week}.png`;
}

const TEST_IDS = {
  container: "share-controls",
  download: "share-download",
  copy: "share-copy",
  share: "share-button",
} as const;

/**
 * Exports the matchup as one fixed-size image (see ShareCard) through the same export
 * actions the charts use. The card is only mounted while an image is being made, so the page
 * itself is unchanged.
 */
export function ShareButton({ matchup, disabled = false }: { matchup: MatchupData; disabled?: boolean }) {
  return (
    <ExportActions
      filename={shareFileName(matchup)}
      shareTitle={`${matchup.awayTeam} at ${matchup.homeTeam}`}
      width={SHARE_CARD_WIDTH}
      height={SHARE_CARD_HEIGHT}
      backgroundColor="#0b0b0d"
      disabled={disabled}
      disabledReason="Sharing unavailable until matchup data lineage is verified"
      tooltipAlign="left"
      testIds={TEST_IDS}
    >
      <ShareCard matchup={matchup} />
    </ExportActions>
  );
}
