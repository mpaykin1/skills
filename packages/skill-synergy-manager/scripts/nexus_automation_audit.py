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


def digest(a, now, include_paused=False):
    if not a.get('is_enabled') and not include_paused:
        return None
    issues = []

    def mapping(value, field):
        if value is None:
            return {}
        if not isinstance(value, dict):
            issues.append({'kind': 'invalid_' + field, 'certainty': 'observed'})
            return {}
        return value

    rd = mapping(a.get('run_details'), 'run_details')
    run = mapping(rd.get('last_run'), 'last_run')
    result = mapping(rd.get('latest_result'), 'latest_result')
    status = run.get('recorded_status') or 'unknown'
    # A result from a different run cannot describe the current run.
    if result and not (run.get('id') and result.get('run_id')):
        issues.append({'kind': 'unlinked_result', 'certainty': 'observed'})
        result = {}
    elif run.get('id') and result.get('run_id') and run['id'] != result['run_id']:
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
        if t is None:
            issues.append({'kind': 'missing_or_invalid_started_at', 'certainty': 'observed'})
        else:
            age = (now - t).total_seconds()
            # Allow up to five minutes of clock skew.
            if age < -300:
                issues.append({'kind': 'future_started_at', 'certainty': 'observed'})
            elif age > 7200:
                issues.append({'kind': 'long_running', 'certainty': 'suspected'})
    # Results are prose, not execution traces: only suspect zero-value progress.
    needles = ('новых изменений не внесено', '0 п.п.', 'ничего не изменено', 'no changes made', 'no commits')
    if any(x in text.lower() for x in needles):
        issues.append({'kind': 'possibly_idle_run', 'certainty': 'suspected'})
    # Skill evidence must be checked against actual artifacts/commands.
    return {
        'task_id': a.get('id'), 'title': a.get('title'),
        'is_enabled': bool(a.get('is_enabled')),
        'last_run_id': run.get('id'), 'status': status,
        'has_result': bool(result), 'issues': issues,
        'skill_use': 'unverified', 'code_change': 'unverified',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('snapshot', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--include-paused', action='store_true', help='Inspect paused tasks without activating them')
    args = ap.parse_args()
    raw = json.loads(args.snapshot.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('automations'), list):
        raise SystemExit('Expected object with automations list')
    now = datetime.now(timezone.utc)
    invalid_task_entries = sum(not isinstance(a, dict) for a in raw['automations'])
    tasks = [x for a in raw['automations'] if isinstance(a, dict) if (x := digest(a, now, include_paused=args.include_paused))]
    issues = sum(len(t['issues']) for t in tasks) + invalid_task_entries
    report = {'active_tasks_checked': sum(t['is_enabled'] for t in tasks),
              'paused_tasks_checked': sum(not t['is_enabled'] for t in tasks), 'issues': issues,
              'invalid_task_entries': invalid_task_entries,
              'snapshot_issues': ([{'kind': 'invalid_task_entries', 'certainty': 'observed',
                                    'count': invalid_task_entries}] if invalid_task_entries else []),
              'notes': 'Diagnostics only; no skill usage or code changes verified',
              'tasks': tasks}
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.write_text(encoded, encoding='utf-8')
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
