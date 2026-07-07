import { ImageResponse } from "next/og";

/**
 * Programmatic OpenGraph image. Consumed automatically by Next.js metadata
 * conventions and surfaced via the openGraph/twitter metadata in layout.tsx.
 * No binary asset files required.
 */
export const runtime = "nodejs";
export const alt = "CK's Picks · CFB Model Leans";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "80px",
          background: "linear-gradient(135deg, #0a0a0a 0%, #1e3a8a 100%)",
          color: "#ffffff",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginBottom: 28,
          }}
        >
          <div
            style={{
              width: 84,
              height: 84,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "#2563eb",
              borderRadius: 16,
              fontSize: 44,
              fontWeight: 800,
              letterSpacing: -2,
            }}
          >
            CK
          </div>
          <div style={{ fontSize: 28, color: "#93c5fd", fontWeight: 600 }}>
            CFB
          </div>
        </div>
        <div
          style={{
            fontSize: 76,
            fontWeight: 800,
            lineHeight: 1.05,
            letterSpacing: -2,
            marginBottom: 20,
          }}
        >
          CK&rsquo;s Picks
        </div>
        <div style={{ fontSize: 34, color: "#cbd5e1", maxWidth: 900 }}>
          Weekly model leans for every FBS game.
        </div>
        <div
          style={{
            marginTop: 48,
            display: "flex",
            gap: 24,
            fontSize: 22,
            color: "#94a3b8",
          }}
        >
          <span>Spreads</span>
          <span style={{ color: "#475569" }}>&middot;</span>
          <span>Totals</span>
          <span style={{ color: "#475569" }}>&middot;</span>
          <span>Edges vs market</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
