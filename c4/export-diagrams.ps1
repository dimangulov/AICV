#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Exports C4 diagrams from c4/workspace.dsl to responsive SVGs via the
    C4 CLI Docker image and writes them to frontend/public/diagrams/.

.DESCRIPTION
    Requirements:
      - Docker Desktop running (no local Java / CLI install needed)

    The exported SVGs are post-processed to:
      - Remove the <?xml?> declaration (invalid in inline SVG contexts)
      - Strip fixed pixel width/height from the root <svg> element
        (keeping viewBox so the diagram scales correctly)

    The SVG files are loaded inline by the DiagramViewer component, which
    means the page stylesheet's CSS variables fully control theming
    (defined in frontend/app/globals.css under "C4 Diagram Theme").

.EXAMPLE
    pwsh c4/export-diagrams.ps1

.NOTES
    Re-run whenever c4/workspace.dsl changes.
    Output path: frontend/public/diagrams/*.svg
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$c4Dir     = $PSScriptRoot
$repoRoot  = Split-Path $c4Dir -Parent
$outputDir = Join-Path $repoRoot "frontend" "public" "diagrams"
$tmpName   = "_export_tmp"
$tmpDir    = Join-Path $c4Dir $tmpName

# ── Verify Docker is available ────────────────────────────────────────────────
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw }
} catch {
    Write-Error "Docker is not running or not installed. Start Docker Desktop and try again."
}

# ── Clean tmp output directory ────────────────────────────────────────────────
if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
New-Item $tmpDir -ItemType Directory -Force | Out-Null

Write-Host ""
Write-Host "Structurizr CLI — Mermaid Export" -ForegroundColor Cyan
Write-Host "  workspace : c4/workspace.dsl"
Write-Host "  output    : frontend/public/diagrams/"
Write-Host ""

# ── Run Structurizr CLI via Docker ────────────────────────────────────────────
# Mounts the entire c4/ directory; output goes to c4/_export_tmp/
docker run --rm `
    -v "${c4Dir}:/usr/local/structurizr" `
    structurizr/cli:latest export `
        -workspace /usr/local/structurizr/workspace.dsl `
        -format    mermaid `
        -output    /usr/local/structurizr/$tmpName

if ($LASTEXITCODE -ne 0) {
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    throw "Structurizr CLI exited with code $LASTEXITCODE"
}

# ── Find exported .mmd files ──────────────────────────────────────────────────
$mmdFiles = @(Get-ChildItem $tmpDir -Filter "*.mmd" -ErrorAction SilentlyContinue)
if ($mmdFiles.Count -eq 0) {
    Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    throw "No .mmd files found in the export output. Check workspace.dsl view definitions."
}

# ── Ensure output directory exists ────────────────────────────────────────────
if (-not (Test-Path $outputDir)) {
    New-Item $outputDir -ItemType Directory -Force | Out-Null
}

# ── Copy each .mmd file to public/diagrams/ ──────────────────────────────────
$count = 0
foreach ($f in $mmdFiles) {
    $dstPath = Join-Path $outputDir $f.Name
    Copy-Item $f.FullName $dstPath -Force
    Write-Host ("  {0,-45} -> diagrams/{1}" -f $f.Name, $f.Name) -ForegroundColor Green
    $count++
}

# ── Cleanup temp directory ────────────────────────────────────────────────────
Remove-Item $tmpDir -Recurse -Force

Write-Host ""
Write-Host "$count diagram(s) exported successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Filenames (used in C4DiagramsSection):" -ForegroundColor DarkGray
$mmdFiles | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Blue
}
Write-Host ""
Write-Host "Restart the Next.js dev server if it is already running." -ForegroundColor DarkGray
