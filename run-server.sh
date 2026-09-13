#!/usr/bin/env bash
set -euo pipefail
repo_path="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
report_root="${KAMYABI_REPORT_DIR:-$repo_path/reports}"
command -v python3 >/dev/null || { echo "Python 3 is required."; exit 2; }
command -v curl >/dev/null || { echo "curl is required."; exit 2; }
command -v openssl >/dev/null || { echo "openssl is required for IBPS chain verification."; exit 2; }
command -v flock >/dev/null || { echo "flock is required for overlapping-run protection."; exit 2; }
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ is required"'
mkdir -p -- "$report_root"
exec 9>"$report_root/.monitor.lock"
flock -n 9 || { echo "A recruitment check is already running."; exit 2; }
report_dir="$report_root/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p -- "$report_dir"
cd -- "$repo_path"
python3 -m unittest -v test_monitor.py test_submit_jobs.py >"$report_dir/tests.log" 2>&1
check_status=0
python3 monitor.py --output "$report_dir" >"$report_dir/run.log" 2>&1 || check_status=$?
echo "Report saved: $report_dir"
echo "Collection exit code: $check_status"
exit "$check_status"
