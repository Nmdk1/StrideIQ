/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // Ensure app directory is included in standalone build
  experimental: {
    outputFileTracingIncludes: {
      '/**': ['./app/**/*'],
    },
  },
}

module.exports = nextConfig

