import type { NextConfig } from "next";

// Require BACKEND_URL - no fallbacks to avoid silent failures
const BACKEND_URL = process.env.BACKEND_URL;
if (!BACKEND_URL) {
  throw new Error(
    "Missing required environment variable: BACKEND_URL. " +
    "Set it in .env.local (e.g., BACKEND_URL=http://localhost:7860)"
  );
}

const nextConfig: NextConfig = {
  // Allow development requests from common remote dev environments
  allowedDevOrigins: [
    "localhost:3000",
    "localhost:3001",
    "localhost:3003",
    // Tailscale/remote dev IPs
    "100.89.76.91",
    "10.1.10.192",
  ],
  async rewrites() {
    return [
      {
        source: "/api/chat",
        destination: `${BACKEND_URL}/get-message`,
      },
      {
        source: "/api/image",
        destination: `${BACKEND_URL}/api/full_image`,
      },
    ];
  },
};

export default nextConfig;
