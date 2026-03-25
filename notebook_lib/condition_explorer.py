# Condition Explorer
# A notebook-friendly widget for practicing boolean conditions with AND / OR / parentheses

from __future__ import annotations

import re
import html as _html
import ipywidgets as widgets
from IPython.display import display, HTML

import pandas as pd


from pathlib import Path
import csv
from datetime import datetime

import markdown

def normalize_condition_for_dropdown(condition: str) -> str:
    return " ".join((condition or "").split())


def append_condition_history(log_file: Path, explorer_id: str, condition: str) -> None:
    is_new = not log_file.exists()

    # consecutive dedupe
    last_explorer_id = None
    last_condition = None

    if log_file.exists():
        with log_file.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            if rows:
                last_row = rows[-1]
                last_explorer_id = last_row.get("explorer_id")
                last_condition = last_row.get("condition")

    if last_explorer_id == explorer_id and last_condition == condition:
        return

    with log_file.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["ts", "explorer_id", "condition"])
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            explorer_id,
            condition,
        ])

def load_recent_conditions(
    log_file: Path,
    explorer_id: str,
    limit: int = 10,
) -> list[tuple[str, str]]:
    """
    Returns dropdown options as (label, original_condition).
    Labels are normalized for compact display, originals are preserved.
    Newest first, deduped by normalized label.
    """
    if not log_file.exists():
        return []

    rows = []
    with log_file.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("explorer_id") == explorer_id:
                condition = row.get("condition", "")
                rows.append(condition)

    rows = list(reversed(rows))  # newest first

    seen = set()
    options = []
    for condition in rows:
        label = normalize_condition_for_dropdown(condition)
        if not label:
            continue
        if label in seen:
            continue
        seen.add(label)
        options.append((label, condition))
        if len(options) >= limit:
            break

    return options


def load_latest_condition(log_file: Path, explorer_id: str) -> str | None:
    if not log_file.exists():
        return None

    latest = None
    with log_file.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("explorer_id") == explorer_id:
                latest = row.get("condition")

    return latest
# =========================================================
# CSS
# =========================================================

