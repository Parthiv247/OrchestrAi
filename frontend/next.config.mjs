/** @type {import('next').NextConfig} */
const nextConfig = {
  // Dashboard app — all pages are dynamic (live API data, no static prerendering)
  output: 'standalone',
  eslint: {
    // Warnings don't block production builds
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
}

export default nextConfig
