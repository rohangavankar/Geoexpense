#!/bin/bash
# Quick start: install deps and run the full AI pipeline
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "Error: ANTHROPIC_API_KEY is not set."
  echo "Run: export ANTHROPIC_API_KEY=your_key_here"
  exit 1
fi

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "Running AI pipeline (review → test → build → deploy)..."
python pipeline.py
