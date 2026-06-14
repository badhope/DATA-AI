import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const SCRIPT = fileURLToPath(new URL('./install.ps1', import.meta.url))

function hasPwsh(): boolean {
  const r = spawnSync('pwsh', ['-NoProfile', '-NonInteractive', '-Command', '$PSVersionTable.PSVersion.Major'], {
    encoding: 'utf8',
  })
  return r.status === 0
}

const PWSH = hasPwsh()

const STUB = [
  'function Invoke-RestMethod {',
  '    param([string]$Uri, $Headers)',
  '    if ($Uri -like \'*/releases/latest\') {',
  '        if (-not $env:HX_LATEST) { throw \'mock 404\' }',
  '        return ($env:HX_LATEST | ConvertFrom-Json)',
  '    }',
  '    elseif ($Uri -like \'*/releases?per_page=100\') {',
  '        if (-not $env:HX_LIST) { throw \'mock 404\' }',
  '        return ($env:HX_LIST | ConvertFrom-Json)',
  '    }',
  '    elseif ($Uri -like \'*/releases/tags/*\') {',
  '        $t = $Uri -replace \'.*/releases/tags/\', \'\'',
  '        $k = \'HX_TAG_\' + ($t -replace \'[.\\-]\', \'_\')',
  '        $v = [Environment]::GetEnvironmentVariable($k)',
  '        if (-not $v) { throw \'mock 404\' }',
  '        return ($v | ConvertFrom-Json)',
  '    }',
  '    throw "unexpected uri $Uri"',
  '}',
].join('\n')

type Run = { code: number, stdout: string, stderr: string }

function runPwsh(body: string, env: Record<string, string> = {}): Run {
  const script = `$ErrorActionPreference='Stop'\n${STUB}\n. '${SCRIPT}'\n${body}`
  const r = spawnSync('pwsh', ['-NoProfile', '-NonInteractive', '-Command', script], {
    encoding: 'utf8',
    env: {
      ...process.env,
      DATACTL_INSTALL_LIB: '1',
      DATA_VERSION: '',
      DATACTL_VERSION: '',
      LOCALAPPDATA: process.env.LOCALAPPDATA || '/tmp',
      TEMP: process.env.TEMP || '/tmp',
      ...env,
    },
  })
  return { code: r.status ?? 1, stdout: (r.stdout ?? '').trim(), stderr: r.stderr ?? '' }
}

const REL_1142 = JSON.stringify({ tag_name: '1.14.2', assets: [{ name: 'datactl-v0.2.0-windows-x64.exe' }] })
const REL_1150 = JSON.stringify({ tag_name: '1.15.0', assets: [{ name: 'datactl-v0.3.0-windows-x64.exe' }] })
const LIST_NEWEST_FIRST = JSON.stringify([
  { tag_name: '1.15.0', assets: [{ name: 'datactl-v0.3.0-windows-x64.exe' }] },
  { tag_name: '1.14.2', assets: [{ name: 'datactl-v0.2.0-windows-x64.exe' }] },
])

describe.skipIf(!PWSH)('install.ps1 Get-AssetSemver', () => {
  it('extracts the version from a windows .exe asset name', () => {
    const r = runPwsh('(Get-AssetSemver \'datactl-v0.2.0-windows-x64.exe\').Version')
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('0.2.0')
  })

  it('extracts a prerelease version and its rc number', () => {
    const r = runPwsh('$a = Get-AssetSemver \'datactl-v0.1.0-rc.1-windows-x64.exe\'; "$($a.Version) $($a.Rc)"')
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('0.1.0-rc.1 1')
  })

  it('rejects a non-windows asset (returns null)', () => {
    const r = runPwsh('if ($null -eq (Get-AssetSemver \'datactl-v0.2.0-linux-x64\')) { \'NULL\' } else { \'OBJ\' }')
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('NULL')
  })

  it('rejects a malformed core version (returns null)', () => {
    const r = runPwsh('if ($null -eq (Get-AssetSemver \'datactl-vx.y.z-windows-x64.exe\')) { \'NULL\' } else { \'OBJ\' }')
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('NULL')
  })
})

