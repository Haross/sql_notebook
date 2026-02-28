# notebook_lib/sql_runner_store.py
from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import html as _html

def to_int(x):
    try:
        return int(x) if x not in (None, "", "None") else None
    except Exception:
        return None

def append_history(log_all_file: Path, runner_id: str, sql: str) -> None:
    is_new = not log_all_file.exists()
    with log_all_file.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["ts", "runner_id", "sql"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), runner_id, sql])

def load_latest_map(log_latest_file: Path) -> Dict[str, str]:
    if not log_latest_file.exists():
        return {}
    latest = {}
    with log_latest_file.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            latest[row["runner_id"]] = row["sql"]
    return latest

def save_latest_map(log_latest_file: Path, latest: Dict[str, str]) -> None:
    with log_latest_file.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["runner_id", "sql"])
        for rid, sql in latest.items():
            w.writerow([rid, sql])

def load_scores(score_file: Path) -> Dict[str, Dict[str, Any]]:
    if not score_file.exists():
        return {}
    scores = {}
    with score_file.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            scores[row["runner_id"]] = {
                "current_points": to_int(row.get("current_points")),
                "max_points": to_int(row.get("max_points")),
                "attempt": to_int(row.get("attempt")),
            }
    return scores

def save_scores(score_file: Path, scores: Dict[str, Dict[str, Any]]) -> None:
    with score_file.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["runner_id", "current_points", "max_points", "attempt"])
        for rid, rec in scores.items():
            w.writerow([rid, rec.get("current_points"), rec.get("max_points"), rec.get("attempt")])

