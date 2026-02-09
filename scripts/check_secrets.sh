#!/bin/bash
# =============================================================================
# Secret Scanner - Prevents accidental commit of secrets
# =============================================================================
# This script scans staged files for potential secrets and API keys
# Add to pre-commit hook with: ln -s ../../scripts/check_secrets.sh .git/hooks/pre-commit
# =============================================================================

set -e

# ANSI color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "🔍 Scanning staged files for secrets..."

# Get list of staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED_FILES" ]; then
    echo "${GREEN}✅ No staged files to scan${NC}"
    exit 0
fi

# Patterns to detect secrets
PATTERNS=(
    "AIza[0-9A-Za-z_-]{35}"                          # Google API keys
    "-----BEGIN (RSA |DSA |EC )?PRIVATE KEY-----"    # Private keys
    "firebase-adminsdk"                              # Firebase admin SDK
    "serviceAccountKey"                              # Service account keys
    "AKIA[0-9A-Z]{16}"                              # AWS Access Key ID
    "[0-9a-zA-Z/+]{40}"                             # AWS Secret Access Key patterns
    "sk-[a-zA-Z0-9]{48}"                            # OpenAI API keys
    "ghp_[0-9a-zA-Z]{36}"                           # GitHub Personal Access Token
    "glpat-[0-9a-zA-Z_-]{20}"                       # GitLab PAT
    "xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9a-zA-Z]{24}" # Slack tokens
    "mongodb(\+srv)?://[^:]+:[^@]+@"                # MongoDB connection strings with passwords
    "postgres://[^:]+:[^@]+@"                       # PostgreSQL with passwords
    "mysql://[^:]+:[^@]+@"                          # MySQL with passwords
    "password\s*=\s*['\"][^'\"]{8,}"                # Hardcoded passwords
    "token\s*=\s*['\"][^'\"]{20,}"                  # Hardcoded tokens
    "api[_-]?key\s*=\s*['\"][^'\"]{20,}"           # API keys
    "client[_-]?secret\s*=\s*['\"][^'\"]{20,}"     # Client secrets
)

FOUND_SECRETS=0
FINDINGS=""

# Scan each staged file
for FILE in $STAGED_FILES; do
    # Skip if file doesn't exist (deleted)
    [ ! -f "$FILE" ] && continue
    
    # Skip binary files
    file "$FILE" | grep -q "text" || continue
    
    # Skip files that should contain examples
    if [[ "$FILE" == *".env.example"* ]] || [[ "$FILE" == *".env.template"* ]]; then
        continue
    fi
    
    # Check each pattern
    for PATTERN in "${PATTERNS[@]}"; do
        MATCHES=$(grep -nE "$PATTERN" "$FILE" 2>/dev/null || true)
        
        if [ ! -z "$MATCHES" ]; then
            FOUND_SECRETS=1
            FINDINGS="${FINDINGS}\n${YELLOW}File: ${FILE}${NC}\n${MATCHES}\n"
        fi
    done
done

# Check for specific filenames that shouldn't be committed
DANGEROUS_FILES=(
    "vercel.json"
    "firebase-key.json"
    "*-firebase-adminsdk-*.json"
    "serviceAccountKey.json"
    ".env"
    ".env.production"
    ".env.local"
)

for PATTERN in "${DANGEROUS_FILES[@]}"; do
    for FILE in $STAGED_FILES; do
        if [[ "$FILE" == $PATTERN ]]; then
            FOUND_SECRETS=1
            FINDINGS="${FINDINGS}\n${RED}⚠️  Dangerous file staged: ${FILE}${NC}\n"
        fi
    done
done

# Report results
if [ $FOUND_SECRETS -eq 1 ]; then
    echo ""
    echo "${RED}❌ COMMIT BLOCKED: Potential secrets detected!${NC}"
    echo ""
    echo -e "$FINDINGS"
    echo ""
    echo "${YELLOW}If these are false positives:${NC}"
    echo "  1. Review the findings carefully"
    echo "  2. If safe, use: git commit --no-verify"
    echo ""
    echo "${YELLOW}To fix:${NC}"
    echo "  1. Remove secrets from code"
    echo "  2. Use environment variables instead"
    echo "  3. Add sensitive files to .gitignore"
    echo "  4. If keys were committed before, rotate them immediately"
    echo ""
    exit 1
else
    echo "${GREEN}✅ No secrets detected - commit allowed${NC}"
    exit 0
fi
