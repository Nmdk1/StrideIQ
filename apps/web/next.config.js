/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  assetPrefix: '',
  basePath: '',
  trailingSlash: false,
  async headers() {
    return [
      {
        source: '/manifest.json',
        headers: [
          {
            key: 'Cache-Control',
            value: 'no-cache, max-age=0, must-revalidate',
          },
        ],
      },
    ];
  },
}

module.exports = nextConfig
