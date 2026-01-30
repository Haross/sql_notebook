# notebook_lib/sql_runner.py
from __future__ import annotations

import csv
import html as _html
import random
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple, Union, List, Any

import pandas as pd
import ipywidgets as widgets
from IPython.display import display, clear_output, HTML

# -------------------------------------------------------------------
# Small constants missing in the notebook snippet
# -------------------------------------------------------------------
SUCCESS_MESSAGES = [
    "👏 Nice!",
    "💪 Great job",
    "👏 Good job",
    "👏 Keep up the good work!",
    "👏 I think you’re getting the hang of this!",
    "👏 Well played",
    "🌟 Fantastic! Let’s keep it going",
    "👏 Nicely done",
]

def _inject_css_once(css: str) -> None:
    """
    Colab sometimes drops <style> that are emitted into an output area.
    So we inject into document.head via JS (persisting across cells).
    """
    js = f"""
    <script>
    (function() {{
      const id = "sql-runner-css";
      if (document.getElementById(id)) return;
      const style = document.createElement("style");
      style.id = id;
      style.type = "text/css";
      style.appendChild(document.createTextNode({css!r}));
      document.head.appendChild(style);
    }})();
    </script>
    """
    display(HTML(js))


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
):
    # ---------- helpers ----------
    def md_to_html(md: str) -> str:
        try:
            import markdown as _md
            return _md.markdown(md)
        except Exception:
            return "<br>".join(_html.escape(md).splitlines())

    # ---------- persistence ----------
    LOG_ALL_FILE = Path("sql_query_log.csv")
    LOG_LATEST_FILE = Path("sql_query_latest.csv")

    def _append_history(runner_id: str, sql: str, log_path: Path = LOG_ALL_FILE):
        is_new = not log_path.exists()
        with log_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["ts", "runner_id", "sql"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), runner_id, sql])

    def _load_latest_map(latest_path: Path = LOG_LATEST_FILE) -> dict:
        if not latest_path.exists():
            return {}
        latest = {}
        with latest_path.open("r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                latest[row["runner_id"]] = row["sql"]
        return latest

    def _save_latest_map(latest: dict, latest_path: Path = LOG_LATEST_FILE):
        with latest_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["runner_id", "sql"])
            for rid, sql in latest.items():
                w.writerow([rid, sql])

    latest_map = _load_latest_map()
    last_saved = latest_map.get(runner_id)
    initial_sql = last_saved if last_saved is not None else (default_sql or "")

    # ---------- UI chrome (CSS) ----------
    CSS = r"""
/* =========================
          Dark-theme safety (Colab): keep runner readable
          ========================= */
        .sql-runner, .sql-runner *{
          color: #24292f !important;
        }

        /* Textarea: force readable text + placeholder */
        .sql-runner .sql-editor textarea{
          background: #ffffff !important;
          color: #24292f !important;
          caret-color: #24292f !important;
        }
        .sql-runner .sql-editor textarea::placeholder{
          color: #57606a !important;
          opacity: 1 !important;
        }

        /* Output containers: prevent dark blocks behind content (esp. schema accordion) */
        .sql-runner .widget-output,
        .sql-runner .output,
        .sql-runner .output_area,
        .sql-runner .jp-OutputArea,
        .sql-runner .jp-OutputArea-output,
        .sql-runner .jp-RenderedHTMLCommon,
        .sql-runner .jp-OutputArea-child,
        .sql-runner .output_subarea,
        .sql-runner .output_html{
          background: #ffffff !important;
        }

        /* =========================
          Fix pandas Styler tables in Colab dark theme
          ========================= */
        .sql-runner table.dataframe,
        .sql-runner .output table,
        .sql-runner .jp-RenderedHTMLCommon table{
          background: #ffffff !important;
          color: #24292f !important;
          border-collapse: collapse !important;
        }

        .sql-runner table.dataframe thead th,
        .sql-runner .output thead th,
        .sql-runner .jp-RenderedHTMLCommon thead th{
          background: #f6f8fa !important;
          color: #24292f !important;
          border: 1px solid #d0d7de !important;
        }

        .sql-runner table.dataframe tbody td,
        .sql-runner .output tbody td,
        .sql-runner .jp-RenderedHTMLCommon tbody td{
          background: #ffffff !important;
          color: #24292f !important;
          border: 1px solid #eaeef2 !important;
        }

        /* kill dark zebra striping some themes apply */
        .sql-runner table.dataframe tbody tr:nth-child(even) td,
        .sql-runner .output tbody tr:nth-child(even) td,
        .sql-runner .jp-RenderedHTMLCommon tbody tr:nth-child(even) td{
          background: #ffffff !important;
        }

        /* =========================
          Accordion (Schema) header styling
          ========================= */
        .sql-runner .p-Accordion .p-Collapse-header{
          background: #f6f8fa !important;
          border: 1px solid #d0d7de !important;
          border-radius: 8px !important;
        }
        .sql-runner .p-Accordion .p-Collapse-header i,
        .sql-runner .p-Accordion .p-Collapse-header span{
          color: #24292f !important;
        }
        .sql-runner .p-Accordion .p-Collapse-contents{
          background: #ffffff !important;
          border: 1px solid #d0d7de !important;
          border-top: 0 !important;
          border-radius: 0 0 8px 8px !important;
        }
        .sql-runner .p-Accordion .p-Collapse-header:hover{
          background: #eaeef2 !important;
        }

        /* =========================
        DataFrame sizing + no overlap (no full-width stretch)
        ========================= */

        /* Let the table size to its content, but don't exceed container */
        .sql-runner table.dataframe{
        width: auto !important;
        max-width: 100% !important;

        /* Keep column widths stable so overflow is handled per-cell */
        table-layout: fixed !important;

        /* Important when using width:auto + fixed layout */
        display: inline-block !important;
        overflow-x: auto !important;   /* if it still gets too wide, allow scroll */
        vertical-align: top;
        }

        /* Stop text painting over other columns */
        .sql-runner table.dataframe th,
        .sql-runner table.dataframe td{
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
        }

        /* Fix "everything is right aligned" coming from notebook theme CSS */
        .sql-runner table.dataframe th,
        .sql-runner table.dataframe td{
        text-align: left !important;
        }

        .sql-runner table.dataframe th{ text-align:left !important; }

        .sql-runner table.dataframe td{
        white-space: pre !important;
        }




        /* =========================
          Global runner bounds
          ========================= */
        .sql-runner{
          max-width: 100% !important;
          box-sizing: border-box !important;
          padding-right: 18px;   /* keep resize handle away from notebook scrollbar */
          padding-bottom: 12px;
          overflow-x: hidden;
        }

        .sql-runner .widget-box,
        .sql-runner .widget-vbox,
        .sql-runner .widget-hbox{
          width: 100% !important;
          max-width: 100% !important;
          box-sizing: border-box !important;
        }

        /* =========================
          Description / Hint boxes
          ========================= */
        .sql-desc{
          border-left: 4px solid #1a73e8;
          background: #f5f9ff;
          padding: 10px 12px;
          margin: 6px 0 10px 0;
          border-radius: 6px;
          font-size: 14px;
          line-height: 1.5;
        }
        .sql-hintbox{
          border-left: 4px solid #fbbc04;
          background: #fff8e1;
          padding: 10px 12px;
          margin: 8px 0 10px 0;
          border-radius: 6px;
          font-size: 14px;
          line-height: 1.5;
        }

        /* =========================
          Solution box
          ========================= */
        .sql-solbox{
          position: relative;
          border-left: 4px solid #2e7d32;
          background: #e8f5e9;
          padding: 10px 12px;
          margin: 8px 0 10px 0;
          border-radius: 6px;
          font-size: 13px;
          line-height: 1.5;
        }
        .sql-solbox pre{
          margin: 8px 0 0 0;
          padding: 10px;
          background: #ffffff;
          border: 1px solid #d0d7de;
          border-radius: 8px;
          overflow: auto;
          white-space: pre-wrap;
        }

        .sql-sol-close{
          padding: 0 !important;
          border: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
          color: #24292f !important;
          opacity: 0.65 !important;
          font-weight: 700 !important;
        }

        .sql-sol-close:hover{
          opacity: 1 !important;
          background: transparent !important;
        }



        /* =========================
          Editor + toolbar panel
          ========================= */
        .sql-runner .sql-panel{
          border: 1px solid #d0d7de;
          border-radius: 12px;
          background: #f6f8fa;
          overflow: hidden;
        }

        /* Textarea wrapper adapts to resized textarea */
        .sql-runner .widget-textarea{
          height: auto !important;
        }

        /* Base textarea behavior (resizable) */
        .sql-runner .widget-textarea textarea{
          height: 95px;                 /* initial size */
          min-height: 120px !important;
          resize: vertical !important;
          width: 100% !important;
          max-width: 100% !important;
          box-sizing: border-box !important;
        }

        /* Editor look */
        .sql-runner .sql-editor textarea{
          background: #ffffff;
          border: 0 !important;          /* panel provides border */
          border-radius: 0 !important;
          padding: 12px !important;
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 13px;
          line-height: 1.4;
        }

        /* Toolbar */
        .sql-runner .sql-toolbar{
          border-top: 1px solid #d0d7de;
          background: #f6f8fa;
          margin: 0 !important;
          padding: 6px 10px !important;
        }

        .sql-runner .sql-toolbar .widget-button{
          min-width: 40px !important;
          width: 40px !important;
          height: 40px !important;
          border-radius: 8px !important;
          font-size: 18px !important;

          background: transparent !important;
          border: 1px solid transparent !important;
          box-shadow: none !important;
          color: #24292f !important;
        }
        /* Override the square toolbar button sizing for the solution toggle */
        .sql-runner .sql-toolbar .widget-button.sql-sol-toggle{
          width: auto !important;
          min-width: unset !important;
          padding: 0 14px !important;
          border-radius: 999px !important;
          font-size: 12px !important;
        }
        .sql-runner .sql-toolbar .widget-button:hover{
          background: #eaeef2 !important;
          border-color: #d0d7de !important;
        }
        .sql-runner .sql-toolbar .widget-button.mod-primary{
          background: #1a73e8 !important;
          border-color: #1a73e8 !important;
          color: #ffffff !important;
        }
        .sql-runner .sql-toolbar .widget-button.mod-primary:hover{
          filter: brightness(0.95);
        }

        .sql-runner .sql-toolbar .hint{
          color: #57606a;
          font-size: 12px;
          margin-left: 12px;
        }

        .sql-sol-toggle{
          padding: 0 10px !important;
          font-size: 12px !important;
          border-radius: 999px !important;
          background: #ffffff !important;
          border: 1px dashed #2e7d32 !important;
          color: #2e7d32 !important;
          font-weight: 500 !important;
        }

        .sql-sol-toggle:hover{
          background: #e8f5e9 !important;
        }

        /* =========================
          Tabs results panel (dock)
          ========================= */

        .sql-runner .sql-tabs-panel{
          border: 1px solid #d0d7de;
          border-radius: 10px;
          background: #ffffff;
          overflow: hidden;
        }

        /* Remove default focus rings */
        .sql-runner .widget-tab:focus,
        .sql-runner .widget-tab :focus{
          outline: none !important;
          box-shadow: none !important;
        }

        /* Let outer panel own the border */
        .sql-runner .sql-tabs-panel .widget-tab{
          border: 0 !important;
          background: transparent !important;
        }

        /* Tab bar */
        .sql-runner .widget-tab > .p-TabBar{
          background: #f6f8fa !important;
          border-bottom: 1px solid #d0d7de !important;
          padding: 0 6px !important;
        }

        /* Tabs */
        .sql-runner .p-TabBar-tab{
          margin: 0 6px 0 0 !important;
          padding: 6px 12px !important;
          font-size: 13px !important;
          line-height: 18px !important;
          color: #57606a !important;

          background: transparent !important;
          border: 1px solid transparent !important;
          border-bottom: 0 !important;
          border-radius: 8px 8px 0 0 !important;

          position: relative; /* for ::after indicator */
        }

        .sql-runner .p-TabBar-tab:hover{
          background: #eaeef2 !important;
          border-color: #d0d7de !important;
        }

        /* Active tab */
        .sql-runner .p-TabBar-tab.p-mod-current{
          background: #ffffff !important;
          color: #24292f !important;
          border-color: #d0d7de !important;
          border-bottom: 1px solid #ffffff !important; /* merges into content */
          font-weight: 500 !important;
          z-index: 2;
        }

        /* Blue indicator INSIDE the tab (prevents "blue line below") */
        .sql-runner .p-TabBar-tab.p-mod-current::after{
          content: "";
          position: absolute;
          left: 12px;
          right: 12px;
          bottom: 4px;      /* <-- inside the tab; NOT -1px */
          height: 2px;
          background: #1a73e8;
          border-radius: 2px;
        }

        /* Tab content */
        .sql-runner .widget-tab > .p-TabPanel{
          padding: 10px !important;
          background: #ffffff !important;
        }


        /* --- HARD OVERRIDES: remove Lumino/Colab active-tab blue indicator --- */
        .sql-runner .p-TabBar-tab.p-mod-current{
          box-shadow: none !important;      /* Lumino often draws the blue line here */
          background-image: none !important;
        }

        /* Some themes use ::before as the underline */
        .sql-runner .p-TabBar-tab.p-mod-current::before{
          content: none !important;
          display: none !important;
        }

        /* Some themes apply focus-visible outline/underline */
        .sql-runner .p-TabBar-tab:focus-visible,
        .sql-runner .p-TabBar-tab.p-mod-current:focus-visible{
          outline: none !important;
          box-shadow: none !important;
        }



        /* =========================
          Remove Lumino inner divider inside tab contents
          ========================= */
        .sql-runner .sql-tabs-panel .widget-tab-contents,
        .sql-runner .sql-tabs-panel .p-TabPanel-tabContents{
          border: 0 !important;
          box-shadow: none !important;
          outline: none !important;
          background: transparent !important;
        }





        /* =========================
          Resizable tabs container (stable)
          ========================= */

        /* Make the OUTER bordered panel resizable */
        .sql-runner .sql-tabs-panel{
          resize: vertical;
          overflow: hidden;          /* important: prevents the tab bar from getting clipped/overlapped */
          min-height: 220px;         /* prevents collapsing into the tabs */
        }

        /* Force the Tab widget to use a vertical flex layout */
        .sql-runner .sql-tabs-panel .widget-tab{
          height: 100% !important;
          display: flex !important;
          flex-direction: column !important;
        }

        /* Tab bar stays fixed at top */
        .sql-runner .sql-tabs-panel .widget-tab > .p-TabBar{
          flex: 0 0 auto !important;
        }

        /* Tab content area becomes the flexible, scrollable region */
        .sql-runner .sql-tabs-panel .widget-tab > .p-TabPanel{
          flex: 1 1 auto !important;
          overflow: auto !important;
          min-height: 140px;         /* keeps content area usable even when resized smaller */
          box-sizing: border-box !important;
        }

        /* =========================
          Validation box
          ========================= */
        .sql-validation{
          position: relative;
          padding: 10px 38px 10px 12px; /* extra right padding for ✕ */
          margin: 8px 0 10px 0;
          border-radius: 6px;
          font-size: 14px;
          line-height: 1.5;
        }
        .sql-validation.ok{
          border-left: 4px solid #2e7d32;
          background: #e8f5e9;
        }
        .sql-validation.err{
          border-left: 4px solid #b00020;
          background: #ffebee;
        }
        .sql-validation .close{
          position: absolute;
          top: 8px;
          right: 10px;
          cursor: pointer;
          user-select: none;
          opacity: 0.65;
          font-weight: 700;
        }
        .sql-validation .close:hover{
          opacity: 1;
        }
        .sql-validation ul{
          margin: 6px 0 0 18px;
        }
    """
    _inject_css_once(CSS)

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
            problems = [problems_or_msg] if problems_or_msg else []
        else:
            problems = list(problems_or_msg or [])

        cls = "ok" if ok else "err"

        if ok:
            title = random.choice(SUCCESS_MESSAGES)
            message = ""
        else:
            title = "🙁 Not correct yet"
            message = " ".join(problems)

        box_id = f"val_{runner_id}_{validation_nonce}"

        validation_widget.value = f"""
          <div id="{box_id}" class="sql-validation {cls}">
            <div class="close" onclick="document.getElementById('{box_id}').remove()">✕</div>
            <b>{_html.escape(title)}</b>
            { _html.escape(message) }
          </div>
        """

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

    left = widgets.HBox(left_items, layout=widgets.Layout(gap="8px", align_items="center"))
    right = widgets.HBox([status], layout=widgets.Layout(justify_content="flex-end", align_items="center"))

    toolbar = widgets.HBox(
        [left, right],
        layout=widgets.Layout(width="100%", align_items="center", justify_content="space-between")
    )
    toolbar.add_class("sql-toolbar")

    # ---------- schema renderer ----------
    def render_schema():
        with schema_out:
            clear_output()
            try:
                all_tables = pd.read_sql_query(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name;
                    """,
                    conn
                )["name"].tolist()

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
                    info = pd.read_sql_query(f"PRAGMA table_info('{t}');", conn)
                    info = info[["name", "type", "notnull", "dflt_value", "pk"]]
                    info = info.rename(columns={
                            "name": "attribute",
                            "type": "datatype",
                            "notnull": "not null",
                            "dflt_value": "default value",
                            "pk": "primary key"
                        })

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
                _append_history(runner_id, q)
                latest_map = _load_latest_map()
                latest_map[runner_id] = q
                _save_latest_map(latest_map)
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
                    df = pd.read_sql_query(q, conn)
                    display(df.style.format(na_rep="NULL").hide(axis="index"))
                    set_status(f"Returned {len(df)} row(s).")

                    if validator:
                        # ✅ New consistent signature:
                        ok, problems = validator(q, df, conn)
                        show_validation(ok, problems)
                    else:
                        hide_validation()

                else:
                    cur = conn.cursor()
                    cur.executescript(q)
                    conn.commit()
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
        latest_map_local = _load_latest_map()
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

    run_btn.on_click(run_query)
    revert_btn.on_click(revert_query)
    if reset_btn:
        reset_btn.on_click(reset_to_default)
    clear_results_btn.on_click(clear_results)
    clear_query_btn.on_click(clear_query)

    # ---------- layout ----------
    elements = []
    if desc_widget:
        elements.append(desc_widget)
    if hint_box:
        elements.append(hint_box)
    if sol_box:
        elements.append(sol_box)
    elements.append(validation_widget)

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
    set_status("Ready.")
