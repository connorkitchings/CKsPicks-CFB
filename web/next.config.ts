import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  turbopack: {
    root: process.cwd(),
  },
  // 307 first; moves to 308 after the owner accepts. Query strings are forwarded automatically.
  async redirects() {
    return [
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
        // Content-addressed by version prefix: bump `v2` to invalidate.
        source: "/logos/v2/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};

export default nextConfig;
