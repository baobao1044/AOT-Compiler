#!/usr/bin/env bash
set -euo pipefail

git tag -a v0.1.0 -m "AOTC v0.1.0"
git tag --list | grep -E '^v0\.1\.0$'
