# notebook_lib/validators.py
from __future__ import annotations

import hashlib
import random
import pandas as pd


def df_fingerprint(
    df: pd.DataFrame,
    *,
    sort_rows: bool = True,
    sort_cols: bool = False,
    normalize_whitespace: bool = True,
    na_token: str = "<NA>",
) -> tuple[str, dict]:
    x = df.copy()

    if sort_cols:
        x = x.reindex(sorted(x.columns), axis=1)

    def norm(v):
        if pd.isna(v):
            return na_token
        s = str(v)
        if normalize_whitespace:
            s = " ".join(s.split())
        return s

    x = x.map(norm)

    if sort_rows and len(x.columns) > 0 and len(x) > 0:
        x = x.sort_values(by=list(x.columns), kind="mergesort").reset_index(drop=True)
    else:
        x = x.reset_index(drop=True)

    payload = x.to_csv(index=False)
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    meta = {"rows": int(len(df)), "cols": list(df.columns)}
    return h, meta


def make_df_validator_nospoilers(
    expected_hash: str,
    *,
    required_cols=None,
    exact_cols: bool = False,
    expected_rows: int | None = None,
    sort_rows: bool = True,
    sort_cols: bool = False,
    hide_missing_cols: bool = True,
    hide_row_count: bool = False,
):
    required_cols = required_cols or []

    def validator(sql: str, df: pd.DataFrame, conn ):
        problems = []
        structural_issue = False

        if required_cols:
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                structural_issue = True
                if hide_missing_cols:
                    problems.append("Wrong number of columns! Make corrections and try again.")
                else:
                    problems.append(f"Missing column(s): {', '.join(missing)}")
                return False, problems

        if exact_cols and required_cols:
            if set(df.columns) != set(required_cols):
                structural_issue = True
                return False, ["Wrong number of columns! Make corrections and try again."]

        if structural_issue:
            return False, problems

        if expected_rows is not None and len(df) != expected_rows:
            if hide_row_count:
                return False, ["Wrong number of rows! Make corrections and try again."]
            return False, ["Wrong number of rows! Make corrections and try again."]

        got_hash, _ = df_fingerprint(df, sort_rows=sort_rows, sort_cols=sort_cols)
        if got_hash != expected_hash:
            return False, ["The result is not correct yet. Make corrections and try again."]

        return True, ["Nice — your output matches the expected result ✅"]

    return validator