CONDITION_EXPLORER_CSS = r"""
.condition-explorer{
  --ce-surface:   #ffffff;
  --ce-surface2:  #f6f8fa;
  --ce-border:    #d0d7de;
  --ce-border2:   #eaeef2;
  --ce-text:      #24292f;
  --ce-muted:     #57606a;
  --ce-accent:    #1a73e8;
  --ce-true-bg:   rgba(46,125,50,0.14);
  --ce-true-bd:   #2e7d32;
  --ce-false-bg:  rgba(176,0,32,0.14);
  --ce-false-bd:  #b00020;
  --ce-shadow:    0 2px 6px rgba(0,0,0,0.05);

  width: 100%;
  max-width: 100%;
  box-sizing: border-box !important;
  color: var(--ce-text) !important;
}
.condition-explorer,
.condition-explorer *{
  box-sizing: border-box !important;
}

/* keep everything width-safe */
.condition-explorer .widget-box,
.condition-explorer .widget-vbox,
.condition-explorer .widget-hbox{
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}


.condition-explorer .widget-textarea textarea{
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
  box-sizing: border-box !important;
}


.condition-explorer .ce-input-box,
.condition-explorer .ce-card,
.condition-explorer .ce-error{
  width: 100% !important;
  max-width: 100% !important;
  overflow-x: hidden !important;
}

html[theme="dark"] .condition-explorer{
  --ce-surface:   #111418;
  --ce-surface2:  #161b22;
  --ce-border:    #2b313b;
  --ce-border2:   #222834;
  --ce-text:      #e6edf3;
  --ce-muted:     #9aa7b4;
  --ce-accent:    #8ab4f8;
  --ce-true-bg:   rgba(46,125,50,0.20);
  --ce-true-bd:   #81c995;
  --ce-false-bg:  rgba(176,0,32,0.22);
  --ce-false-bd:  #f28b82;
  --ce-shadow:    0 2px 8px rgba(0,0,0,0.6);
}


/* ---------- unified top input card ---------- */

.condition-explorer .ce-input-box{
  padding: 16px;
  border-left: 6px solid var(--ce-accent);
  background: var(--ce-surface2);
  border-radius: 10px;
  box-shadow: var(--ce-shadow);
  color: var(--ce-text);
  margin-bottom: 14px;
  width: 100%;
  box-sizing: border-box;
}

.condition-explorer .ce-title{
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 6px;
}

.condition-explorer .ce-subtitle{
  font-size: 14px;
  color: var(--ce-muted);
  margin-bottom: 14px;
  line-height: 1.5;
}

.condition-explorer .ce-field-block{
  margin-top: 10px;
  margin-bottom: 6px;
}

.condition-explorer .ce-label{
  font-size: 14px;
  font-weight: 600;
  color: var(--ce-text);
}

.condition-explorer .ce-help{
  font-size: 12px;
  color: var(--ce-muted);
  margin-top: 4px;
  line-height: 1.4;
}

/* ---------- inputs ---------- */

.condition-explorer .widget-textarea{
  width: 100% !important;
  max-width: 100% !important;
  height: auto !important;
  min-height: unset !important;
  overflow: visible !important;
  padding-right: 2px !important;
}

.condition-explorer .widget-textarea > div{
  height: auto !important;
  min-height: unset !important;
  overflow: visible !important;
}

.condition-explorer .widget-textarea textarea{
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
  box-sizing: border-box !important;

  border: 1px solid var(--ce-border) !important;
  border-radius: 10px !important;
  background: var(--ce-surface) !important;
  color: var(--ce-text) !important;
  padding: 12px !important;
  font-size: 14px !important;
  line-height: 1.5 !important;
  box-shadow: none !important;

  overflow: auto !important;
  resize: vertical !important;
}

.condition-explorer .ce-condition-textarea textarea{
  min-height: 90px !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}

.condition-explorer .ce-values-textarea textarea{
  min-height: 110px !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}

.condition-explorer .widget-textarea textarea:focus{
  border-color: var(--ce-accent) !important;
  box-shadow: 0 0 0 3px rgba(26,115,232,0.15) !important;
  outline: none !important;
}

html[theme="dark"] .condition-explorer .widget-textarea textarea:focus{
  box-shadow: 0 0 0 3px rgba(138,180,248,0.20) !important;
}

.condition-explorer .widget-textarea textarea::placeholder{
  color: var(--ce-muted) !important;
  opacity: 1 !important;
}

/* ---------- button row ---------- */

.condition-explorer .ce-actions{
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}

.condition-explorer .ce-run.widget-button{
  min-width: 150px !important;
  height: 42px !important;
  padding: 0 16px !important;
  background: var(--ce-accent) !important;
  color: #ffffff !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  border: none !important;
  box-shadow: none !important;
}

.condition-explorer .ce-run.widget-button:hover{
  filter: brightness(0.96);
}

.condition-explorer .ce-run.widget-button:disabled{
  opacity: 0.7 !important;
}

/* ---------- cards ---------- */

.condition-explorer .ce-card{
  border: 1px solid var(--ce-border);
  border-radius: 12px;
  background: var(--ce-surface);
  overflow: hidden;
  margin: 10px 0;
}

.condition-explorer .ce-header{
  background: var(--ce-surface2);
  padding: 10px 14px;
  font-weight: 600;
  border-bottom: 1px solid var(--ce-border);
  color: var(--ce-text);
}

.condition-explorer .ce-body{
  padding: 12px 14px;
  color: var(--ce-text);
}

.condition-explorer .ce-code{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  background: var(--ce-surface2);
  border: 1px solid var(--ce-border2);
  padding: 4px 8px;
  border-radius: 999px;
  color: var(--ce-text);
}

.condition-explorer .ce-inputs{
  display: grid;
  gap: 12px;
}

.condition-explorer .ce-input-row{
  font-size: 14px;
  color: var(--ce-text);
}

.condition-explorer .ce-steps{
  display: grid;
  gap: 10px;
}

.condition-explorer .ce-step{
  border: 1px solid var(--ce-border2);
  border-radius: 10px;
  padding: 10px 12px;
  background: var(--ce-surface);
}

.condition-explorer .ce-step-inner{
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.condition-explorer .ce-num{
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: var(--ce-surface2);
  border: 1px solid var(--ce-border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--ce-text);
}

.condition-explorer .ce-step-text{
  flex: 1 1 auto;
  line-height: 1.55;
  padding-top: 4px;
  color: var(--ce-text);
}

.condition-explorer .ce-bool{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 600;
  border: 1px solid transparent;
  vertical-align: middle;
}

.condition-explorer .ce-bool.true{
  background: var(--ce-true-bg);
  border-color: var(--ce-true-bd);
  color: var(--ce-true-bd);
}

.condition-explorer .ce-bool.false{
  background: var(--ce-false-bg);
  border-color: var(--ce-false-bd);
  color: var(--ce-false-bd);
}

.condition-explorer .ce-final{
  background: var(--ce-surface2);
  padding: 12px 14px;
  font-weight: 600;
  border-top: 1px solid var(--ce-border);
  color: var(--ce-text);
}

.condition-explorer .ce-error{
  padding: 14px 16px;
  border-left: 6px solid #c62828;
  background: #fdecea;
  border-radius: 10px;
  color: #202124;
  box-shadow: var(--ce-shadow);
}

html[theme="dark"] .condition-explorer .ce-error{
  background: #3a1f1f;
  color: #e8eaed;
  border-left-color: #f28b82;
}

/* ---------- table preview ---------- */

.condition-explorer .ce-table-wrap{
  overflow-x: auto;
  width: 100%;
}

.condition-explorer table.ce-table{
  width: auto;
  min-width: 100%;
  border-collapse: collapse;
  background: var(--ce-surface);
  color: var(--ce-text);
  font-size: 14px;
}

.condition-explorer table.ce-table th{
  background: var(--ce-surface2);
  color: var(--ce-text);
  border: 1px solid var(--ce-border);
  padding: 8px 10px;
  text-align: left;
  white-space: nowrap;
}

.condition-explorer table.ce-table td{
  border: 1px solid var(--ce-border2);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}

.condition-explorer table.ce-table tr.ce-row-match{
  background: rgba(46,125,50,0.06);
}

.condition-explorer table.ce-table tr.ce-row-no-match{
  background: transparent;
}

html[theme="dark"] .condition-explorer table.ce-table tr.ce-row-match{
  background: rgba(129,201,149,0.10);
}

.condition-explorer .ce-small{
  font-size: 12px;
  color: var(--ce-muted);
  margin-top: 8px;
}

.condition-explorer .ce-section-gap{
  margin-top: 14px;
}

.condition-explorer .ce-counts{
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.condition-explorer .ce-pill{
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--ce-surface2);
  border: 1px solid var(--ce-border);
  font-size: 13px;
  font-weight: 600;
  color: var(--ce-text);
}

/* ---------- row picker ---------- */

.condition-explorer .ce-row-picker{
  display: grid;
  gap: 8px;
}

.condition-explorer .ce-row-pick{
  border: 1px solid var(--ce-border2);
  border-radius: 10px;
  background: var(--ce-surface);
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.condition-explorer .ce-row-pick-text{
  flex: 1 1 auto;
  line-height: 1.45;
  color: var(--ce-text);
  min-width: 0;
}

.condition-explorer .ce-row-pick-label{
  color: var(--ce-muted);
  font-size: 12px;
  margin-bottom: 4px;
}

.condition-explorer .ce-row-pick-code{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  background: var(--ce-surface2);
  border: 1px solid var(--ce-border2);
  padding: 2px 8px;
  border-radius: 999px;
  display: inline-block;
  margin-right: 6px;
  margin-bottom: 6px;
}

.condition-explorer .ce-use-row.widget-button{
  min-width: 120px !important;
  height: 36px !important;
  padding: 0 12px !important;
  border-radius: 8px !important;
  border: 1px solid var(--ce-border) !important;
  background: var(--ce-surface2) !important;
  color: var(--ce-text) !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}

.condition-explorer .ce-use-row.widget-button:hover{
  border-color: var(--ce-accent) !important;
}


/* ---------- custom collapsible sections ---------- */

.condition-explorer .ce-collapse{
  width: 100% !important;
  max-width: 100% !important;
  margin: 10px 0 !important;
  border: 1px solid var(--ce-border) !important;
  border-radius: 12px !important;
  overflow: hidden !important;
  background: var(--ce-surface) !important;
  box-shadow: none !important;
}

.condition-explorer .ce-collapse-header.widget-button{
  width: 100% !important;
  min-height: 44px !important;
  height: auto !important;
  padding: 10px 14px !important;
  margin: 0 !important;
  border: 0 !important;
  border-bottom: 1px solid var(--ce-border) !important;
  border-radius: 0 !important;
  background: var(--ce-surface2) !important;
  color: var(--ce-text) !important;
  box-shadow: none !important;
  text-align: left !important;
  font-weight: 600 !important;
  font-size: 14px !important;
  line-height: 1.35 !important;
  overflow: hidden !important;
}

.condition-explorer .ce-collapse-header.widget-button:hover{
  background: rgba(127,127,127,0.08) !important;
}

html[theme="dark"] .condition-explorer .ce-collapse-header.widget-button:hover{
  background: rgba(255,255,255,0.04) !important;
}



.condition-explorer .ce-collapse-body{
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow-x: hidden !important;
  background: var(--ce-surface) !important;
}

.condition-explorer .ce-collapse-body .widget-box,
.condition-explorer .ce-collapse-body .widget-vbox,
.condition-explorer .ce-collapse-body .widget-hbox,
.condition-explorer .ce-collapse-body .widget-html,
.condition-explorer .ce-collapse-body .widget-output{
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  box-shadow: none !important;
  background: var(--ce-surface) !important;
  overflow-x: hidden !important;
}

.condition-explorer .ce-collapse-body .widget-html > .widget-html-content{
  margin: 0 !important;
  padding: 0 !important;
  background: var(--ce-surface) !important;
  color: var(--ce-text) !important;
}

.condition-explorer .ce-section-body{
  padding: 6px 8px !important;
  margin: 0 !important;
  background: var(--ce-surface) !important;
  color: var(--ce-text) !important;
  overflow-x: hidden !important;
}


.condition-explorer .ce-bool-text{
  font-weight: 700;
}

.condition-explorer .ce-bool-text.true{
  color: var(--ce-true-bd);
}

.condition-explorer .ce-bool-text.false{
  color: var(--ce-false-bd);
}

"""


