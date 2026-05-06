from __future__ import annotations

import csv
import io
import json
from collections import deque
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.logging_config import LOG_FILES

settings = get_settings()


def resolve_log_file(log_type: str) -> Path:
    filename = LOG_FILES.get(log_type)
    if not filename:
        raise ValueError('Geçersiz log tipi')
    return Path(settings.log_root) / filename


def tail_json_logs(path: Path, limit: int = 1000) -> list[dict]:
    if not path.exists():
        return []
    q: deque[str] = deque(maxlen=limit)
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            q.append(line.strip())

    data = []
    for line in q:
        if not line:
            continue
        try:
            data.append(json.loads(line))
        except Exception:
            data.append({'raw': line})
    return data


def tail_all_json_logs(limit: int = 1000) -> list[dict]:
    merged: list[dict] = []
    per_file_limit = max(100, min(limit, 500))
    for category in LOG_FILES:
        path = resolve_log_file(category)
        rows = tail_json_logs(path, limit=per_file_limit)
        for row in rows:
            if 'module' not in row:
                row['module'] = category
            row['_log_type'] = category
            merged.append(row)

    def sort_key(item: dict) -> datetime:
        raw = str(item.get('timestamp') or '')
        if not raw:
            return datetime.min
        try:
            if raw.endswith('Z'):
                raw = raw[:-1] + '+00:00'
            return datetime.fromisoformat(raw)
        except Exception:
            return datetime.min

    merged.sort(key=sort_key, reverse=True)
    return merged[:limit]


def filter_logs(entries: list[dict], filters: dict) -> list[dict]:
    result = []
    text = (filters.get('search') or '').lower()
    level = filters.get('level')
    username = filters.get('username')
    ip = filters.get('ip')

    for item in entries:
        if level and item.get('level') != level:
            continue
        if username and str(item.get('username') or '') != username:
            continue
        if ip and str(item.get('ip_address') or '') != ip:
            continue
        if text and text not in json.dumps(item, ensure_ascii=False).lower():
            continue
        result.append(item)
    return result


def logs_to_csv(entries: list[dict]) -> bytes:
    output = io.StringIO()
    fields = [
        'timestamp',
        'level',
        'module',
        'action',
        'user_id',
        'username',
        'user_role',
        'ip_address',
        'request_id',
        'message',
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for e in entries:
        writer.writerow({k: e.get(k, '') for k in fields})
    return ('\ufeff' + output.getvalue()).encode('utf-8')
