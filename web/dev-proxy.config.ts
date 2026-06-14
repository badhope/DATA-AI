import type { CookieRewriteOptions, DevProxyConfig } from '@langgenius/dev-proxy'

const DATA_CLOUD_TARGET = 'https://cloud.data.ai'
const DEV_PROXY_TARGET = process.env.DEV_PROXY_TARGET || DATA_CLOUD_TARGET
const DEV_PROXY_ENTERPRISE_TARGET = process.env.DEV_PROXY_ENTERPRISE_TARGET || DEV_PROXY_TARGET
const DEV_PROXY_PUBLIC_TARGET = process.env.DEV_PROXY_PUBLIC_TARGET || DEV_PROXY_TARGET
const DEV_PROXY_HOST = process.env.DEV_PROXY_HOST || '127.0.0.1'
const DEV_PROXY_PORT = Number(process.env.DEV_PROXY_PORT || 5001)

const dataCookieRewrite: CookieRewriteOptions = {
  hostPrefixCookies: [
    'access_token',
    'csrf_token',
    'refresh_token',
    'webapp_access_token',
    /^passport-/,
  ],
  localCookieScope: 'target-origin',
  csrfHeader: {
    cookieName: 'csrf_token',
    headerName: 'X-CSRF-Token',
  },
}

export default {
  server: {
    host: DEV_PROXY_HOST,
    port: DEV_PROXY_PORT,
  },
  routes: [
    {
      paths: [
        '/console/api/enterprise',
        '/api/enterprise',
        '/admin-api',
        '/inner/api',
        '/mfa',
        '/scim',
        '/v1/audit',
        '/v1/dashboard',
        '/v1/healthz',
        '/v1/plugin-manager',
      ],
      target: DEV_PROXY_ENTERPRISE_TARGET,
      cookieRewrite: dataCookieRewrite,
    },
    {
      paths: [
        '/console/api',
      ],
      target: DEV_PROXY_TARGET,
      cookieRewrite: dataCookieRewrite,
    },
    {
      paths: [
        '/api',
      ],
      target: DEV_PROXY_PUBLIC_TARGET,
      cookieRewrite: dataCookieRewrite,
    },
  ],
} satisfies DevProxyConfig