def inject_condition_css_once(style_id: str = "condition-explorer-css") -> None:
    js = f"""
    <script>
    (function() {{
      const id = {style_id!r};
      if (document.getElementById(id)) return;
      const style = document.createElement("style");
      style.id = id;
      style.type = "text/css";
      style.appendChild(document.createTextNode({CONDITION_EXPLORER_CSS!r}));
      document.head.appendChild(style);
    }})();
    </script>
    """
    display(HTML(js))

def to_python_scalar(value):
    """Convert pandas/numpy scalars into plain Python values when possible."""
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value

def format_value_for_values_box(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return f"'{value}'"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def dataframe_row_to_values_text(row: pd.Series, include_columns: list[str] | None = None) -> str:
    cols = include_columns if include_columns is not None else list(row.index)
    lines = []
    for col in cols:
        if col == "condition_result":
            continue
        lines.append(f"{col} = {format_value_for_values_box(row[col])}")
    return "\n".join(lines)


def row_to_values(row: pd.Series) -> dict:
    return {col: to_python_scalar(row[col]) for col in row.index}


def evaluate_condition_on_dataframe(df: pd.DataFrame, expr: str) -> pd.DataFrame:
    rows = []

    for _, row in df.iterrows():
        values = row_to_values(row)
        steps = []
        result = evaluate(expr, values, steps, expr)

        out = dict(values)
        out["condition_result"] = bool(result["value"])
        rows.append(out)

    return pd.DataFrame(rows)


def html_escape_cell(value) -> str:
    if value is None:
        return "<span class='ce-muted'>NULL</span>"
    return _html.escape(str(value))


def render_dataframe_table(
    df: pd.DataFrame,
    *,
    highlight_match: bool = False,
    max_rows: int = 8,
    show_match_column: bool = True,
) -> str:
    if df is None or df.empty:
        return "<div class='ce-small'>No rows to display.</div>"

    shown = df.head(max_rows).copy()

    columns = list(shown.columns)
    if not show_match_column and "condition_result" in columns:
        columns.remove("condition_result")

    thead = "".join(
        f"<th>{_html.escape('Condition Result' if col == 'condition_result' else str(col))}</th>"
        for col in columns
    )


    body_rows = []
    for _, row in shown.iterrows():
        row_cls = ""
        if highlight_match and "condition_result" in shown.columns:
            row_cls = "ce-row-match" if bool(row["condition_result"]) else "ce-row-no-match"

        cells = []
        for col in columns:
            value = row[col]
            if col == "condition_result":
                value_html = bool_badge(bool(value))
            else:
                value_html = html_escape_cell(value)
            cells.append(f"<td>{value_html}</td>")

        body_rows.append(f"<tr class='{row_cls}'>{''.join(cells)}</tr>")

    note = ""
    if len(df) > max_rows:
        note = f"<div class='ce-small'>Showing first {max_rows} of {len(df)} rows.</div>"

    return f"""
    <div class="ce-table-wrap">
      <table class="ce-table">
        <thead>
          <tr>{thead}</tr>
        </thead>
        <tbody>
          {''.join(body_rows)}
        </tbody>
      </table>
    </div>
    {note}
    """

def build_default_values_text(
    default_values: str = "",
    default_variables: list[str] | None = None,
) -> str:
    existing = parse_values_loose(default_values)
    lines = []

    seen = set()

    for var in (default_variables or []):
        var = var.strip()
        if not var or var in seen:
            continue
        seen.add(var)

        if var in existing:
            lines.append(f"{var} = {existing[var]}")
        else:
            lines.append(f"{var} = ")

    for var, value in existing.items():
        if var in seen:
            continue
        lines.append(f"{var} = {value}")

    return "\n".join(lines)

# =========================================================
# Parsing / evaluation helpers
# =========================================================
def bool_text(value: bool) -> str:
    cls = "true" if value else "false"
    label = "True" if value else "False"
    return f"<span class='ce-bool-text {cls}'>{label}</span>"


def get_step_result_for_table_mode(expr: str, evaluated_df: pd.DataFrame, values_text: str):
    """
    Use current values box when valid.
    Otherwise fallback to first false row, else first row.
    Returns: values, steps, result, new_values_text
    """
    try:
        values = parse_values(values_text)
        steps = []
        result = evaluate(expr, values, steps, expr)
        return values, steps, result, values_text
    except Exception:
        values = pick_step_values_from_evaluated_df(evaluated_df)
        steps = []
        result = evaluate(expr, values, steps, expr)
        new_values_text = dataframe_row_to_values_text(
            pd.Series(values),
            include_columns=list(values.keys())
        )
        return values, steps, result, new_values_text


def pick_step_values_from_evaluated_df(evaluated_df: pd.DataFrame) -> dict:
    """
    Pick the row used for the step-by-step section in table/sql mode.
    Preference:
    1. first false row
    2. otherwise first row
    """
    if evaluated_df is None or evaluated_df.empty:
        return {}

    false_rows = evaluated_df[evaluated_df["condition_result"] == False]
    if not false_rows.empty:
        row = false_rows.iloc[0]
    else:
        row = evaluated_df.iloc[0]

    return {
        col: to_python_scalar(row[col])
        for col in evaluated_df.columns
        if col != "condition_result"
    }


def extract_next_expression(expr: str) -> tuple[str, str]:
    """
    Splits expr into (first_expr, remaining_expr)

    Example:
    "rating = 5 AND population > 10"
      -> ("rating = 5", "AND population > 10")

    "(rating = 5 OR x = 1) AND y = 2"
      -> ("(rating = 5 OR x = 1)", "AND y = 2")
    """
    expr = expr.strip()

    if not expr:
        return "", ""

    # Case 1: starts with parentheses → grab full group
    if expr.startswith("("):
        depth = 0
        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

            if depth == 0:
                return expr[:i+1], expr[i+1:].strip()

        raise ValueError("Unbalanced parentheses")

    # Case 2: atomic → stop at first AND/OR
    match = re.search(r"\s+(AND|OR)\s+", expr, flags=re.IGNORECASE)
    if match:
        idx = match.start()
        return expr[:idx].strip(), expr[idx:].strip()

    return expr, ""


def detect_invalid_variables(expr: str) -> list[str]:
    if not expr:
        return []

    expr_wo_strings = re.sub(r"'[^']*'|\"[^\"]*\"", " ", expr)

    # detect dotted variables like s1.name
    dotted = re.findall(r"\b[a-zA-Z_]\w*\.[a-zA-Z_]\w*\b", expr_wo_strings)

    return list(set(dotted))

def parse_values_loose(text: str) -> dict[str, str]:
    values = {}

    for line in (text or "").splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            continue

        name, raw = line.split("=", 1)
        name = name.strip()
        raw = raw.strip()

        if not re.fullmatch(r"[a-zA-Z_]\w*", name):
            continue

        values[name] = raw

    return values

def extract_variables_from_condition(expr: str) -> list[str]:
    if not expr:
        return []

    # remove quoted strings so words inside them are ignored
    expr_wo_strings = re.sub(r"'[^']*'|\"[^\"]*\"", " ", expr)

    # find identifier-like tokens
    candidates = re.findall(r"\b[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?\b", expr_wo_strings)

    reserved = {
        "AND", "OR", "TRUE", "FALSE", "NULL", "LIKE", "BETWEEN"
    }

    variables = []
    seen = set()

    for token in candidates:
        upper = token.upper()
        if upper in reserved:
            continue
        if token not in seen:
            seen.add(token)
            variables.append(token)

    return variables

def normalize_boolean_keywords(expr: str) -> str:
    expr = re.sub(r"\bAND\b", "AND", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bOR\b", "OR", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bNOT\b", "NOT", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bIN\b", "IN", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bLIKE\b", "LIKE", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bBETWEEN\b", "BETWEEN", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bIS\b", "IS", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bNULL\b", "NULL", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bTRUE\b", "TRUE", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bFALSE\b", "FALSE", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\s+", " ", expr).strip()
    return expr


def split_top_level(expr: str, op: str) -> list[str]:
    """
    Split an expression by top-level AND / OR, ignoring:
    - nested parentheses
    - strings
    - the AND that belongs to BETWEEN ... AND ...
    """
    expr = expr.strip()
    target = op.upper()

    parts = []
    depth = 0
    start = 0
    i = 0
    in_single = False
    in_double = False
    between_pending_and = False

    while i < len(expr):
        ch = expr[i]

        # quoted strings
        if in_single:
            if ch == "'" and (i == 0 or expr[i - 1] != "\\"):
                in_single = False
            i += 1
            continue

        if in_double:
            if ch == '"' and (i == 0 or expr[i - 1] != "\\"):
                in_double = False
            i += 1
            continue

        if ch == "'":
            in_single = True
            i += 1
            continue

        if ch == '"':
            in_double = True
            i += 1
            continue

        # parentheses
        if ch == "(":
            depth += 1
            i += 1
            continue

        if ch == ")":
            depth -= 1
            i += 1
            continue

        # only inspect keywords at top level
        if depth == 0 and (ch.isalpha() or ch == "_"):
            j = i
            while j < len(expr) and (expr[j].isalnum() or expr[j] == "_"):
                j += 1

            word = expr[i:j].upper()

            # BETWEEN marks that the next AND is not a boolean AND
            if word == "BETWEEN":
                between_pending_and = True
                i = j
                continue

            # ignore the AND belonging to BETWEEN
            if word == "AND" and between_pending_and:
                between_pending_and = False
                i = j
                continue

            # normal top-level operator split
            if word == target:
                parts.append(expr[start:i].strip())
                start = j
                i = j
                continue

            i = j
            continue

        i += 1

    parts.append(expr[start:].strip())
    return parts

def strip_outer_parens(expr: str) -> str:
    expr = expr.strip()

    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        wraps_all = True

        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

            if depth == 0 and i != len(expr) - 1:
                wraps_all = False
                break

        if wraps_all:
            expr = expr[1:-1].strip()
        else:
            break

    return expr


def parse_literal(raw: str):
    raw = raw.strip()

    if raw.lower() == "null":
        return None

    if raw.lower() == "true":
        return True

    if raw.lower() == "false":
        return False

    if re.fullmatch(r"-?\d+", raw):
        return int(raw)

    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)

    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]

    return raw


