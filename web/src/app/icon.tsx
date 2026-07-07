import { ImageResponse } from "next/og";

/**
 * Programmatic favicon: "CK" monogram on a brand-blue field.
 * Consumed automatically by Next.js metadata conventions (served at /icon).
 */
export const runtime = "nodejs";
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#2563eb",
          color: "#ffffff",
          fontSize: 18,
          fontWeight: 800,
          letterSpacing: -1,
          fontFamily: "sans-serif",
        }}
      >
        CK
      </div>
    ),
    { ...size },
  );
}
