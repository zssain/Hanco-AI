# =============================================================================
# Secret Scanner - Prevents accidental commit of secrets (PowerShell version)
# =============================================================================
# This script scans staged files for potential secrets and API keys
# Run manually or integrate with pre-commit hooks
# =============================================================================

Write-Host "🔍 Scanning staged files for secrets..." -ForegroundColor Cyan

# Get list of staged files
$stagedFiles = git diff --cached --name-only --diff-filter=ACM

if (-not $stagedFiles) {
    Write-Host "✅ No staged files to scan" -ForegroundColor Green
    exit 0
}

# Patterns to detect secrets
$patterns = @(
    "AIza[0-9A-Za-z_-]{35}",                          # Google API keys
    "-----BEGIN (RSA |DSA |EC )?PRIVATE KEY-----",    # Private keys
    "firebase-adminsdk",                              # Firebase admin SDK
    "serviceAccountKey",                              # Service account keys
    "AKIA[0-9A-Z]{16}",                              # AWS Access Key ID
    "sk-[a-zA-Z0-9]{48}",                            # OpenAI API keys
    "ghp_[0-9a-zA-Z]{36}",                           # GitHub Personal Access Token
    "glpat-[0-9a-zA-Z_-]{20}",                       # GitLab PAT
    "xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9a-zA-Z]{24}", # Slack tokens
    "mongodb(\+srv)?://[^:]+:[^@]+@",                # MongoDB connection strings
    "postgres://[^:]+:[^@]+@",                       # PostgreSQL with passwords
    "mysql://[^:]+:[^@]+@",                          # MySQL with passwords
    "password\s*=\s*['\`"][^'\`"]{8,}",               # Hardcoded passwords
    "token\s*=\s*['\`"][^'\`"]{20,}",                 # Hardcoded tokens
    "api[_-]?key\s*=\s*['\`"][^'\`"]{20,}",           # API keys
    "client[_-]?secret\s*=\s*['\`"][^'\`"]{20,}"      # Client secrets
)

$foundSecrets = $false
$findings = @()

# Scan each staged file
foreach ($file in $stagedFiles) {
    # Skip if file doesn't exist (deleted)
    if (-not (Test-Path $file)) { continue }
    
    # Skip binary files and images
    $extension = [System.IO.Path]::GetExtension($file)
    if ($extension -in @('.exe', '.dll', '.bin', '.jpg', '.png', '.gif', '.pdf', '.zip')) {
        continue
    }
    
    # Skip example files
    if ($file -like "*.env.example" -or $file -like "*.env.template") {
        continue
    }
    
    # Read file content
    try {
        $content = Get-Content $file -Raw -ErrorAction Stop
        
        # Check each pattern
        foreach ($pattern in $patterns) {
            $matches = [regex]::Matches($content, $pattern)
            
            if ($matches.Count -gt 0) {
                $foundSecrets = $true
                $findings += "⚠️  File: $file"
                $findings += "   Pattern matched: $pattern"
                $findings += "   Occurrences: $($matches.Count)"
                $findings += ""
            }
        }
    }
    catch {
        # Skip files that can't be read as text
        continue
    }
}

# Check for specific filenames that shouldn't be committed
$dangerousFiles = @(
    "*vercel.json",
    "*firebase-key.json",
    "*-firebase-adminsdk-*.json",
    "*serviceAccountKey.json",
    "*.env",
    "*.env.production",
    "*.env.local"
)

foreach ($dangerousPattern in $dangerousFiles) {
    foreach ($file in $stagedFiles) {
        if ($file -like $dangerousPattern) {
            $foundSecrets = $true
            $findings += "🚨 Dangerous file staged: $file"
            $findings += ""
        }
    }
}

# Report results
if ($foundSecrets) {
    Write-Host ""
    Write-Host "❌ COMMIT BLOCKED: Potential secrets detected!" -ForegroundColor Red
    Write-Host ""
    
    foreach ($finding in $findings) {
        Write-Host $finding -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "If these are false positives:" -ForegroundColor Yellow
    Write-Host "  1. Review the findings carefully" -ForegroundColor White
    Write-Host "  2. If safe, use: git commit --no-verify" -ForegroundColor White
    Write-Host ""
    Write-Host "To fix:" -ForegroundColor Yellow
    Write-Host "  1. Remove secrets from code" -ForegroundColor White
    Write-Host "  2. Use environment variables instead" -ForegroundColor White
    Write-Host "  3. Add sensitive files to .gitignore" -ForegroundColor White
    Write-Host "  4. If keys were committed before, rotate them immediately" -ForegroundColor White
    Write-Host ""
    
    exit 1
}
else {
    Write-Host "✅ No secrets detected - commit allowed" -ForegroundColor Green
    exit 0
}