def parse_values(text: str) -> dict:
    values = {}

    for line in text.strip().splitlines():
        if not line.strip():
            continue

        if "=" not in line:
            raise ValueError(f"Could not understand line: {line}")

        name, raw = line.split("=", 1)
        name = name.strip()
        raw = raw.strip()

        if not re.fullmatch(r"[a-zA-Z_]\w*", name):
            raise ValueError(f"Invalid variable name: {name}")

        values[name] = parse_literal(raw)

    return values


def format_bool_word(v: bool) -> str:
    return "True" if v else "False"


def format_value(v):
    if v is None:
        return "NULL"
    return str(v)
    
def eval_atomic(expr: str, values: dict) -> dict:
    expr = expr.strip()

    # BETWEEN operator
    m_between = re.fullmatch(
        r"([a-zA-Z_]\w*)\s+BETWEEN\s+(.+?)\s+AND\s+(.+)",
        expr,
        flags=re.IGNORECASE,
    )
    if m_between:
        left, low_raw, high_raw = m_between.groups()

        left = left.strip()
        low_raw = low_raw.strip()
        high_raw = high_raw.strip()

        if left not in values:
            raise ValueError(f"Missing value for variable: {left}")

        left_val = values[left]
        low_val = values[low_raw] if low_raw in values else parse_literal(low_raw)
        high_val = values[high_raw] if high_raw in values else parse_literal(high_raw)

        if low_val is None or high_val is None or left_val is None:
            result = False
            reduced = f"{format_value(low_val)} <= {format_value(left_val)} <= {format_value(high_val)}"
        else:
            result = low_val <= left_val <= high_val
            reduced = f"{format_value(low_val)} <= {format_value(left_val)} <= {format_value(high_val)}"

        return {
            "expr": expr,
            "value": result,
            "rendered": format_bool_word(result),
            "reduced": reduced,
        }

    # IN operator
    m_in = re.fullmatch(r"([a-zA-Z_]\w*)\s+IN\s*\((.+)\)", expr, flags=re.IGNORECASE)
    if m_in:
        left, raw_list = m_in.groups()

        if left not in values:
            raise ValueError(f"Missing value for variable: {left}")

        left_val = values[left]

        # split values inside (...)
        items = [parse_literal(x.strip()) for x in raw_list.split(",")]

        result = left_val in items
        reduced = f"{left_val} IN {items}"

        return {
            "expr": expr,
            "value": result,
            "rendered": format_bool_word(result),
            "reduced": reduced,
        }

    # IS NULL / IS NOT NULL
    m_null = re.fullmatch(r"([a-zA-Z_]\w*)\s+IS\s+(NOT\s+)?NULL", expr, flags=re.IGNORECASE)
    if m_null:
        var, not_part = m_null.groups()

        val = values.get(var, None)  # <-- key change

        is_null = val is None
        result = not is_null if not_part else is_null

        val_str = format_value(val)

        reduced = f"{val_str} IS {'NOT ' if not_part else ''}NULL"


        return {
            "expr": expr,
            "value": result,
            "rendered": format_bool_word(result),
            "reduced": reduced,
        }

    # LIKE operator
    m_like = re.fullmatch(
        r"([a-zA-Z_]\w*)\s+LIKE\s+(.+)",
        expr,
        flags=re.IGNORECASE,
    )
    if m_like:
        left, pattern_raw = m_like.groups()

        if left not in values:
            raise ValueError(f"Missing value for variable: {left}")

        left_val = values[left]
        pattern_val = values[pattern_raw] if pattern_raw in values else parse_literal(pattern_raw)

        if left_val is None:
            result = False
            reduced = f"{left_val} LIKE {pattern_val}"
        else:
            left_str = str(left_val)
            pattern_str = str(pattern_val)

            # SQL LIKE -> regex
            regex = re.escape(pattern_str)
            regex = regex.replace("%", ".*").replace("_", ".")
            regex = f"^{regex}$"

            result = re.match(regex, left_str) is not None
            reduced = f"{left_str} LIKE {pattern_str}"

        return {
            "expr": expr,
            "value": result,
            "rendered": format_bool_word(result),
            "reduced": reduced,
        }

    m = re.fullmatch(r"([a-zA-Z_]\w*)\s*(=|!=|>=|<=|>|<)\s*(.+)", expr)
    if not m:
        raise ValueError(f"Could not understand atomic condition: {expr}")

    left, op, right = m.groups()
    right = right.strip()

    if left not in values:
        raise ValueError(f"Missing value for variable: {left}")

    left_val = values[left]

    if right in values:
        right_val = values[right]
    else:
        right_val = parse_literal(right)

    if op == "=":
        result = left_val == right_val
        reduced = f"{left_val} = {right_val}"
    elif op == "!=":
        result = left_val != right_val
        reduced = f"{left_val} != {right_val}"
    elif op == ">":
        result = left_val > right_val
        reduced = f"{left_val} > {right_val}"
    elif op == "<":
        result = left_val < right_val
        reduced = f"{left_val} < {right_val}"
    elif op == ">=":
        result = left_val >= right_val
        reduced = f"{left_val} >= {right_val}"
    elif op == "<=":
        result = left_val <= right_val
        reduced = f"{left_val} <= {right_val}"
    else:
        raise ValueError(f"Unsupported operator: {op}")

    return {
        "expr": expr,
        "value": result,
        "rendered": format_bool_word(result),
        "reduced": reduced,
    }

