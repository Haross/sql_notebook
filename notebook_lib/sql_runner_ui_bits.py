# notebook_lib/sql_runner_ui_bits.py
from __future__ import annotations
import html as _html
import random
from IPython.display import display, HTML

SUCCESS_MESSAGES = [
    "👏 Nice!", "💪 Great job", "👏 Good job", "👏 Keep up the good work!",
    "👏 I think you’re getting the hang of this!", "👏 Well played",
    "🌟 Fantastic! Let’s keep it going", "👏 Nicely done",
]

SQL_RUNNER_CSS  = r"""
    /* =========================================================
    SQL Runner — Theme-aware (Light + Dark)
    Works well in Colab/JupyterLab without fighting global CSS
    ========================================================= */

    /* -------------------------
    Theme tokens (Light default)
    ------------------------- */
    .sql-runner{
    --sr-bg:        transparent;     /* outer background */
    --sr-surface:   #ffffff;         /* cards/panels */
    --sr-surface2:  #f6f8fa;         /* headers/toolbars */
    --sr-border:    #d0d7de;
    --sr-border2:   #eaeef2;
    --sr-text:      #24292f;
    --sr-muted:     #57606a;
    --sr-accent:    #1a73e8;

    max-width: 100% !important;
    box-sizing: border-box !important;
    padding-right: 18px;   /* keep resize handle away from notebook scrollbar */
    padding-bottom: 12px;
    overflow-x: hidden;

    color: var(--sr-text) !important;
    }

/* Dark theme — follows Colab html[theme="dark"] */
html[theme="dark"] .sql-runner{
  --sr-surface:   #111418;
  --sr-surface2:  #161b22;
  --sr-border:    #2b313b;
  --sr-border2:   #222834;
  --sr-text:      #e6edf3;
  --sr-muted:     #9aa7b4;
  --sr-accent:    #4da3ff;
}


    /* Ensure inner widget containers don't exceed runner width */
    .sql-runner .widget-box,
    .sql-runner .widget-vbox,
    .sql-runner .widget-hbox{
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    }

    /* -------------------------
    Output containers: don’t force white slabs
    ------------------------- */
    .sql-runner .widget-output,
    .sql-runner .output,
    .sql-runner .output_area,
    .sql-runner .jp-OutputArea,
    .sql-runner .jp-OutputArea-output,
    .sql-runner .jp-RenderedHTMLCommon,
    .sql-runner .jp-OutputArea-child,
    .sql-runner .output_subarea,
    .sql-runner .output_html{
    background: transparent !important;
    color: var(--sr-text) !important;
    }

    /* -------------------------
    Description / Hint / Solution boxes
    ------------------------- */
    .sql-desc{
    border-left: 4px solid var(--sr-accent);
    background: var(--sr-surface2);
    color: var(--sr-text);
    padding: 10px 12px;
    margin: 6px 0 10px 0;
    border-radius: 6px;
    font-size: 14px;
    line-height: 1.5;
    }

    .sql-hintbox{
    border-left: 4px solid #fbbc04;
    background: var(--sr-surface2);
    color: var(--sr-text);
    padding: 10px 12px;
    margin: 8px 0 10px 0;
    border-radius: 6px;
    font-size: 14px;
    line-height: 1.5;
    }

    .sql-solbox{
    position: relative;
    border-left: 4px solid #2e7d32;
    background: var(--sr-surface2);
    color: var(--sr-text);
    padding: 10px 12px;
    margin: 8px 0 10px 0;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.5;
    }

    .sql-solbox pre{
    margin: 8px 0 0 0;
    padding: 10px;
    background: var(--sr-surface);
    color: var(--sr-text);
    border: 1px solid var(--sr-border);
    border-radius: 8px;
    overflow: auto;
    white-space: pre-wrap;
    }

    .sql-sol-close{
    padding: 0 !important;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
    color: var(--sr-text) !important;
    opacity: 0.65 !important;
    font-weight: 700 !important;
    }
    .sql-sol-close:hover{ opacity: 1 !important; }

    /* -------------------------
    Editor + toolbar panel
    ------------------------- */
    .sql-runner .sql-panel{
    border: 1px solid var(--sr-border);
    border-radius: 12px;
    background: var(--sr-surface2);
    overflow: hidden;
    }

    /* Textarea wrapper adapts to resized textarea */
    .sql-runner .widget-textarea{
      height: auto !important;
      padding-right: 2px !important;
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
    background: var(--sr-surface) !important;
    color: var(--sr-text) !important;
    caret-color: var(--sr-text) !important;

    border: 0 !important;          /* panel provides border */
    border-radius: 0 !important;
    padding: 12px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    font-size: 13px;
    line-height: 1.4;
    }
    .sql-runner .sql-editor textarea::placeholder{
    color: var(--sr-muted) !important;
    opacity: 1 !important;
    }

    /* Toolbar */
    .sql-runner .sql-toolbar{
    border-top: 1px solid var(--sr-border);
    background: var(--sr-surface2);
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
    color: var(--sr-text) !important;
    }

    .sql-runner .sql-toolbar .widget-button:hover{
    background: rgba(127,127,127,0.12) !important;
    border-color: var(--sr-border) !important;
    }

    /* Primary Run button */
    .sql-runner .sql-toolbar .widget-button.mod-primary{
    background: var(--sr-accent) !important;
    border-color: var(--sr-accent) !important;
    color: #ffffff !important;
    }
    .sql-runner .sql-toolbar .widget-button.mod-primary:hover{
    filter: brightness(0.95);
    }

    .sql-runner .sql-toolbar .hint{
    color: var(--sr-muted);
    font-size: 12px;
    margin-left: 12px;
    }

    /* Solution toggle button (pill) */
    .sql-runner .sql-toolbar .widget-button.sql-sol-toggle{
    width: auto !important;
    min-width: unset !important;
    padding: 0 14px !important;
    border-radius: 999px !important;
    font-size: 12px !important;
    }

    .sql-sol-toggle{
    padding: 0 10px !important;
    font-size: 12px !important;
    border-radius: 999px !important;
    background: var(--sr-surface) !important;
    border: 1px dashed #2e7d32 !important;
    color: #2e7d32 !important;
    font-weight: 500 !important;
    }
    .sql-sol-toggle:hover{ background: rgba(46,125,50,0.10) !important; }

    /* -------------------------
    Tabs results panel (dock)
    ------------------------- */
    .sql-runner .sql-tabs-panel{
    border: 1px solid var(--sr-border);
    border-radius: 10px;
    background: var(--sr-surface);
    overflow: hidden;

    resize: vertical;
    min-height: 220px;
    }

    /* Let outer panel own the border */
    .sql-runner .sql-tabs-panel .widget-tab{
    border: 0 !important;
    background: transparent !important;

    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    }

    /* Remove focus rings */
    .sql-runner .widget-tab:focus,
    .sql-runner .widget-tab :focus{
    outline: none !important;
    box-shadow: none !important;
    }

    /* Tab bar */
    .sql-runner .widget-tab > .p-TabBar{
    flex: 0 0 auto !important;
    background: var(--sr-surface2) !important;
    border-bottom: 1px solid var(--sr-border) !important;
    padding: 0 6px !important;
    }

    /* Tabs */
    .sql-runner .p-TabBar-tab{
    margin: 0 6px 0 0 !important;
    padding: 6px 12px !important;
    font-size: 13px !important;
    line-height: 18px !important;
    color: var(--sr-muted) !important;

    background: transparent !important;
    border: 1px solid transparent !important;
    border-bottom: 0 !important;
    border-radius: 8px 8px 0 0 !important;

    position: relative;
    }

    .sql-runner .p-TabBar-tab:hover{
    background: rgba(127,127,127,0.12) !important;
    border-color: var(--sr-border) !important;
    }

    /* Active tab */
    .sql-runner .p-TabBar-tab.p-mod-current{
    background: var(--sr-surface) !important;
    color: var(--sr-text) !important;
    border-color: var(--sr-border) !important;
    border-bottom: 1px solid var(--sr-surface) !important;
    font-weight: 500 !important;
    z-index: 2;

    box-shadow: none !important;
    background-image: none !important;
    }

    /* Remove any Lumino underline */
    .sql-runner .p-TabBar-tab.p-mod-current::before{
    content: none !important;
    display: none !important;
    }

    /* Accent indicator inside the tab */
    .sql-runner .p-TabBar-tab.p-mod-current::after{
    content: "";
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: 4px;
    height: 2px;
    background: var(--sr-accent);
    border-radius: 2px;
    }

    /* Tab content */
    .sql-runner .widget-tab > .p-TabPanel{
    flex: 1 1 auto !important;
    overflow: auto !important;
    min-height: 140px;
    box-sizing: border-box !important;

    padding: 10px !important;
    background: var(--sr-surface) !important;
    color: var(--sr-text) !important;
    }

    /* Remove Lumino inner divider */
    .sql-runner .sql-tabs-panel .widget-tab-contents,
    .sql-runner .sql-tabs-panel .p-TabPanel-tabContents{
    border: 0 !important;
    box-shadow: none !important;
    outline: none !important;
    background: transparent !important;
    }

    /* -------------------------
    Accordion (Schema) header styling
    ------------------------- */
    .sql-runner .p-Accordion .p-Collapse-header{
    background: var(--sr-surface2) !important;
    border: 1px solid var(--sr-border) !important;
    border-radius: 8px !important;
    }
    .sql-runner .p-Accordion .p-Collapse-header i,
    .sql-runner .p-Accordion .p-Collapse-header span{
    color: var(--sr-text) !important;
    }
    .sql-runner .p-Accordion .p-Collapse-contents{
    background: var(--sr-surface) !important;
    border: 1px solid var(--sr-border) !important;
    border-top: 0 !important;
    border-radius: 0 0 8px 8px !important;
    }
    .sql-runner .p-Accordion .p-Collapse-header:hover{
    background: rgba(127,127,127,0.12) !important;
    }

    /* -------------------------
    Pandas Styler tables (results + schema)
    ------------------------- */
    .sql-runner table.dataframe,
    .sql-runner .output table,
    .sql-runner .jp-RenderedHTMLCommon table{
    background: var(--sr-surface) !important;
    color: var(--sr-text) !important;
    border-collapse: collapse !important;
    }

    /* Header cells */
    .sql-runner table.dataframe thead th,
    .sql-runner .output thead th,
    .sql-runner .jp-RenderedHTMLCommon thead th{
    background: var(--sr-surface2) !important;
    color: var(--sr-text) !important;
    border: 1px solid var(--sr-border) !important;
    padding: 6px 12px !important;
    text-align: left !important;
    }

    /* Body cells */
    .sql-runner table.dataframe tbody td,
    .sql-runner .output tbody td,
    .sql-runner .jp-RenderedHTMLCommon tbody td{
    background: var(--sr-surface) !important;
    color: var(--sr-text) !important;
    border: 1px solid var(--sr-border2) !important;
    padding: 6px 12px !important;
    text-align: left !important;
    }

    /* Make table size to content without forcing full width */
    .sql-runner table.dataframe{
    width: auto !important;
    max-width: 100% !important;
    table-layout: fixed !important;

    display: inline-block !important;
    overflow-x: auto !important;
    vertical-align: top;
    }

    /* Preserve whitespace for teaching (leading + multiple spaces) */
    .sql-runner table.dataframe th,
    .sql-runner table.dataframe td{
    white-space: pre-wrap !important;    /* preserves spaces + wraps */
    overflow-wrap: anywhere !important;  /* prevents overflow on long tokens */
    word-break: break-word !important;
    }

    /* If you truly want to show leading spaces, switch to pre:
    BUT this can make tables look weird with accidental spacing.
    Uncomment only if needed.
    */
    /*
    .sql-runner table.dataframe td{
    white-space: pre !important;
    }
    */

    /* -------------------------
    Validation box
    ------------------------- */
    .sql-validation{
    position: relative;
    padding: 10px 38px 10px 12px;
    margin: 8px 0 10px 0;
    border-radius: 6px;
    font-size: 14px;
    line-height: 1.5;
    color: var(--sr-text);
    }
    .sql-validation.ok{
    border-left: 4px solid #2e7d32;
    background: rgba(46,125,50,0.14);
    }
    .sql-validation.err{
    border-left: 4px solid #b00020;
    background: rgba(176,0,32,0.14);
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
    .sql-validation .close:hover{ opacity: 1; }
    .sql-validation ul{ margin: 6px 0 0 18px; }


.sql-submit{
  position: relative;
  padding: 10px 38px 10px 12px;
  margin: 8px 0 10px 0;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--sr-text);
  border-left: 4px solid var(--sr-border);
  background: var(--sr-surface2);
}

.sql-submit.good{
  border-left-color: #2e7d32;
  background: rgba(46,125,50,0.14);
}

.sql-submit.warn{
  border-left-color: #f9ab00;
  background: rgba(249,171,0,0.14);
}

.sql-submit.bad{
  border-left-color: #b00020;
  background: rgba(176,0,32,0.14);
}

.sql-submit .close{
  position: absolute;
  top: 8px;
  right: 10px;
  cursor: pointer;
  user-select: none;
  opacity: 0.65;
  font-weight: 700;
}
.sql-submit .close:hover{ opacity: 1; }

.sql-submit .meta{
  color: var(--sr-muted);
  font-size: 12px;
  margin-top: 4px;
}

.sql-submit .hint{
  margin-top: 6px;
}


.score {
  font-size: 13px;
  opacity: 0.9;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(0,0,0,0.15);
}
.score.muted { opacity: 0.6; }
"""