describe.skipIf(!PWSH)('install.ps1 Select-Asset', () => {
  it('picks the highest semver among several windows builds', () => {
    const rel = JSON.stringify({ assets: [
      { name: 'datactl-v0.2.0-windows-x64.exe' },
      { name: 'datactl-v0.10.0-windows-x64.exe' },
      { name: 'datactl-v0.9.0-windows-x64.exe' },
    ] })
    const r = runPwsh(`(Select-Asset ('${rel}' | ConvertFrom-Json)).Version`)
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('0.10.0')
  })

  it('prefers the stable release over an rc of the same core', () => {
    const rel = JSON.stringify({ assets: [
      { name: 'datactl-v0.2.0-rc.1-windows-x64.exe' },
      { name: 'datactl-v0.2.0-windows-x64.exe' },
    ] })
    const r = runPwsh(`(Select-Asset ('${rel}' | ConvertFrom-Json)).Version`)
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('0.2.0')
  })

  it('ignores checksums and non-windows assets', () => {
    const rel = JSON.stringify({ assets: [
      { name: 'datactl-v0.2.0-linux-x64' },
      { name: 'datactl-v0.2.0-checksums.txt' },
      { name: 'datactl-v0.2.0-windows-x64.exe' },
      { name: 'some-other-asset.zip' },
    ] })
    const r = runPwsh(`(Select-Asset ('${rel}' | ConvertFrom-Json)).Name`)
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('datactl-v0.2.0-windows-x64.exe')
  })

  it('yields null when no windows asset is present', () => {
    const rel = JSON.stringify({ assets: [{ name: 'datactl-v0.2.0-linux-x64' }] })
    const r = runPwsh(`if ($null -eq (Select-Asset ('${rel}' | ConvertFrom-Json))) { 'NULL' } else { 'OBJ' }`)
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('NULL')
  })
})

describe.skipIf(!PWSH)('install.ps1 Resolve-Release', () => {
  it('DATA_VERSION pins the release directly', () => {
    const r = runPwsh('(Resolve-Release).tag_name', { DATA_VERSION: '1.14.2', HX_TAG_1_14_2: REL_1142 })
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('1.14.2')
  })

  it('DATA_VERSION that does not exist throws a clear message', () => {
    const r = runPwsh('(Resolve-Release).tag_name', { DATA_VERSION: '9.9.9' })
    expect(r.code).not.toBe(0)
    expect(r.stderr).toContain('DATA release 9.9.9 not found')
  })

  it('blank resolves to the latest release', () => {
    const r = runPwsh('(Resolve-Release).tag_name', { HX_LATEST: REL_1150 })
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('1.15.0')
  })

  it('blank throws when the latest query fails (no silent fallback)', () => {
    const r = runPwsh('(Resolve-Release).tag_name')
    expect(r.code).not.toBe(0)
    expect(r.stderr).toContain('failed to query latest DATA release')
  })

  it('DATACTL_VERSION resolves to the release hosting that build', () => {
    const r = runPwsh('(Resolve-Release).tag_name', { DATACTL_VERSION: '0.2.0', HX_LIST: LIST_NEWEST_FIRST })
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('1.14.2')
  })

  it('DATACTL_VERSION not hosted anywhere throws', () => {
    const r = runPwsh('(Resolve-Release).tag_name', { DATACTL_VERSION: '9.9.9', HX_LIST: LIST_NEWEST_FIRST })
    expect(r.code).not.toBe(0)
    expect(r.stderr).toContain('datactl 9.9.9 not found on any DATA release')
  })
})

describe.skipIf(!PWSH)('install.ps1 Find-ReleaseForDATActl', () => {
  it('returns the newest release whose assets host the wanted build', () => {
    const r = runPwsh('(Find-ReleaseForDATActl \'0.2.0\').tag_name', { HX_LIST: LIST_NEWEST_FIRST })
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('1.14.2')
  })

  it('returns nothing when no release hosts the wanted build', () => {
    const r = runPwsh('$x = Find-ReleaseForDATActl \'9.9.9\'; if ($null -eq $x) { \'NULL\' } else { $x.tag_name }', { HX_LIST: LIST_NEWEST_FIRST })
    expect(r.code).toBe(0)
    expect(r.stdout).toBe('NULL')
  })
})