def normalize_condition_spacing(expr: str) -> str:
    return re.sub(r"\s+", " ", expr).strip()

def evaluate(expr: str, values: dict, steps: list, original_expr: str | None = None) -> dict:
    expr = normalize_condition_spacing(expr)
    stripped = strip_outer_parens(expr)

    if original_expr is None:
        original_expr = stripped

    # OR
    parts = split_top_level(stripped, "OR")
    if len(parts) > 1:
        evaluated_parts = [evaluate(p, values, steps, p) for p in parts]
        reduced = " OR ".join(part["rendered"] for part in evaluated_parts)
        result = any(part["value"] for part in evaluated_parts)

        steps.append({
            "expr": original_expr.strip(),
            "reduced": reduced,
            "value": result,
        })

        return {
            "expr": original_expr.strip(),
            "value": result,
            "rendered": format_bool_word(result),
        }

    # AND
    parts = split_top_level(stripped, "AND")
    if len(parts) > 1:
        evaluated_parts = [evaluate(p, values, steps, p) for p in parts]
        reduced = " AND ".join(part["rendered"] for part in evaluated_parts)
        result = all(part["value"] for part in evaluated_parts)

        steps.append({
            "expr": original_expr.strip(),
            "reduced": reduced,
            "value": result,
        })

        return {
            "expr": original_expr.strip(),
            "value": result,
            "rendered": format_bool_word(result),
        }

    # NOT
    if stripped.upper().startswith("NOT "):
        inner_expr = stripped[4:].strip()
        evaluated_inner = evaluate(inner_expr, values, steps, inner_expr)
        result = not evaluated_inner["value"]

        steps.append({
            "expr": original_expr.strip(),
            "reduced": f"NOT {evaluated_inner['rendered']}",
            "value": result,
        })

        return {
            "expr": original_expr.strip(),
            "value": result,
            "rendered": format_bool_word(result),
        }

    # atomic
    atom = eval_atomic(stripped, values)
    steps.append({
        "expr": atom["expr"],
        "reduced": atom["reduced"],
        "value": atom["value"],
    })
    return atom


