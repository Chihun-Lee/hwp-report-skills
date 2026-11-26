#!/usr/bin/env bash
# 1회 설치(예전 진입점) — hr.py setup 과 같다:  bash setup.sh [--figures]
exec bash "$(cd "$(dirname "$0")" && pwd)/hwp_report.sh" setup "$@"
