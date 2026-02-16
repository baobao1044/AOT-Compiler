#!/usr/bin/env bash
set -euo pipefail

git tag -a v0.2.0 -m "AOTC v0.2.0"
git tag --list | grep -E '^v0\.2\.0$'
