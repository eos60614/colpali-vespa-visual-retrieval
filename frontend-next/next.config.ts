import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Proxy API calls to the Python backend during development
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:7860"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