def inject_css_once(css: str = SQL_RUNNER_CSS, style_id: str = "sql-runner-css") -> None:
    """
    Colab sometimes drops <style> that are emitted into an output area.
    So we inject into document.head via JS (persisting across cells).
    """
    js = f"""
    <script>
    (function() {{
      const id = {style_id!r};
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

def md_to_html(md: str) -> str:
    try:
        import markdown as _md
        return _md.markdown(md)
    except Exception:
        return "<br>".join(_html.escape(md).splitlines())    
    
def pick_success_title() -> str:
    return random.choice(SUCCESS_MESSAGES)    

def render_score_badge(current_points=None, max_points=None, attempt=None) -> str:
    if current_points is None:
        return "<span class='score muted'>Points: —</span>"

    parts = []
    parts.append(
        f"Points: <b>{current_points}</b>"
        + (f" / {max_points}" if max_points is not None else "")
    )

    if attempt is not None:
        parts.append(f"Attempts: {attempt}")

    return "<span class='score'>" + " &nbsp;|&nbsp; ".join(parts) + "</span>"

def render_validation_banner(ok: bool, title: str, message: str, box_id: str) -> str:
    cls = "ok" if ok else "err"

    return f"""
      <div id="{box_id}" class="sql-validation {cls}">
        <div class="close" onclick="document.getElementById('{box_id}').remove()">✕</div>
        <b>{_html.escape(title)}</b>
        {_html.escape(message)}
      </div>
    """

def render_submit_banner(
    *,
    box_id: str,
    ok: bool,
    good: bool,
    title: str,
    score_line: str = "",
    meta_line: str = "",
    hint: str | None = None,
    error: str | None = None,
) -> str:
    """
    Returns the HTML for the submission result banner.

    ok=False => 'bad' banner using error
    ok=True  => 'good' if good==True else 'warn'
    """

    if not ok:
        body = _html.escape(error or "Something went wrong.")
        return f"""
          <div id="{box_id}" class="sql-submit bad">
            <div class="close" onclick="document.getElementById('{box_id}').remove()">✕</div>
            <b>{_html.escape(title)}</b><br/>
            {body}
          </div>
        """

    cls = "good" if good else "warn"

    hint_html = ""
    if hint:
        hint_html = f"<div class='hint'><b>Next hint:</b> {_html.escape(hint)}</div>"

    # score_line is expected to be safe HTML you created (numbers + tags),
    # meta_line is plain text or already escaped before passing in
    return f"""
      <div id="{box_id}" class="sql-submit {cls}">
        <div class="close" onclick="document.getElementById('{box_id}').remove()">✕</div>
        <b>{_html.escape(title)}</b><br/>
        {score_line}
        <div class="meta">{meta_line}</div>
        {hint_html}
      </div>
    """