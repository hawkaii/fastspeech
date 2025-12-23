#!/bin/bash
# Project structure verification and setup script

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          Indic TTS API - Project Verification                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1 (MISSING)"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        return 0
    else
        echo -e "${RED}✗${NC} $1/ (MISSING)"
        return 1
    fi
}

echo "Checking project structure..."
echo ""

# Core files
echo "Core Files:"
check_file "Dockerfile"
check_file "environment.yml"
check_file "README.md"
check_file ".gitignore"
check_file ".dockerignore"
check_file ".env.example"
echo ""

# API
echo "API Components:"
check_dir "api"
check_file "api/__init__.py"
check_file "api/app.py"
echo ""

# Source
echo "Source Code:"
check_dir "src"
check_file "src/__init__.py"
check_file "src/config.py"
check_file "src/model_store.py"
check_file "src/tts_engine.py"
check_file "src/text_processor.py"
check_file "src/preprocessing/__init__.py"
echo ""

# Scripts
echo "Scripts:"
check_dir "scripts"
check_file "scripts/start.sh"
check_file "scripts/deploy.sh"
check_file "scripts/test_api.sh"
check_file "scripts/tts_client.py"
check_file "scripts/upload_models_to_gcs.sh"
check_file "scripts/gce-startup.sh"
echo ""

# Documentation
echo "Documentation:"
check_dir "docs"
check_file "docs/QUICKSTART.md"
check_file "docs/GCP_DEPLOYMENT.md"
check_file "docs/kubernetes-deployment.yaml"
check_file "PROJECT_SUMMARY.md"
echo ""

# Check executability of scripts
echo "Script Permissions:"
for script in scripts/*.sh scripts/tts_client.py; do
    if [ -x "$script" ]; then
        echo -e "${GREEN}✓${NC} $script (executable)"
    else
        echo -e "${YELLOW}⚠${NC} $script (not executable - run: chmod +x $script)"
    fi
done
echo ""

# Check for required tools
echo "System Dependencies:"
for tool in docker git curl; do
    if command -v $tool &> /dev/null; then
        echo -e "${GREEN}✓${NC} $tool installed"
    else
        echo -e "${RED}✗${NC} $tool not found"
    fi
done
echo ""

# Optional tools
echo "Optional Tools:"
for tool in gcloud kubectl gsutil; do
    if command -v $tool &> /dev/null; then
        echo -e "${GREEN}✓${NC} $tool installed"
    else
        echo -e "${YELLOW}⚠${NC} $tool not found (needed for GCP deployment)"
    fi
done
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                     Setup Instructions                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "1. Copy .env.example to .env and configure:"
echo "   cp .env.example .env"
echo "   # Edit .env with your settings"
echo ""
echo "2. For local testing:"
echo "   docker build -t indic-tts:latest ."
echo "   docker run -p 8080:8080 -e DEVICE=cpu indic-tts:latest"
echo ""
echo "3. For GCP deployment:"
echo "   export PROJECT_ID=your-gcp-project"
echo "   export GCS_BUCKET=gs://your-bucket"
echo "   ./scripts/deploy.sh all"
echo ""
echo "4. Read the documentation:"
echo "   - README.md - Full documentation"
echo "   - docs/QUICKSTART.md - Quick start guide"
echo "   - docs/GCP_DEPLOYMENT.md - GCP deployment"
echo "   - PROJECT_SUMMARY.md - Project overview"
echo ""
echo "For more information, visit:"
echo "https://github.com/smtiitm/Fastspeech2_HS"
echo ""
