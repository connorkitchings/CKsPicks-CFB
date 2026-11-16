import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  turbopack: {
    root: process.cwd(),
  },
  // `/ratings` is permanent (308); the rest stay 307 until the owner accepts. Query strings are forwarded automatically.
  async redirects() {
    return [
      { source: "/ratings", destination: "/teams", permanent: true },
      { source: "/results", destination: "/", permanent: false },
      { source: "/matchup", destination: "/", permanent: false },
      { source: "/performance", destination: "/model", permanent: false },
      { source: "/methodology", destination: "/model/method", permanent: false },
      { source: "/charts", destination: "/stats", permanent: false },
      { source: "/charts/:path*", destination: "/stats/:path*", permanent: false },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
        ],
      },
      {
        // Content-addressed by version prefix: bump `v2` to invalidate.
        source: "/logos/v2/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};

export default nextConfig;
