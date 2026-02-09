#!/bin/bash
# =============================================================================
# Install Pre-Commit Hook for Secret Scanning
# =============================================================================
# This script installs the secret scanner as a git pre-commit hook
# Run this once after cloning the repository
# =============================================================================

set -e

echo "🔧 Installing pre-commit hook for secret scanning..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository root"
    echo "Please run this script from the repository root directory"
    exit 1
fi

# Check if hook already exists
if [ -f ".git/hooks/pre-commit" ]; then
    echo "⚠️  Warning: pre-commit hook already exists"
    echo "Do you want to overwrite it? (y/n)"
    read -r response
    if [ "$response" != "y" ]; then
        echo "Installation cancelled"
        exit 0
    fi
    echo "Backing up existing hook to .git/hooks/pre-commit.backup"
    cp .git/hooks/pre-commit .git/hooks/pre-commit.backup
fi

# Create symlink to our secret scanner
echo "Creating symlink: .git/hooks/pre-commit -> ../../scripts/check_secrets.sh"
ln -sf ../../scripts/check_secrets.sh .git/hooks/pre-commit

# Make it executable
chmod +x .git/hooks/pre-commit
chmod +x scripts/check_secrets.sh

echo ""
echo "✅ Pre-commit hook installed successfully!"
echo ""
echo "📋 What this does:"
echo "   - Scans staged files for secrets before each commit"
echo "   - Blocks commits if secrets are detected"
echo "   - Helps prevent accidental credential leaks"
echo ""
echo "🧪 Test it:"
echo "   bash scripts/check_secrets.sh"
echo ""
echo "⚠️  To bypass (only if you're sure):"
echo "   git commit --no-verify"
echo ""
echo "✨ You're all set! The hook will run automatically on every commit."
