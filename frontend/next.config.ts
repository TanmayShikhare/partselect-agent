import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "www.partselect.com" },
      { protocol: "https", hostname: "partselect.com" },
      // Common PartSelect image/CDN hosts (keep this list tight).
      { protocol: "https", hostname: "images.partselect.com" },
      { protocol: "https", hostname: "www.partselect.ca" },
    ],
  },
};

export default nextConfig;
