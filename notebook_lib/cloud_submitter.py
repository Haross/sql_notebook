from __future__ import annotations

from typing import Callable, Optional, Dict, Any
from pathlib import Path

def make_cloud_run_submitter(
    *,
    submit_url: str,
    exam_id: str,
    question_id: str,
    api_key: Optional[str] = None,
    timeout_s: int = 20,
) -> Callable[[str, str], Dict[str, Any]]:
    """
    Returns a function (runner_id, sql) -> dict
    that calls your Cloud Run /submit endpoint.

    Success shape:
      {
        "ok": True,
        "attempt": int,
        "final_points": int,
        "raw_points": int,
        "multiplier": float,
        "hint": Optional[str]
      }

    Error shape:
      { "ok": False, "error": str }
    """
    import requests

    def _submit(runner_id: str, sql: str) -> Dict[str, Any]:
        # todo token file not visible from module here and the notebok
        token_path = Path("student_token.txt")
        # token_path = Path(TOKEN_FILE) if TOKEN_FILE else Path("student_token.txt")
        if not token_path.exists():
            return {"ok": False, "error": "⚠️ No token found. Please enter and save your student token first."}

        student_token = token_path.read_text(encoding="utf-8").strip()    

        if len(student_token) < 6:
            return {"ok": False, "error": "⚠️ Invalid or incomplete token. Please verify and save again. Contact the professor if needed."}

        payload: Dict[str, Any] = {
            "student_token": student_token,
            "exam_id": exam_id,
            "question_id": question_id,
            "sql": sql,
        }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        try:
            r = requests.post(submit_url, json=payload, headers=headers, timeout=timeout_s)
        except Exception as e:
            return {"ok": False, "error": f"Network error: {e}"}

        # Handle HTTP errors
        if r.status_code >= 400:
            try:
                data = r.json()
            except Exception:
                return {"ok": False, "error": f"{r.status_code}: {r.text}"}

            detail = data.get("detail")


            #  Special handling for invalid token
            if isinstance(detail, dict):
                code = detail.get("code")
                msg = detail.get("message") or "Submission failed."

                if code == "INVALID_TOKEN":
                    return {"ok": False, "error": "Token not valid for this exam. Please contact the professor."}
                if code == "EXAM_CLOSED":
                    return {"ok": False, "error": "⛔ The exam is currently closed."}

                return {"ok": False, "error": msg}


            if isinstance(detail, list):
                # If token failed validation, show a friendlier message
                for d in detail:
                    loc = d.get("loc", [])
                    if len(loc) >= 2 and loc[-1] == "student_token":
                        return {"ok": False, "error": "⚠️ Token missing/invalid format. Please re-enter and save your token."}

                # otherwise show generic validation messages
                msg = "; ".join(
                    [f"{'.'.join(map(str, d.get('loc', [])))}: {d.get('msg')}" for d in detail]
                )
                return {"ok": False, "error": f"{r.status_code}: {msg}"}

            return {"ok": False, "error": f"{r.status_code}: {detail or data}"}

        # Success
        data = r.json()
        revealed = data.get("revealed_failure") or {}
        hint = revealed.get("description")  # <-- your green/amber rule can use this

        return {
            "ok": True,
            "attempt": data.get("attempt"),
            "final_points": data.get("final_points"),
            "raw_points": data.get("raw_points"),
            "multiplier": data.get("multiplier"),
            "hint": hint,
        }

    return _submit