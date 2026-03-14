#Requires -Version 5.1
<#
.SYNOPSIS
    One-shot local development setup for the Interactive Digital Twin CV.
.DESCRIPTION
    - Checks prerequisites (Ollama, Docker, Node.js, Python, pnpm)
    - Pulls required Ollama models
    - Creates .env files from examples if they don't exist
    - Starts Qdrant in Docker (optional)
    - Installs frontend dependencies
    - Sets up Python virtual environment and installs backend dependencies
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Helpers ───────────────────────────────────────────────────────────────────

function Write-Step([string]$msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

function Write-OK([string]$msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "  [WARN] $msg" -ForegroundColor Yellow
}

function Write-Fail([string]$msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
}

function Test-Command([string]$name) {
    return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

# ── Root of the repo ──────────────────────────────────────────────────────────

$repoRoot = $PSScriptRoot
Set-Location $repoRoot

# ── 1. Prerequisites check ────────────────────────────────────────────────────

Write-Step "Checking prerequisites"

$missing = @()

if (Test-Command 'ollama') { Write-OK "Ollama found: $(ollama --version 2>&1 | Select-Object -First 1)" }
else { Write-Fail "Ollama not found — install from https://ollama.com"; $missing += 'ollama' }

if (Test-Command 'docker') { Write-OK "Docker found: $(docker --version)" }
else { Write-Warn "Docker not found — Qdrant Docker start will be skipped (QDRANT_MODE=memory will be used)" }

if (Test-Command 'node') { Write-OK "Node.js found: $(node --version)" }
else { Write-Fail "Node.js not found — install from https://nodejs.org"; $missing += 'node' }

if (Test-Command 'pnpm') { Write-OK "pnpm found: $(pnpm --version)" }
elseif (Test-Command 'npm') { Write-Warn "pnpm not found — installing via npm..."; npm install -g pnpm }
else { Write-Fail "npm/pnpm not found"; $missing += 'pnpm' }

if (Test-Command 'python') { Write-OK "Python found: $(python --version)" }
elseif (Test-Command 'python3') { Write-OK "Python3 found: $(python3 --version)" }
else { Write-Fail "Python not found — install from https://python.org"; $missing += 'python' }

if ($missing.Count -gt 0) {
    Write-Host "`nThe following required tools are missing: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Please install them and re-run this script." -ForegroundColor Red
    exit 1
}

# ── 2. Pull Ollama models ─────────────────────────────────────────────────────

Write-Step "Pulling Ollama models"

Write-Host "  Pulling llama3.2 (chat model)..." -ForegroundColor Gray
ollama pull llama3.2
Write-OK "llama3.2 ready"

Write-Host "  Pulling nomic-embed-text (embedding model)..." -ForegroundColor Gray
ollama pull nomic-embed-text
Write-OK "nomic-embed-text ready"

# ── 3. Create .env files ──────────────────────────────────────────────────────

Write-Step "Creating environment files"

$backendEnv = Join-Path $repoRoot 'backend\.env'
$backendEnvExample = Join-Path $repoRoot 'backend\.env.example'

if (-not (Test-Path $backendEnv)) {
    Copy-Item $backendEnvExample $backendEnv
    Write-OK "Created backend/.env from .env.example"
} else {
    Write-Warn "backend/.env already exists — skipping (delete it to reset)"
}

$frontendEnv = Join-Path $repoRoot 'frontend\.env.local'
$frontendEnvExample = Join-Path $repoRoot 'frontend\.env.local.example'

if (-not (Test-Path $frontendEnv)) {
    Copy-Item $frontendEnvExample $frontendEnv
    Write-OK "Created frontend/.env.local from .env.local.example"
} else {
    Write-Warn "frontend/.env.local already exists — skipping"
}

# ── 4. Qdrant (optional Docker) ───────────────────────────────────────────────

Write-Step "Qdrant setup"

if (Test-Command 'docker') {
    $compose = Join-Path $repoRoot 'docker-compose.yml'
    Write-Host "  Starting Qdrant via Docker Compose..." -ForegroundColor Gray
    docker compose -f $compose up -d qdrant
    Write-OK "Qdrant container started (REST: http://localhost:6333)"
    Write-Host "  Note: backend/.env uses QDRANT_MODE=memory by default." -ForegroundColor Gray
    Write-Host "        Change to QDRANT_MODE=docker to use this container." -ForegroundColor Gray
} else {
    Write-Warn "Docker not available — Qdrant skipped. Backend will use in-memory mode."
}

# ── 5. Frontend dependencies ──────────────────────────────────────────────────

Write-Step "Installing frontend dependencies"

Push-Location (Join-Path $repoRoot 'frontend')
pnpm install
Write-OK "Frontend node_modules installed"
Pop-Location

# ── 6. Backend virtual environment ────────────────────────────────────────────

Write-Step "Setting up Python virtual environment"

$venvPath = Join-Path $repoRoot 'backend\.venv'

if (-not (Test-Path $venvPath)) {
    $pyCmd = if (Test-Command 'python') { 'python' } else { 'python3' }
    & $pyCmd -m venv $venvPath
    Write-OK "Virtual environment created at backend/.venv"
} else {
    Write-Warn "backend/.venv already exists — skipping creation"
}

$pip = Join-Path $venvPath 'Scripts\pip.exe'
& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $repoRoot 'backend\requirements.txt') --quiet
Write-OK "Python dependencies installed"

# ── Done ──────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "  Setup complete! Start the dev servers:" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend:" -ForegroundColor White
Write-Host "    cd backend" -ForegroundColor Gray
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "    uvicorn main:app --reload --port 8000" -ForegroundColor Gray
Write-Host ""
Write-Host "  Frontend (new terminal):" -ForegroundColor White
Write-Host "    cd frontend" -ForegroundColor Gray
Write-Host "    pnpm dev" -ForegroundColor Gray
Write-Host ""
Write-Host "  Open: http://localhost:3000" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
