#!/usr/bin/env python3
"""Skill Nexus automation audit: offline facts only; never calls external systems.
Input is a sanitized JSON snapshot of Automations.peek calls. Outputs a compact
machine-readable triage, not an assertion that a skill executed.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone


def parse_dt(v):
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        x = datetime.fromisoformat(v.replace('Z', '+00:00'))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def digest(a, now):
    rd = a.get('run_details') or {}
    run = rd.get('last_run') or {}
    result = rd.get('latest_result') or {}
    status = run.get('recorded_status') or 'unknown'
    issues = []
    if not a.get('is_enabled'):
        return None
    # A result from a different run cannot describe the current run.
    if run.get('id') and result.get('run_id') and run['id'] != result['run_id']:
        issues.append({'kind': 'stale_result', 'certainty': 'observed'})
        result = {}
    text = str(result.get('content_text') or '')
    if not run:
        issues.append({'kind': 'no_last_run', 'certainty': 'observed'})
    if status == 'failed' or result.get('is_failure_message'):
        issues.append({'kind': 'failed', 'certainty': 'observed'})
    if result.get('requires_user_action'):
        issues.append({'kind': 'requires_user_action', 'certainty': 'observed'})
    if status == 'completed' and not result:
        issues.append({'kind': 'completed_without_result', 'certainty': 'observed'})
    if status == 'no_update':
        issues.append({'kind': 'no_update', 'certainty': 'observed'})
    if result.get('content_truncated'):
        issues.append({'kind': 'truncated_result', 'certainty': 'observed'})
    if status == 'in_progress':
        t = parse_dt(run.get('started_at'))
        if t and (now - t).total_seconds() > 7200:
            issues.append({'kind': 'long_running', 'certainty': 'suspected'})
    # Results are prose, not execution traces: only suspect zero-value progress.
    needles = ('новых изменений не внесено', '0 п.п.', 'ничего не изменено', 'no changes made', 'no commits')
    if any(x in text.lower() for x in needles):
        issues.append({'kind': 'possibly_idle_run', 'certainty': 'suspected'})
    # Skill evidence must be checked against actual artifacts/commands.
    return {
        'task_id': a.get('id'), 'title': a.get('title'),
        'last_run_id': run.get('id'), 'status': status,
        'has_result': bool(result), 'issues': issues,
        'skill_use': 'unverified', 'code_change': 'unverified',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('snapshot', type=Path)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    raw = json.loads(args.snapshot.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('automations'), list):
        raise SystemExit('Expected object with automations list')
    now = datetime.now(timezone.utc)
    tasks = [x for a in raw['automations'] if isinstance(a, dict) if (x := digest(a, now))]
    issues = sum(len(t['issues']) for t in tasks)
    report = {'active_tasks_checked': len(tasks), 'issues': issues,
              'notes': 'Diagnostics only; no skill usage or code changes verified',
              'tasks': tasks}
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.write_text(encoded, encoding='utf-8')
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
