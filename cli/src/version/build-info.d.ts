// Build-time globals injected by vite-plus. Single source of truth — both
// info.ts (client identity) and compat.ts (supported data range) read from
// here. Values are computed in scripts/lib/resolve-buildinfo.ts.
declare const __DATACTL_VERSION__: string
declare const __DATACTL_COMMIT__: string
declare const __DATACTL_BUILD_DATE__: string
declare const __DATACTL_CHANNEL__: string
declare const __DATACTL_MIN_DATA__: string
declare const __DATACTL_MAX_DATA__: string
