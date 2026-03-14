import type { NextConfig } from "next";

// When NEXT_OUTPUT=export the app is compiled to a fully-static site (no Node server needed).
// This is the target mode for Azure Static Web Apps Free tier deployment.
// Local development keeps SSR capabilities by leaving this unset.
const isStaticExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  output: isStaticExport ? "export" : undefined,
  // Required for static export: trailing slashes ensure correct asset resolution on SWA.
  trailingSlash: isStaticExport,
  images: {
    // next/image optimisation is not available in static export mode.
    unoptimized: isStaticExport,
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.liveavatar.com",
      },
    ],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
