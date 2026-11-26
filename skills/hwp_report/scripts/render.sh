#!/usr/bin/env bash
# 미리보기(예전 진입점) — hr.py render 와 같다:  bash render.sh report.hwpx [outdir]
exec bash "$(cd "$(dirname "$0")" && pwd)/hwp_report.sh" render "$@"
