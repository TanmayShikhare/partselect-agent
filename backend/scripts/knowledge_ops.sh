#!/usr/bin/env bash
# Thin wrapper: run from repo anywhere — resolves to backend/ and invokes knowledge_ops.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python scripts/knowledge_ops.py "$@"
