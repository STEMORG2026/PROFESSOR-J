import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Proxy API calls to the FastAPI backend so the client only ever talks to /api/*
  // on the same origin. Override with NEXT_PUBLIC_API_BASE (e.g. in production).
  async rewrites() {
    const backend = process.env.API_BASE_URL || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
