# install.ps1 — one-line datactl installer for Windows. datactl ships as assets
# on DATA GitHub Releases; this installs the build matching your DATA version.
#
# usage:
#   irm https://raw.githubusercontent.com/langgenius/data/main/cli/scripts/install.ps1 | iex
#
# env:
#   DATA_VERSION     DATA release tag to install datactl from (e.g. 1.14.2). Primary key.
#   DATACTL_VERSION  datactl version pin (used only when DATA_VERSION is unset).
#   DATACTL_PREFIX   install dir (default $env:LOCALAPPDATA\datactl)
#   DATACTL_REPO     release source repo (default langgenius/data)

$ErrorActionPreference = 'Stop'

$repo           = if ($env:DATACTL_REPO) { $env:DATACTL_REPO } else { 'langgenius/data' }
$dataVersion    = $env:DATA_VERSION
$datactlVersion = $env:DATACTL_VERSION
$prefix         = if ($env:DATACTL_PREFIX) { $env:DATACTL_PREFIX } else { Join-Path $env:LOCALAPPDATA 'datactl' }
$target         = 'windows-x64'
$apiBase        = "https://api.github.com/repos/$repo"
$dlBase         = "https://github.com/$repo/releases/download"
$headers        = @{ Accept = 'application/vnd.github+json' }

function Get-AssetSemver([string]$Name) {
    if ($Name -notmatch '^datactl-v(.+?)-windows-x64\.exe$') { return $null }
    $v = $Matches[1]
    $core = (($v -split '\+')[0] -split '-')[0]
    if ($core -notmatch '^\d+\.\d+\.\d+$') { return $null }
    $rc = if ($v -match '-rc\.(\d+)') { [int]$Matches[1] } else { [int]::MaxValue }
    return [pscustomobject]@{ Name = $Name; Version = $v; Core = [version]$core; Rc = $rc }
}

function Select-Asset([object]$Release) {
    $Release.assets |
        ForEach-Object { Get-AssetSemver $_.name } |
        Where-Object { $_ } |
        Sort-Object Core, Rc |
        Select-Object -Last 1
}

function Find-ReleaseForDATActl([string]$Want) {
    $releases = Invoke-RestMethod -Uri "$apiBase/releases?per_page=100" -Headers $headers
    foreach ($rel in $releases) {
        $asset = Select-Asset $rel
        if ($asset -and $asset.Version -eq $Want) { return $rel }
    }
    return $null
}

function Resolve-Release {
    if ($dataVersion) {
        try { return Invoke-RestMethod -Uri "$apiBase/releases/tags/$dataVersion" -Headers $headers }
        catch { throw "DATA release $dataVersion not found: $_" }
    }
    elseif ($datactlVersion) {
        $release = Find-ReleaseForDATActl $datactlVersion
        if (-not $release) { throw "datactl $datactlVersion not found on any DATA release" }
        return $release
    }
    else {
        try { return Invoke-RestMethod -Uri "$apiBase/releases/latest" -Headers $headers }
        catch { throw "failed to query latest DATA release (set DATA_VERSION to pin one): $_" }
    }
}

function Invoke-Main {
    $release = Resolve-Release
    $dataTag = $release.tag_name
    $asset = Select-Asset $release
    if (-not $asset) { throw "no datactl published for DATA $dataTag (target $target); set DATA_VERSION to a release that has one" }

    $assetName = $asset.Name
    $ver       = $asset.Version
    $checksums = "datactl-v$ver-checksums.txt"
    $base      = "$dlBase/$dataTag"

    $tmp = Join-Path $env:TEMP ("datactl-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    try {
        Write-Host "downloading $assetName (DATA $dataTag)..."
        $assetPath = Join-Path $tmp $assetName
        $sumsPath  = Join-Path $tmp $checksums
        Invoke-WebRequest -Uri "$base/$assetName" -OutFile $assetPath
        Invoke-WebRequest -Uri "$base/$checksums" -OutFile $sumsPath

        $expected = (Get-Content $sumsPath |
            Where-Object { $_ -match '\s' + [regex]::Escape($assetName) + '$' } |
            ForEach-Object { ($_ -split '\s+')[0] } |
            Select-Object -First 1)
        if (-not $expected) { throw "no checksum entry for $assetName" }
        $actual = (Get-FileHash -Path $assetPath -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $expected.ToLower()) { throw "checksum mismatch for $assetName" }

        $binDir = Join-Path $prefix 'bin'
        New-Item -ItemType Directory -Path $binDir -Force | Out-Null
        $targetBin = Join-Path $binDir 'datactl.exe'
        Copy-Item -Path $assetPath -Destination $targetBin -Force

        Write-Host ""
        Write-Host "datactl v$ver installed (from DATA $dataTag): $targetBin"
        if (($env:PATH -split ';') -notcontains $binDir) {
            Write-Host ""
            Write-Host "$binDir is not on your PATH. Add it with:"
            Write-Host "  [Environment]::SetEnvironmentVariable('PATH', `"$binDir;`$env:PATH`", 'User')"
        }
        else {
            Write-Host 'verify: run "datactl version"'
        }
    }
    finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}

if ($env:DATACTL_INSTALL_LIB -ne '1') { Invoke-Main }
