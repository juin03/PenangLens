import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'penanglensstorage.blob.core.windows.net',
      },
    ],
  },
};

export default nextConfig;