def build_balanced_preview(df: pd.DataFrame, max_rows: int = 12) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    true_df = df[df["condition_result"] == True]
    false_df = df[df["condition_result"] == False]

    half = max_rows // 2

    # take initial halves
    true_part = true_df.head(half)
    false_part = false_df.head(half)

    # how many we actually got
    current = len(true_part) + len(false_part)

    # fill remaining slots
    remaining = max_rows - current

    if remaining > 0:
        # try to fill from the bigger side
        if len(true_df) > len(true_part):
            extra = true_df.iloc[len(true_part):len(true_part)+remaining]
            true_part = pd.concat([true_part, extra])
        elif len(false_df) > len(false_part):
            extra = false_df.iloc[len(false_part):len(false_part)+remaining]
            false_part = pd.concat([false_part, extra])

    # combine
    result = pd.concat([true_part, false_part])
    result["__order__"] = result["condition_result"].astype(int)
    result = result.sort_values("condition_result", ascending=False).drop(columns="__order__")

    # optional: reset index for clean display
    return result.reset_index(drop=True)

def make_row_dropdown(
    df: pd.DataFrame,
    val_box: widgets.Textarea,
    *,
    preview_columns: list[str] | None = None,
    max_rows: int = 8,
    rerun_callback=None,
):
    if df is None or df.empty:
        return widgets.HTML("")

    shown = build_balanced_preview(df, max_rows=max_rows).copy()

    options = []
    for display_idx, (_, row) in enumerate(shown.iterrows(), start=1):
        cols = preview_columns if preview_columns is not None else [
            c for c in shown.columns if c != "condition_result"
        ]
        cols = [c for c in cols if c in shown.columns and c != "condition_result"]

        # short preview (first 2 cols)
        label_parts = [f"{col}={row[col]}" for col in cols[:2]]

        # condition result
        result_str = "true" if bool(row["condition_result"]) else "false"

        label = f"Row {display_idx}: " + ", ".join(label_parts)
        label += f" | condition result={result_str}"

        values_text = dataframe_row_to_values_text(row, include_columns=cols)

        options.append((label, values_text))

    dropdown = widgets.Dropdown(
        options=options,
        description="Row:",
        layout=widgets.Layout(width="70%"),
    )

    btn = widgets.Button(
        description="Use this row",
        layout=widgets.Layout(width="160px", height="36px"),
    )
    btn.add_class("ce-use-row")

    def on_click(_):
        val_box.value = dropdown.value
        if rerun_callback:
            rerun_callback(None)

    btn.on_click(on_click)

    ui = widgets.HBox(
        [dropdown, btn],
        layout=widgets.Layout(width="100%", align_items="center", gap="10px"),
    )

    wrapper = widgets.VBox(
        [
            widgets.HTML("""
                <div class="ce-small" style="margin-top:10px;">
                  Pick a row and reuse its values:
                </div>
            """),
            ui
        ],
        layout=widgets.Layout(width="100%"),
    )

    return wrapper
# =========================================================
# Rendering
# =========================================================

def bool_badge(value: bool) -> str:
    cls = "true" if value else "false"
    label = "True" if value else "False"
    return f"<span class='ce-bool {cls}'>{label}</span>"

def render_steps_section(steps: list[dict], final_value: bool, values: dict) -> str:
    # build variable pills
    pill_html = ""
    if values:
        pills = []
        for k, v in values.items():
            val_str = "NULL" if v is None else str(v)
            pills.append(f"<span class='ce-pill'>{_html.escape(k)} = {_html.escape(val_str)}</span>")
        pill_html = f"""
        <div class="ce-small">Input values:</div>
        <div style="height:6px"></div>
        <div class="ce-counts">
            {''.join(pills)}
        </div>
        <div style="height:12px"></div>
        """
    steps_html = []
    for i, step in enumerate(steps, 1):
        condition_html = f"<span class='ce-code'>{_html.escape(step['expr'])}</span>"
        reduced_text = _html.escape(step["reduced"])
        reduced_text = re.sub(r"\bTrue\b", lambda _: bool_text(True), reduced_text)
        reduced_text = re.sub(r"\bFalse\b", lambda _: bool_text(False), reduced_text)
        reduced_html = f"<span class='ce-code'>{reduced_text}</span>"
        result_html = bool_badge(step["value"])

        steps_html.append(f"""
        <div class='ce-step'>
          <div class='ce-step-inner'>
            <div class='ce-num'>{i}</div>
            <div class='ce-step-text'>
              Condition {condition_html} is {reduced_html}, so it returns {result_html}.
            </div>
          </div>
        </div>
        """)

    return f"""
    <div class="ce-section-body">
      {pill_html}
      <div class="ce-steps">
        {''.join(steps_html)}
      </div>
      <div class="ce-final" style="margin-top:12px;">
        Final result: {bool_badge(final_value)}
      </div>
    </div>
    """




def render_all_rows_section(evaluated_df: pd.DataFrame, max_rows: int = 8) -> str:
    preview_df = build_balanced_preview(evaluated_df, max_rows=max_rows)

    matched_df = evaluated_df[evaluated_df["condition_result"] == True].copy()
    total_rows = len(evaluated_df)
    matched_rows = len(matched_df)
    not_matched_rows = total_rows - matched_rows

    summary_html = f"""
    <div class="ce-small">
      Each row is evaluated using the condition, similar to a SQL <span class="ce-code">WHERE</span> clause.
    </div>
    <div style="height:10px"></div>
    <div class="ce-counts">
      <span class="ce-pill">Total rows: {total_rows}</span>
      <span class="ce-pill">Matched rows: {matched_rows}</span>
      <span class="ce-pill">Not matched: {not_matched_rows}</span>
    </div>
    <div style="height:12px"></div>
    """

    table_html = render_dataframe_table(
        preview_df,
        highlight_match=True,
        max_rows=max_rows,
        show_match_column=True,
    )

    return f"<div class='ce-section-body'>{summary_html}{table_html}</div>"


