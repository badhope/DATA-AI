import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite-plus'
import { resolveBuildInfo } from './scripts/lib/resolve-buildinfo.js'

const buildInfo = resolveBuildInfo()

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@test': fileURLToPath(new URL('./test', import.meta.url)),
    },
  },
  pack: {
    entry: ['src/index.ts', 'src/commands/**/*.ts', 'src/framework/**/*.ts'],
    format: ['esm'],
    fixedExtension: false,
    dts: true,
    clean: true,
    sourcemap: true,
    treeshake: false,
    outDir: 'dist',
    target: 'node22',
    define: {
      __DATACTL_VERSION__: JSON.stringify(buildInfo.version),
      __DATACTL_COMMIT__: JSON.stringify(buildInfo.commit),
      __DATACTL_BUILD_DATE__: JSON.stringify(buildInfo.buildDate),
      __DATACTL_CHANNEL__: JSON.stringify(buildInfo.channel),
      __DATACTL_MIN_DATA__: JSON.stringify(buildInfo.minDATA),
      __DATACTL_MAX_DATA__: JSON.stringify(buildInfo.maxDATA),
    },
  },
  test: {
    environment: 'node',
    setupFiles: ['./test/setup.ts'],
    include: ['test/**/*.test.ts', 'src/**/*.test.ts', 'scripts/**/*.test.ts'],
    exclude: ['**/node_modules/**', '**/dist/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'text-summary', 'json'],
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.test.ts', 'src/types/**'],
    },
  },
})
