# notebook_lib/sql_runner.py
from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Callable, Optional, Tuple, Union, List, Any, Dict

import pandas as pd
import ipywidgets as widgets
from IPython.display import display, clear_output, HTML

from notebook_lib.sql_runner_store import (
    append_history, load_latest_map, save_latest_map, load_scores, save_scores
)

from notebook_lib.sql_runner_ui_bits import (
    inject_css_once,
    md_to_html,
    pick_success_title,
    render_score_badge,
    render_validation_banner,
    render_submit_banner,
)

def _detect_db_type(conn) -> str:
    """
    Detect database backend from connection object.
    Returns: 'sqlite' or 'duckdb'
    """
    mod = type(conn).__module__.lower()
    name = type(conn).__name__.lower()

    if "duckdb" in mod or "duckdb" in name:
        return "duckdb"

    if "sqlite3" in mod or "sqlite" in name:
        return "sqlite"

    raise ValueError(
        f"Unsupported database connection type: {type(conn)}. "
        "Supported: sqlite3, duckdb"
    )

def make_sql_runner(
    conn,
    runner_id: str,
    default_sql: Optional[str] = None,
    sol_sql: Optional[str] = None,
    select_only: bool = True,
    validator: Optional[
        Callable[[str, Optional[pd.DataFrame], Any], Tuple[bool, Union[str, List[str]]]]
    ] = None,
    dedupe: bool = True,
    description_md: Optional[str] = None,
    hint_enabled: bool = False,
    hint_md: Optional[str] = None,
    schema_tables: Optional[List[str]] = None,

    # --- Cloud submit (optional) ---
    submitter: Optional[Callable[[str, str], Dict[str, Any]]] = None,
):
    db_type = _detect_db_type(conn)
    if db_type not in {"sqlite", "duckdb"}:
        raise ValueError("db_type must be 'sqlite' or 'duckdb'")

    # ---------- persistence ----------
    LOG_ALL_FILE = Path("sql_query_log.csv")
    LOG_LATEST_FILE = Path("sql_query_latest.csv")
    SCORE_FILE = Path("sql_grades.csv")

    latest_map = load_latest_map(LOG_LATEST_FILE)
    last_saved = latest_map.get(runner_id)
    initial_sql = last_saved if last_saved is not None else (default_sql or "")

    # ---------- UI chrome (CSS) ----------
    inject_css_once()

    # ---------- widgets ----------
    desc_widget = None
    if description_md:
        desc_widget = widgets.HTML(
            value=f"<div class='sql-desc'>{md_to_html(description_md)}</div>"
        )

    # Hint components
    show_hint_ui = bool(hint_enabled and hint_md)

    hint_btn = None
    hint_box = None
    if show_hint_ui:
        hint_btn = widgets.Button(
            description="💡",
            tooltip="Show/hide hint",
            layout=widgets.Layout(width="40px", height="40px"),
        )
        hint_visible = False

        hint_html = widgets.HTML(value=f"<div class='sql-hintbox'>{md_to_html(hint_md)}</div>")
        hint_box = widgets.Box([hint_html], layout=widgets.Layout(display="none"))

        def on_hint_click(_):
            nonlocal hint_visible
            hint_visible = not hint_visible
            hint_box.layout.display = "block" if hint_visible else "none"

        hint_btn.on_click(on_hint_click)

    # Solution components
    show_sol_ui = bool(sol_sql)

    sol_btn = None
    sol_box = None
    if show_sol_ui:
        sol_btn = widgets.Button(
            description="Show solution",
            tooltip="Show the reference SQL solution",
            layout=widgets.Layout(),
        )
        sol_btn.add_class("sql-sol-toggle")
        sol_visible = False

        sol_close_btn = widgets.Button(
            description="✕",
            tooltip="Close",
            layout=widgets.Layout(width="28px", height="28px"),
        )
        sol_close_btn.add_class("sql-sol-close")

        sol_title = widgets.HTML("<b>Solution</b>")
        sol_header = widgets.HBox(
            [sol_title, sol_close_btn],
            layout=widgets.Layout(justify_content="space-between", align_items="center")
        )

        sol_body = widgets.HTML(value=f"<pre>{_html.escape(sol_sql)}</pre>")

        sol_inner = widgets.VBox([sol_header, sol_body])
        sol_inner.add_class("sql-solbox")

        sol_box = widgets.Box([sol_inner], layout=widgets.Layout(display="none"))

        def on_sol_click(_):
            nonlocal sol_visible
            sol_visible = not sol_visible
            sol_box.layout.display = "block" if sol_visible else "none"
            sol_btn.description = "Hide solution" if sol_visible else "Show solution"

        def on_sol_close(_):
            nonlocal sol_visible
            sol_visible = False
            sol_box.layout.display = "none"
            sol_btn.description = "Show solution"

        sol_btn.on_click(on_sol_click)
        sol_close_btn.on_click(on_sol_close)

    # ---------- validation banner ----------
    validation_widget = widgets.HTML(value="")
    validation_nonce = 0

    def hide_validation():
        validation_widget.value = ""

    def show_validation(ok: bool, problems_or_msg):
        nonlocal validation_nonce
        validation_nonce += 1

        if isinstance(problems_or_msg, str):
            message = problems_or_msg or ""
        else:
            message = " ".join(problems_or_msg or [])

        title = pick_success_title() if ok else "🙁 Not correct yet"
        box_id = f"val_{runner_id}_{validation_nonce}"

        validation_widget.value = render_validation_banner(
            ok=ok,
            title=title,
            message=message,
            box_id=box_id,
        )

    # ---------- editor / outputs ----------
    box = widgets.Textarea(
        value=initial_sql,
        placeholder="Type your SQL query here...",
        description="",
        layout=widgets.Layout(width="100%")
    )
    box.add_class("sql-editor")

    results_out = widgets.Output()
    schema_out = widgets.Output()

    results_box = widgets.Box([results_out], layout=widgets.Layout(width="100%", padding="8px"))
    schema_box = widgets.Box([schema_out], layout=widgets.Layout(width="100%", padding="8px"))

    tabs = widgets.Tab(children=[results_box, schema_box], layout=widgets.Layout(width="100%"))
    tabs.set_title(0, "Query results")
    tabs.set_title(1, "Schema Database")

    # Toolbar buttons
    run_btn = widgets.Button(
        description="▶",
        tooltip="Run query",
        layout=widgets.Layout(width="40px", height="40px"),
        button_style="primary"
    )
    revert_btn = widgets.Button(description="⟲", tooltip="Revert to last saved", layout=widgets.Layout(width="40px", height="40px"))

    reset_btn = None
    if default_sql:
        reset_btn = widgets.Button(
            description="↩",
            tooltip="Reset to default SQL",
            layout=widgets.Layout(width="40px", height="40px")
        )

    clear_results_btn = widgets.Button(description="🧹", tooltip="Clear results output", layout=widgets.Layout(width="40px", height="40px"))
    clear_query_btn = widgets.Button(description="⌫", tooltip="Clear query editor", layout=widgets.Layout(width="40px", height="40px"))

    status = widgets.HTML('<span class="hint"></span>')

    def set_status(msg: str):
        status.value = f'<span class="hint">{msg}</span>' if msg else '<span class="hint"></span>'

    score_store = load_scores(SCORE_FILE)
    score_key = runner_id

    score_widget = widgets.HTML(value="")


    def _update_score_widget(*, current_points=None, max_points=None, attempt=None):
        rec = score_store.get(score_key, {})

        if current_points is not None:
            rec["current_points"] = current_points

        if max_points is not None:
            rec["max_points"] = max_points

        if attempt is not None:
            rec["attempt"] = attempt

        score_store[score_key] = rec
        save_scores(SCORE_FILE, score_store)
        score_widget.value = render_score_badge(rec.get("current_points"), rec.get("max_points"), rec.get("attempt"))

    # Initialize from CSV
    rec = score_store.get(score_key, {})
    score_widget.value = render_score_badge(
        rec.get("current_points"),
        rec.get("max_points"),
        rec.get("attempt"),
    )

    submit_widget = widgets.HTML(value="")
    submit_nonce = 0

    def show_submit_result(
        *,
        ok: bool,
        final_points: Optional[int] = None,
        max_points: Optional[int] = None,
        attempt: Optional[int] = None,
        penalty_label: Optional[str] = None,   # e.g. "Penalty: 80%" or "Multiplier: ×0.8"
        hint: Optional[str] = None,            # revealed failure text
        error: Optional[str] = None            # hard error (exam closed, invalid token, etc.)
    ):
        nonlocal submit_nonce
        submit_nonce += 1
        box_id = f"submit_{runner_id}_{submit_nonce}"

        if not ok:
            submit_widget.value = render_submit_banner(
                box_id=box_id,
                ok=False,
                good=False,
                title="❌ Submission failed",
                error=error or "Something went wrong.",
            )
            return

        # --- Success-ish banner ---
        # If hint exists => submitted but not fully correct yet (warn)
        good = not bool(hint)
        title = "✅ Correct!" if good else "❌ Submitted (not perfect yet)"

        # Build score line (HTML fragment)
        score_line = ""
        if final_points is not None:
            if max_points is not None:
                score_line = f"<b>Points:</b> {final_points} / {max_points}<br/>"
            else:
                score_line = f"<b>Points:</b> {final_points}<br/>"

        # Build meta line (plain text, escape it!)
        meta_bits = []
        if attempt is not None:
            meta_bits.append(f"Attempt {attempt}")
        if penalty_label:
            meta_bits.append(penalty_label)

        meta_line = _html.escape(" • ".join(meta_bits))

        submit_widget.value = render_submit_banner(
            box_id=box_id,
            ok=True,
            good=good,
            title=title,
            score_line=score_line,
            meta_line=meta_line,
            hint=hint,
            error=None,
        )

    submit_btn = None
    if submitter is not None:
        submit_btn = widgets.Button(
            description="📤 Submit",
            tooltip="Submit to the autograder",
            layout=widgets.Layout(height="40px"),
        )
        submit_btn.add_class("sql-sol-toggle")    

    # Toolbar composition
    left_items = [run_btn]
    if hint_btn:
        left_items.append(hint_btn)

    left_items.append(revert_btn)
    if reset_btn:
        left_items.append(reset_btn)
    left_items.extend([clear_results_btn, clear_query_btn])
    if sol_btn:
        left_items.append(sol_btn)

    if submit_btn:
      left_items.append(submit_btn)

    left = widgets.HBox(left_items, layout=widgets.Layout(gap="8px", align_items="center"))
    right = widgets.HBox([score_widget, status],layout=widgets.Layout(
            justify_content="flex-end",
            align_items="center",
            gap="12px"
        )
    )

    toolbar = widgets.HBox(
        [left, right],
        layout=widgets.Layout(width="100%", align_items="center", justify_content="space-between")
    )
    toolbar.add_class("sql-toolbar")

    # ---------- database helpers ----------
    def _run_select(query: str) -> pd.DataFrame:
        if db_type == "sqlite":
            return pd.read_sql_query(query, conn)
        return conn.execute(query).df()
    
    def _run_script(query: str) -> None:
        if db_type == "sqlite":
            cur = conn.cursor()
            cur.executescript(query)
            conn.commit()
        else:
            conn.execute(query)

    def _list_tables() -> list[str]:
        if db_type == "sqlite":
            df = pd.read_sql_query(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
                """,
                conn
            )
            return df["name"].tolist()

        df = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ).df()
        return df["table_name"].tolist()        

    def _table_info(table_name: str) -> pd.DataFrame:
        if db_type == "sqlite":
            info = pd.read_sql_query(f"PRAGMA table_info('{table_name}');", conn)
            info = info[["name", "type", "notnull", "dflt_value", "pk"]]
            return info.rename(columns={
                "name": "attribute",
                "type": "datatype",
                "notnull": "not null",
                "dflt_value": "default value",
                "pk": "primary key"
            })

        info = conn.execute(f"DESCRIBE {table_name}").df()
        info = info.rename(columns={
            "column_name": "attribute",
            "column_type": "datatype",
            "null": "null_ok",
            "default": "default value",
            "key": "key",
        })

        if "attribute" not in info.columns:
            info["attribute"] = None
        if "datatype" not in info.columns:
            info["datatype"] = None
        if "default value" not in info.columns:
            info["default value"] = None
        if "null_ok" not in info.columns:
            info["null_ok"] = None
        if "key" not in info.columns:
            info["key"] = None

        info["not null"] = info["null_ok"].map(
            lambda x: "YES" if str(x).upper() == "NO" else ""
        )
        info["primary key"] = info["key"].map(
            lambda x: "YES" if str(x).upper() == "PRI" else ""
        )

        return info[["attribute", "datatype", "not null", "default value", "primary key"]]

    # ---------- schema renderer ----------
    def render_schema():
        with schema_out:
            clear_output()
            try:
                all_tables = _list_tables()

                if not all_tables:
                    display(HTML("<b>No tables found.</b>"))
                    return

                if schema_tables:
                    tables = [t for t in schema_tables if t in all_tables]
                    missing = [t for t in schema_tables if t not in all_tables]

                    if missing:
                        display(HTML(
                            "<div style='margin:6px 0 10px 0;color:#b00020'>"
                            f"<b>Note:</b> table(s) not found: {', '.join(_html.escape(x) for x in missing)}"
                            "</div>"
                        ))
                else:
                    tables = all_tables

                if not tables:
                    display(HTML("<b>No matching tables to display.</b>"))
                    return

                items = []
                titles = []

                for t in tables:
                    info = _table_info()

                    out = widgets.Output()
                    with out:
                        display(info.style.format(na_rep="NULL").hide(axis="index"))

                    items.append(out)
                    titles.append(t)

                acc = widgets.Accordion(children=items)
                for i, t in enumerate(titles):
                    acc.set_title(i, t)

                acc.selected_index = 0 if len(tables) == 1 else None
                display(acc)

            except Exception as e:
                display(HTML(f"<pre style='color:#b00020'>Error:\n{e}</pre>"))

    def on_tab_change(change):
        if change["name"] == "selected_index" and change["new"] == 1:
            render_schema()

    tabs.observe(on_tab_change)

    # ---------- actions ----------
    def run_query(_):
        nonlocal last_saved, latest_map

        q = box.value.strip()
        with results_out:
            clear_output()

            if not q:
                display(HTML("<b>Please type a query.</b>"))
                tabs.selected_index = 0
                set_status("No query to run.")
                return

            norm = lambda s: " ".join(s.split())
            changed = (norm(q) != norm(last_saved or ""))

            if (not dedupe) or changed:
                append_history(LOG_ALL_FILE, runner_id, q)
                latest_map = load_latest_map(LOG_LATEST_FILE)
                latest_map[runner_id] = q
                save_latest_map(LOG_LATEST_FILE, latest_map)
                last_saved = q

            if select_only and not q.lower().lstrip().startswith(("select", "with")):
                display(HTML("<b>Only SELECT/WITH queries are allowed.</b>"))
                tabs.selected_index = 0
                set_status("Blocked: only SELECT/WITH allowed.")
                return

            for b in (run_btn, revert_btn, clear_results_btn, clear_query_btn):
                b.disabled = True
            if reset_btn:
                reset_btn.disabled = True
            if hint_btn:
                hint_btn.disabled = True
            if sol_btn:
                sol_btn.disabled = True

            try:
                if q.lower().lstrip().startswith(("select", "with")):
                    df = _run_select(q)
                    display(df.style.format(na_rep="NULL").hide(axis="index"))
                    set_status(f"Returned {len(df)} row(s).")

                    if validator:
                        ok, problems = validator(q, df, conn)
                        show_validation(ok, problems)
                    else:
                        hide_validation()

                else:
                    _run_script(q)
                    display(HTML("<b>✅ Query executed.</b>"))
                    set_status("Query executed.")
                    hide_validation()

                tabs.selected_index = 0

            except Exception as e:
                display(HTML(f"<pre style='color:#b00020'>Error:\n{e}</pre>"))
                tabs.selected_index = 0
                set_status("Error running query.")
            finally:
                for b in (run_btn, revert_btn, clear_results_btn, clear_query_btn):
                    b.disabled = False
                if reset_btn:
                    reset_btn.disabled = False
                if hint_btn:
                    hint_btn.disabled = False
                if sol_btn:
                    sol_btn.disabled = False

    def revert_query(_):
        nonlocal last_saved
        latest_map_local = load_latest_map(LOG_LATEST_FILE)
        saved = latest_map_local.get(runner_id)
        box.value = saved if saved is not None else (default_sql or "")
        set_status("Reverted to last saved." if saved is not None else "No saved query — reverted.")

    def reset_to_default(_):
        if default_sql:
            box.value = default_sql
            set_status("Reset to default SQL.")

    def clear_results(_):
        results_out.clear_output()
        set_status("Cleared results output.")

    def clear_query(_):
        box.value = ""
        set_status("Cleared query editor.")

    def penalty_label_from_multiplier(mult: float) -> str:
        try:
            mult = float(mult)
        except Exception:
            return "Penalty: unknown"
        if mult >= 0.999:
            return "Penalty: none"
        pct = int(round((1.0 - mult) * 100))
        return f"Penalty: {pct}%"    

    def on_submit(_):
        if submitter is None:
            show_submit_result(ok=False, error="Submit is not configured for this notebook.")
            return
        q = box.value.strip()
        if not q:
            show_submit_result(ok=False, error="Please type a query first.")
            return

        if select_only and not q.lower().lstrip().startswith(("select", "with")):
            show_submit_result(ok=False, error="Only SELECT/WITH queries are allowed.")
            return

        # disable while submitting
        for b in (run_btn, revert_btn, clear_results_btn, clear_query_btn):
            b.disabled = True
        if reset_btn:
            reset_btn.disabled = True
        if hint_btn:
            hint_btn.disabled = True
        if sol_btn:
            sol_btn.disabled = True
        if submit_btn:
            submit_btn.disabled = True

        try:
            resp = submitter(runner_id, q)

            if not resp.get("ok", False):
                code = resp.get("error_code")
                msg  = resp.get("error_message") or resp.get("error") or "Submit failed."

                if code == "MAX_ATTEMPTS":
                    show_submit_result(ok=False, error=msg)  # or a nicer title too
                else:
                    show_submit_result(ok=False, error=msg)
                return
            else:
                mult = float(resp.get("multiplier", 1.0))
                show_submit_result(
                    ok=True,
                    final_points=resp.get("final_points"),
                    max_points=resp.get("max_points"),
                    attempt=resp.get("attempt"),
                    penalty_label=penalty_label_from_multiplier(mult),
                    hint=resp.get("hint"),
                )
                final_pts = resp.get("final_points")
                max_pts = resp.get("max_points")
                att = resp.get("attempt")

                _update_score_widget(current_points=final_pts, max_points=max_pts,attempt=att,)
            set_status("Submitted." if resp.get("ok", False) else "Submit failed.")
        except Exception as e:
            show_submit_result(ok=False, error=str(e))
            set_status("Submit error.")
        finally:
            for b in (run_btn, revert_btn, clear_results_btn, clear_query_btn):
                b.disabled = False
            if reset_btn:
                reset_btn.disabled = False
            if hint_btn:
                hint_btn.disabled = False
            if sol_btn:
                sol_btn.disabled = False
            if submit_btn:
                submit_btn.disabled = False    

    run_btn.on_click(run_query)
    revert_btn.on_click(revert_query)
    if reset_btn:
        reset_btn.on_click(reset_to_default)
    clear_results_btn.on_click(clear_results)
    clear_query_btn.on_click(clear_query)
   
    if submit_btn:
        submit_btn.on_click(on_submit)
    

    # ---------- layout ----------
    elements = []
    if desc_widget:
        elements.append(desc_widget)
    if hint_box:
        elements.append(hint_box)
    if sol_box:
        elements.append(sol_box)
    elements.append(validation_widget)
    if submitter is not None:
      elements.append(submit_widget)

    editor_panel = widgets.VBox([box, toolbar])
    editor_panel.add_class("sql-panel")

    spacer = widgets.Box(layout=widgets.Layout(height="10px"))

    tabs_panel = widgets.VBox([tabs])
    tabs_panel.add_class("sql-tabs-panel")
    tabs_panel.layout.height = "230px"

    elements.extend([editor_panel, spacer, tabs_panel])

    ui = widgets.VBox(elements, layout=widgets.Layout(width="100%"))
    ui.add_class("sql-runner")
    display(ui)

    render_schema()
    set_status(f"Ready ({db_type}).")