def make_collapsible_section(title: str, body_widget, expanded: bool = True):
    arrow_open = "▾"
    arrow_closed = "▸"
    spacer = "\u00A0\u00A0\u00A0"   # 3 non-breaking spaces

    def label(is_open: bool) -> str:
        arrow = arrow_open if is_open else arrow_closed
        return f"{spacer}{arrow}{spacer}{title}"

    header = widgets.Button(
        description=label(expanded),
        layout=widgets.Layout(width="100%", min_height="44px")
    )
    header.add_class("ce-collapse-header")

    body = widgets.VBox([body_widget], layout=widgets.Layout(width="100%"))
    body.add_class("ce-collapse-body")
    body.layout.display = "block" if expanded else "none"

    def on_toggle(_):
        is_open = body.layout.display != "none"
        body.layout.display = "none" if is_open else "block"
        header.description = label(not is_open)

    header.on_click(on_toggle)

    wrapper = widgets.VBox([header, body], layout=widgets.Layout(width="100%"))
    wrapper.add_class("ce-collapse")
    return wrapper

def html_section(html: str):
    w = widgets.HTML(value=html)
    w.add_class("ce-section-html")
    return w

def render_error(message: str, *, is_html: bool = False) -> str:
    body = message if is_html else _html.escape(message)
    return f"""
    <div class="condition-explorer">
      <div class="ce-error">
        <b>❌ Error</b><br/>
        {body}
      </div>
    </div>
    """



# =========================================================
# Main UI
# =========================================================

