import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: false,
  // Static export disables Image Optimization API — use unoptimized images or next/image with loader
  images: { unoptimized: true },
};

export default nextConfig;
