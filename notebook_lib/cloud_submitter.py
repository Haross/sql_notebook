# cloud_submitter.py
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
    import requests

    def _err(
        *,
        status_code: int | None,
        code: str | None,
        message: str,
        **extra: Any,
    ) -> Dict[str, Any]:
        # Keep old "error" key for backwards compatibility
        out: Dict[str, Any] = {
            "ok": False,
            "status_code": status_code,
            "error_code": code,
            "error_message": message,
            "error": message,
        }
        out.update(extra)
        return out

    def _submit(runner_id: str, sql: str) -> Dict[str, Any]:
        token_path = Path("student_token.txt")
        if not token_path.exists():
            return _err(
                status_code=None,
                code="NO_TOKEN",
                message="⚠️ No token found. Please enter and save your student token first.",
            )

        student_token = token_path.read_text(encoding="utf-8").strip()
        if len(student_token) < 2:
            return _err(
                status_code=None,
                code="BAD_TOKEN_FORMAT",
                message="⚠️ Invalid or incomplete token. Token must be more than one character. Please verify and save again. Contact the professor if needed.",
            )

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
            return _err(
                status_code=None,
                code="NETWORK_ERROR",
                message=f"Network error: {e}",
            )

        # ---------- HTTP error handling ----------
        if r.status_code >= 400:
            try:
                data = r.json()
            except Exception:
                # Non-JSON error
                return _err(
                    status_code=r.status_code,
                    code="HTTP_ERROR",
                    message=f"{r.status_code}: {r.text}",
                )

            detail = data.get("detail", data)

            # Case A: structured FastAPI detail dict
            if isinstance(detail, dict):
                code = detail.get("code")
                msg = detail.get("message") or "Submission failed."

                # Friendly overrides (optional)
                if code == "INVALID_TOKEN":
                    msg = "🔑 Token not valid for this exam. Please contact the professor."
                elif code == "EXAM_CLOSED":
                    msg = "⛔ The exam is currently closed."
                elif code == "MAX_ATTEMPTS":
                    # If backend includes max_attempts, use it
                    max_attempts = detail.get("max_attempts")
                    if max_attempts is not None:
                        msg = f"No attempts left. Maximum attempts is {max_attempts}."
                    else:
                        msg = "No attempts left for this question."

                # Return structured info + keep msg in error
                extra = {k: v for k, v in detail.items() if k not in ("code", "message")}
                return _err(
                    status_code=r.status_code,
                    code=code,
                    message=msg,
                    **extra,
                )

            # Case B: pydantic validation errors list
            if isinstance(detail, list):
                # If token failed validation, show a friendlier message
                for d in detail:
                    loc = d.get("loc", [])
                    if len(loc) >= 2 and loc[-1] == "student_token":
                        return _err(
                            status_code=r.status_code,
                            code="TOKEN_VALIDATION_ERROR",
                            message="⚠️ Token missing/invalid format. Please re-enter and save your token.",
                            detail=detail,
                        )

                msg = "; ".join(
                    [f"{'.'.join(map(str, d.get('loc', [])))}: {d.get('msg')}" for d in detail]
                )
                return _err(
                    status_code=r.status_code,
                    code="VALIDATION_ERROR",
                    message=msg,
                    detail=detail,
                )

            # Case C: plain string detail
            if isinstance(detail, str):
                # If backend hasn't been updated yet, you can optionally detect max attempts here:
                if "Max attempts" in detail:
                    return _err(
                        status_code=r.status_code,
                        code="MAX_ATTEMPTS",
                        message="🚫 No attempts left for this question.",
                        raw_detail=detail,
                    )
                return _err(
                    status_code=r.status_code,
                    code="HTTP_ERROR",
                    message=detail,
                )

            # Fallback: unknown error shape
            return _err(
                status_code=r.status_code,
                code="HTTP_ERROR",
                message=str(detail),
            )

        # ---------- Success ----------
        data = r.json()
        revealed = data.get("revealed_failure") or {}
        hint = revealed.get("description")

        return {
            "ok": True,
            "attempt": data.get("attempt"),
            "final_points": data.get("final_points"),
            "max_points": data.get("max_points"),
            "raw_points": data.get("raw_points"),
            "multiplier": data.get("multiplier"),
            "hint": hint,
        }

    return _submit