def make_condition_explorer(
    default_condition: str = "",
    default_values: str = "",
    default_variables: list[str] | None = None,
    title: str = "ℹ️ Condition evaluator",
    subtitle: str = (
        "Type a condition and some input values, then evaluate the logic step by step."
    ),
    table_df: pd.DataFrame | None = None,
    preview_columns: list[str] | None = None,
    max_preview_rows: int = 8,
    duckdb_connection=None,
    explorer_id: str = "explorer_1", 
):
    LOG_CONDITION_EXPLORER_FILE = Path("condition_explorer_history.csv")
    latest_condition = load_latest_condition(LOG_CONDITION_EXPLORER_FILE, explorer_id)

    inject_condition_css_once()

    # top info card
    subtitle_html = markdown.markdown(subtitle)
    intro = widgets.HTML(f"""
    <div class="ce-input-box">
    <div class="ce-title">{_html.escape(title)}</div>
    <div class="ce-subtitle">{subtitle_html}</div>
    </div>
    """)

    # labels
    cond_label = widgets.HTML("""
    <div class="ce-field-block">
      <div class="ce-label">Condition</div>
    </div>
    """)

    values_label = widgets.HTML("""
    <div class="ce-field-block">
      <div class="ce-label">Values</div>
    </div>
    """)

    latest_condition = load_latest_condition(LOG_CONDITION_EXPLORER_FILE, explorer_id)
    # inputs nu
    cond_box = widgets.Textarea(
        value=latest_condition if latest_condition else default_condition,
        placeholder="Type your condition, Example: rating IN (4, 5) OR (population IS NULL AND NOT featured = true) AND score >= 8 OR name like 'A%",
        layout=widgets.Layout(width="100%", height="90px")
    )
    cond_box.add_class("ce-condition-textarea")

    initial_values_text = build_default_values_text(
        default_values=default_values,
        default_variables=default_variables,
    )

    val_box = widgets.Textarea(
        value=initial_values_text,
        placeholder="Write one vairable per line, for example: rating = 5",
        layout=widgets.Layout(width="100%", height="110px")
    )
    val_box.add_class("ce-values-textarea")

    source_options = [("Input values", "values")]

    if duckdb_connection is not None:
        source_options.append(("DB table", "table"))
    elif table_df is not None:
        source_options.append(("DataFrame table", "table"))

    if duckdb_connection is not None:
        source_options.append(("SQL query", "sql"))

    source_mode = widgets.Dropdown(
        options=source_options,
        description="Source:",
        layout=widgets.Layout(width="300px"),
    )

    recent_options = [("Recent conditions", "")] + load_recent_conditions(
        LOG_CONDITION_EXPLORER_FILE, explorer_id, limit=12
    )

    recent_conditions_dropdown = widgets.Dropdown(
        options=recent_options,
        description="Recent:",
        layout=widgets.Layout(width="420px"),
    )

    def on_extract_variables(_):
      expr = cond_box.value.strip()
      invalid_vars = detect_invalid_variables(expr)
      if invalid_vars:
          val_box.value = ""
          results_box.children = (widgets.HTML(render_error(
              "Cannot extract variables from SQL-style names like: "
              + ", ".join(invalid_vars)
              + "<br/><br/>Use simple variables instead.",
              is_html=True
          )),)
          return
      vars_found = extract_variables_from_condition(expr)

      if not vars_found:
          val_box.value = ""
          return

      existing = parse_values_loose(val_box.value)

      lines = []
      for var in vars_found:
          current = existing.get(var, "")
          if current == "":
              lines.append(f"{var} = ")
          else:
              lines.append(f"{var} = {current}")

      val_box.value = "\n".join(lines)

    extract_vars_btn = widgets.Button(
        description="Extract variables",
        layout=widgets.Layout(width="170px", height="40px")
    )
    extract_vars_btn.layout.display = "block"
    extract_vars_btn.add_class("ce-use-row")
    extract_vars_btn.on_click(on_extract_variables)

    source_row = widgets.HBox(
        [source_mode, extract_vars_btn, recent_conditions_dropdown],
        layout=widgets.Layout(width="100%", gap="12px")
    )

    def on_recent_condition_change(change):
        if change["name"] != "value":
            return
        selected = change["new"]
        if selected:
            cond_box.value = selected



    recent_conditions_dropdown.observe(on_recent_condition_change, names="value")

    if duckdb_connection:
        tables = duckdb_connection.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
    else:
        table_names = []

    table_dropdown = widgets.Dropdown(
        options=table_names,
        description="Table:",
        layout=widgets.Layout(width="300px"),
    )

    table_container_children = []
    if duckdb_connection is not None:
        table_container_children.append(table_dropdown)
    elif table_df is not None:
        table_container_children.append(
            widgets.HTML("<div class='ce-small'>Using provided dataframe table.</div>")
        )

    table_container = widgets.VBox(table_container_children)

    sql_box = widgets.Textarea(
        placeholder="SELECT rating, population FROM cities",
        layout=widgets.Layout(width="100%", height="90px")
    )

    values_container = widgets.VBox([values_label, val_box])
    sql_container = widgets.VBox([sql_box])


    def update_source_visibility(change=None):
        mode = source_mode.value

        values_container.layout.display = "block" if mode == "values" else "none"
        table_container.layout.display = "block" if mode == "table" else "none"
        sql_container.layout.display = "block" if mode == "sql" else "none"

        extract_vars_btn.layout.display = "block" if mode == "values" else "none"

    source_mode.observe(update_source_visibility, names="value")
    update_source_visibility()
    # button
    run_btn = widgets.Button(
        description="Evaluate",
        layout=widgets.Layout(width="160px", height="42px")
    )
    run_btn.add_class("ce-run")

    actions = widgets.HBox([run_btn], layout=widgets.Layout(width="100%"))
    actions.add_class("ce-actions")

    # wrap the whole top section in one single box
    controls_inner = widgets.VBox(
        [intro, cond_label, cond_box, source_row,  values_container, table_container, sql_container, actions],
        layout= widgets.Layout(
              width="100%",
              overflow="hidden"
          )
    )


    controls_box = widgets.VBox([controls_inner], layout=widgets.Layout(width="100%"))
    controls_box.layout = widgets.Layout(
        width="100%",
        overflow="hidden"
    )


    # results
    results_box = widgets.VBox([], layout=widgets.Layout(width="100%"))
    results_box.add_class("condition-explorer")




    def on_run(_):
        try:
            expr = cond_box.value.strip()
            if not expr:
                results_box.children = (widgets.HTML(render_error("Please type a condition first.")),)
                return

            append_condition_history(LOG_CONDITION_EXPLORER_FILE, explorer_id, expr)
            recent_conditions_dropdown.options = [("Recent conditions", "")] + load_recent_conditions(
                LOG_CONDITION_EXPLORER_FILE, explorer_id, limit=12
            )

            expr = normalize_boolean_keywords(expr)

            invalid_vars = detect_invalid_variables(expr)
            if invalid_vars:
                msg = (
                    "Invalid variable names detected: "
                    + ", ".join(invalid_vars)
                    + "<br/><br/>"
                    "⚠️ This explorer currently supports only simple variable names "
                    "(e.g. <span class='ce-code'>rating</span>, <span class='ce-code'>population</span>).<br/>"
                    "Do not use table-qualified names like "
                    "<span class='ce-code'>s1.name</span>.<br/><br/>"
                    "👉 Make variables unique instead (e.g. speaker1_name, speaker2_name)."
                )
                results_box.children = (widgets.HTML(render_error(msg, is_html=True)),)
                return

            mode = source_mode.value

            values = {}
            steps = []
            result = None
            df_for_preview = None
            evaluated_df = None

            # ---- VALUES MODE ----
            if mode == "values":
                values = parse_values(val_box.value)
                result = evaluate(expr, values, steps, expr)

                # also show table preview if a dataframe was passed in
                if table_df is not None:
                    df_for_preview = table_df.copy()

                    if preview_columns is not None:
                        keep_cols = [c for c in preview_columns if c in df_for_preview.columns]
                        df_for_preview = df_for_preview[keep_cols]

                    evaluated_df = evaluate_condition_on_dataframe(df_for_preview, expr)


            # ---- TABLE MODE ----
            elif mode == "table":
                if duckdb_connection is not None:
                    if not table_dropdown.value:
                        raise ValueError("Please select a table.")

                    df_for_preview = duckdb_connection.execute(
                        f"SELECT * FROM {table_dropdown.value}"
                    ).df()

                elif table_df is not None:
                    df_for_preview = table_df.copy()

                else:
                    raise ValueError("No table available.")

                if preview_columns is not None:
                    keep_cols = [c for c in preview_columns if c in df_for_preview.columns]
                    df_for_preview = df_for_preview[keep_cols]

                evaluated_df = evaluate_condition_on_dataframe(df_for_preview, expr)

                values, steps, result, new_values_text = get_step_result_for_table_mode(
                    expr=expr,
                    evaluated_df=evaluated_df,
                    values_text=val_box.value,
                )
                val_box.value = new_values_text

            # ---- SQL MODE ----
            elif mode == "sql":
                if not duckdb_connection:
                    raise ValueError("DuckDB connection not available.")

                query = sql_box.value.strip()
                if not query:
                    raise ValueError("Please write a SQL query.")

                df_for_preview = duckdb_connection.execute(query).df()

                if preview_columns is not None:
                    keep_cols = [c for c in preview_columns if c in df_for_preview.columns]
                    df_for_preview = df_for_preview[keep_cols]

                evaluated_df = evaluate_condition_on_dataframe(df_for_preview, expr)

                values, steps, result, new_values_text = get_step_result_for_table_mode(
                    expr=expr,
                    evaluated_df=evaluated_df,
                    values_text=val_box.value,
                )
                val_box.value = new_values_text

            sections = []

            # In all modes, show step-by-step if we have a result
            if result is not None:
                step_html = html_section(
                    render_steps_section(
                        steps=steps,
                        final_value=result["value"],
                        values=values,
                    )
                )
                sections.append(
                    make_collapsible_section(
                        "Step-by-step evaluation",
                        step_html,
                        expanded=True
                    )
                )

            # In table/sql mode, also show the table preview
            if evaluated_df is not None:
                all_rows_html = html_section(
                    render_all_rows_section(
                        evaluated_df=evaluated_df,
                        max_rows=max_preview_rows
                    )
                )

                row_dropdown = make_row_dropdown(
                    evaluated_df,
                    val_box,
                    preview_columns=preview_columns,
                    max_rows=max_preview_rows,
                    rerun_callback=on_run,
                )

                combined = widgets.VBox(
                    [all_rows_html, row_dropdown],
                    layout=widgets.Layout(width="100%"),
                )

                sections.append(
                    make_collapsible_section(
                        "All rows with match result",
                        combined,
                        expanded=True
                    )
                )

            results_box.children = tuple(sections)

        except Exception as e:
            results_box.children = (widgets.HTML(render_error(str(e))),)

    run_btn.on_click(on_run)

    content = widgets.VBox(
        [controls_box, results_box],
        layout=widgets.Layout(
            width="100%",
            padding="0 12px 0 12px",
            overflow="hidden"
        )
    )

    ui = widgets.VBox(
        [content],
        layout=widgets.Layout(
            width="100%",
            max_width="1100px",
            margin="0",
            padding="0",
            overflow="hidden"
        )
    )

    ui.add_class("condition-explorer")


    display(ui)
