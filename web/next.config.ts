import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:7860";

const nextConfig: NextConfig = {
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
