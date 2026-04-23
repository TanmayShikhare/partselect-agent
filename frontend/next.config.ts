import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "www.partselect.com" },
      { protocol: "https", hostname: "partselect.com" },
      // Some search results return CDN URLs; allow HTTPS for demo safety.
      { protocol: "https", hostname: "**" },
    ],
  },
};

export default nextConfig;
