import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  allowedDevOrigins: [
    '172.20.192.1',
    '172.31.32.1',
    '172.31.0.0/16',
    'localhost',
    '127.0.0.1',
  ],
  async rewrites() {
    // API_BACKEND_URL permite trocar a rota quando roda dentro do Docker (host.docker.internal)
    const backendUrl = process.env.API_BACKEND_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
