# =============================================================================
# Install Pre-Commit Hook for Secret Scanning (PowerShell)
# =============================================================================
# This script installs the secret scanner as a git pre-commit hook
# Run this once after cloning the repository
# =============================================================================

Write-Host "🔧 Installing pre-commit hook for secret scanning..." -ForegroundColor Cyan

# Check if we're in a git repository
if (-not (Test-Path ".git")) {
    Write-Host "❌ Error: Not in a git repository root" -ForegroundColor Red
    Write-Host "Please run this script from the repository root directory" -ForegroundColor Yellow
    exit 1
}

# Check if hook already exists
if (Test-Path ".git\hooks\pre-commit") {
    Write-Host "⚠️  Warning: pre-commit hook already exists" -ForegroundColor Yellow
    $response = Read-Host "Do you want to overwrite it? (y/n)"
    if ($response -ne "y") {
        Write-Host "Installation cancelled" -ForegroundColor Yellow
        exit 0
    }
    Write-Host "Backing up existing hook to .git\hooks\pre-commit.backup" -ForegroundColor Cyan
    Copy-Item ".git\hooks\pre-commit" ".git\hooks\pre-commit.backup" -Force
}

# Create the pre-commit hook that calls our PowerShell scanner
$hookContent = @"
#!/bin/sh
# Git pre-commit hook - calls PowerShell secret scanner
powershell.exe -ExecutionPolicy Bypass -File scripts/check_secrets.ps1
"@

# Write the hook
Set-Content -Path ".git\hooks\pre-commit" -Value $hookContent -Encoding ASCII

Write-Host ""
Write-Host "✅ Pre-commit hook installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 What this does:" -ForegroundColor Cyan
Write-Host "   - Scans staged files for secrets before each commit"
Write-Host "   - Blocks commits if secrets are detected"
Write-Host "   - Helps prevent accidental credential leaks"
Write-Host ""
Write-Host "🧪 Test it:" -ForegroundColor Cyan
Write-Host "   powershell -ExecutionPolicy Bypass -File scripts\check_secrets.ps1"
Write-Host ""
Write-Host "⚠️  To bypass (only if you're sure):" -ForegroundColor Yellow
Write-Host "   git commit --no-verify"
Write-Host ""
Write-Host "✨ You're all set! The hook will run automatically on every commit." -ForegroundColor Green
