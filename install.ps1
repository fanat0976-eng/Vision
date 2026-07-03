# Vision AI Agent - PowerShell Installer
# For clean Windows 10/11 machines

$ErrorActionPreference = "Continue"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Vision AI Agent - Installer" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================
# Helper functions
# ============================================

function Test-Command($cmd) {
    try {
        $null = Get-Command $cmd -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Install-WingetPackage($id, $name, $downloadUrl) {
    # Check if winget is available
    if (-not (Test-Command "winget")) {
        Write-Host "[-] winget not found. Manual install required:" -ForegroundColor Yellow
        Write-Host "    Download: $downloadUrl" -ForegroundColor DarkGray
        Write-Host "    After install, restart this script." -ForegroundColor DarkGray
        return $false
    }
    Write-Host "[*] Installing $name via winget..." -ForegroundColor Yellow
    try {
        winget install --id $id --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[+] $name installed" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "[-] winget failed for $name" -ForegroundColor Red
    }
    Write-Host "    Manual install: $downloadUrl" -ForegroundColor DarkGray
    return $false
}

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# ============================================
# 1. Check/Install Python 3.11+
# ============================================

Write-Host "--------------------------------------------" -ForegroundColor White
Write-Host "[1/5] Checking Python..." -ForegroundColor Cyan

$pythonOk = $false
if (Test-Command "python") {
    $pyVer = python --version 2>&1
    if ($pyVer -match "Python 3\.1[1-9]") {
        Write-Host "[+] $pyVer found" -ForegroundColor Green
        $pythonOk = $true
    } else {
        Write-Host "[-] $pyVer found, need 3.11+" -ForegroundColor Yellow
    }
}

if (-not $pythonOk) {
    Write-Host "[*] Installing Python 3.12..." -ForegroundColor Yellow
    Install-WingetPackage "Python.Python.3.12" "Python 3.12" "https://www.python.org/downloads/"
    Refresh-Path

    # Verify
    if (Test-Command "python") {
        $pyVer = python --version 2>&1
        Write-Host "[+] $pyVer installed" -ForegroundColor Green
    } else {
        Write-Host "[!] Python not found after install. Restart terminal." -ForegroundColor Red
        Write-Host "    Download manually: https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "    IMPORTANT: Check 'Add Python to PATH' during install" -ForegroundColor Yellow
    }
}

# ============================================
# 2. Check/Install Git
# ============================================

Write-Host ""
Write-Host "[2/5] Checking Git..." -ForegroundColor Cyan

if (Test-Command "git") {
    $gitVer = git --version
    Write-Host "[+] $gitVer" -ForegroundColor Green
} else {
    Write-Host "[*] Installing Git..." -ForegroundColor Yellow
    Install-WingetPackage "Git.Git" "Git" "https://git-scm.com/download/win"
    Refresh-Path
}

# ============================================
# 3. Check/Install Ollama
# ============================================

Write-Host ""
Write-Host "[3/5] Checking Ollama..." -ForegroundColor Cyan

$ollamaOk = $false
if (Test-Command "ollama") {
    Write-Host "[+] Ollama found" -ForegroundColor Green
    $ollamaOk = $true
} else {
    Write-Host "[*] Installing Ollama..." -ForegroundColor Yellow
    # Download Ollama installer
    $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
    $ollamaInstaller = "$env:TEMP\OllamaSetup.exe"
    try {
        Invoke-WebRequest -Uri $ollamaUrl -OutFile $ollamaInstaller -UseBasicParsing
        Start-Process -FilePath $ollamaInstaller -Wait
        Refresh-Path
        $ollamaOk = $true
        Write-Host "[+] Ollama installed" -ForegroundColor Green
    } catch {
        Write-Host "[-] Auto-install failed. Download manually:" -ForegroundColor Red
        Write-Host "    https://ollama.com/download" -ForegroundColor Yellow
    }
}

# Start Ollama if installed
if ($ollamaOk -or (Test-Command "ollama")) {
    $ollamaProcess = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
    if (-not $ollamaProcess) {
        Write-Host "[*] Starting Ollama..." -ForegroundColor Yellow
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 3
    }

    # Pull models
    Write-Host "[*] Pulling Ollama models (qwen2.5:14b, nomic-embed-text)..." -ForegroundColor Yellow
    Write-Host "    This may take several minutes on first run..." -ForegroundColor DarkGray
    try {
        ollama pull qwen2.5:14b
        ollama pull nomic-embed-text
        Write-Host "[+] Models ready" -ForegroundColor Green
    } catch {
        Write-Host "[-] Model pull failed. Run manually: ollama pull qwen2.5:14b" -ForegroundColor Yellow
    }
}

# ============================================
# 4. Install Vision dependencies
# ============================================

Write-Host ""
Write-Host "[4/5] Installing Vision dependencies..." -ForegroundColor Cyan

Push-Location $ProjectDir

# Install pip packages
Write-Host "[*] Installing pip packages..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet 2>$null
python -m pip install -e "." --quiet 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[+] Vision dependencies installed" -ForegroundColor Green
} else {
    Write-Host "[-] pip install failed, trying individual packages..." -ForegroundColor Yellow
    python -m pip install requests httpx rich pyyaml aiosqlite fastapi uvicorn psutil croniter
}

# Optional: voice support
Write-Host "[*] Installing voice support (optional)..." -ForegroundColor Yellow
python -m pip install faster-whisper sounddevice numpy edge-tts --quiet 2>$null

# Optional: gesture support
Write-Host "[*] Installing gesture support (optional)..." -ForegroundColor Yellow
python -m pip install mediapipe opencv-python pyautogui pynput Pillow --quiet 2>$null

Pop-Location

# ============================================
# 5. Create config
# ============================================

Write-Host ""
Write-Host "[5/5] Creating configuration..." -ForegroundColor Cyan

$configPath = Join-Path $ProjectDir "config.json"
if (-not (Test-Path $configPath)) {
    $config = @{
        llm = @{
            provider = "ollama"
            model = "qwen2.5:14b"
            base_url = "http://127.0.0.1:11434"
        }
        voice = @{ enabled = $false }
        gestures = @{ enabled = $false }
        gateway = @{
            host = "0.0.0.0"
            port = 8080
        }
    } | ConvertTo-Json -Depth 5
    Set-Content -Path $configPath -Value $config -Encoding UTF8
    Write-Host "[+] config.json created" -ForegroundColor Green
} else {
    Write-Host "[=] config.json already exists" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Vision installed successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
