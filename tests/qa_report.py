"""A short HTML report in the same shape as the Fortender QA checks panel."""

from datetime import datetime
from html import escape
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "playwright-report" / "index.html"

CHECKS = {
    "test_01_invoice_list_loads": ("01  Invoice list loads", "/invoices"),
    "test_02_every_row_has_a_known_status": ("02  Every invoice has a known status", "/invoices"),
    "test_03_unpaid_filter_shows_only_unpaid": ("03  Unpaid filter shows only unpaid invoices", "/invoices?status=Unpaid"),
    "test_04_search_finds_one_invoice_by_number": ("04  Search finds one invoice by number", "/invoices"),
    "test_05_dubai_filter_shows_only_dubai": ("05  Dubai filter shows only Dubai", "/invoices?city=Dubai"),
    "test_06_clear_removes_the_filters": ("06  Clear removes the filters", "/invoices"),
    "test_07_detail_balance_is_total_minus_paid": ("07  Balance is total minus amount paid", "/invoices"),
    "test_08_query_checks_match_the_screens": ("08  Query checks match the screens", "/queries"),
    "test_09_new_invoice_form_marks_required_fields": ("09  New invoice marks required fields", "/invoices/new"),
    "test_10_due_date_before_issue_date_is_refused": ("10  Due date before the issue date is refused", "/invoices/new"),
    "test_11_amount_paid_above_the_total_is_refused": ("11  Amount paid above the total is refused", "/invoices/new"),
    "test_12_saved_customer_fills_name_and_email": ("12  Saved customer fills name and email", "/invoices/new"),
    "test_13_live_total_is_quantity_times_price": ("13  Live total is quantity times price", "/invoices/new"),
    "test_14_dismissing_delete_keeps_the_invoice": ("14  Dismissing delete keeps the invoice", "/invoices"),
    "test_15_city_and_status_filters_apply_together": ("15  City and status filters apply together", "/invoices?city=Dubai&status=Overdue"),
}


def label_for(nodeid: str) -> tuple[str, str]:
    for key, value in CHECKS.items():
        if key in nodeid:
            return value
    short = nodeid.split("::")[-1].replace("[chromium]", "")
    return short, ""


def clock(seconds: float) -> str:
    if seconds < 1:
        return f"{round(seconds * 1000)} ms"
    return f"{seconds:.1f}s"


def write(rows: list[dict]) -> None:
    passed = sum(1 for row in rows if row["result"] == "Pass")
    failed = sum(1 for row in rows if row["result"] == "Fail")
    skipped = sum(1 for row in rows if row["result"] == "Skipped")
    total = sum(row["seconds"] for row in rows)
    status = "Passed" if failed == 0 and rows else "Failed"
    when = datetime.now().strftime("%d %b %Y, %H:%M")
    body = "\n".join(_row(row) for row in rows)
    html = PAGE.format(
        status=status,
        pill=status.lower(),
        when=escape(when),
        passed=passed,
        failed=failed,
        skipped=skipped,
        duration=escape(clock(total)),
        rows=body,
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(html, encoding="utf-8")
    print(f"Report: {REPORT}")


def _row(row: dict) -> str:
    kind = row["result"].lower()
    detail = f'<div class="detail">{escape(row["detail"])}</div>' if row["detail"] else ""
    return (
        f'<tr class="{kind}" data-result="{kind}">'
        f'<td>{escape(row["check"])}{detail}</td>'
        f'<td class="page">{escape(row["page"])}</td>'
        f'<td class="fit"><span class="tag {kind}">{escape(row["result"])}</span></td>'
        f'<td class="fit time">{escape(row["time"])}</td>'
        f"</tr>"
    )


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Invoice Tracker QA</title>
  <style>
    :root {{
      --ink: #1c2430;
      --muted: #667085;
      --line: #e7e2d8;
      --paper: #f6f3ee;
      --card: #fffcf8;
      --navy: #1b2a4a;
      --pass: #1f7a4d;
      --pass-soft: #e7f5ee;
      --fail: #a33b32;
      --fail-soft: #fdecea;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font: 15px/1.5 "Segoe UI", sans-serif; color: var(--ink); background: var(--paper); }}
    header, main {{ width: min(980px, calc(100% - 40px)); margin: 0 auto; }}
    header {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 28px 0 8px; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .mark {{ width: 36px; height: 36px; border-radius: 10px; background: var(--navy); display: grid; place-items: center; }}
    h1 {{ margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.02em; }}
    .sub {{ margin: 2px 0 0; color: var(--muted); font-size: 13px; }}
    .pill {{ display: flex; align-items: center; gap: 8px; border-radius: 999px; padding: 8px 12px; background: white; border: 1px solid var(--line); font-size: 13px; font-weight: 600; }}
    .pill.passed {{ background: var(--pass-soft); border-color: #c9e8d6; color: var(--pass); }}
    .pill.failed {{ background: var(--fail-soft); border-color: #f3c7c3; color: var(--fail); }}
    .dot {{ width: 8px; height: 8px; border-radius: 50%; background: currentColor; }}
    main {{ padding-bottom: 48px; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 18px; }}
    .stat {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }}
    .stat span {{ display: block; color: var(--muted); font-size: 12px; }}
    .stat strong {{ display: block; margin-top: 4px; font-size: 26px; letter-spacing: -0.03em; }}
    .stat.pass strong {{ color: var(--pass); }}
    .stat.fail strong {{ color: var(--fail); }}
    .panel {{ margin-top: 12px; background: var(--card); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }}
    .toolbar {{ display: flex; gap: 8px; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--line); }}
    .toolbar h2 {{ margin: 0; font-size: 13px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); font-weight: 600; }}
    input[type="search"] {{ margin-left: auto; width: 220px; border: 1px solid var(--line); background: white; border-radius: 8px; padding: 8px 10px; font: inherit; }}
    .filters {{ display: flex; gap: 6px; }}
    .filters button {{ border: 1px solid var(--line); background: white; border-radius: 999px; padding: 6px 10px; font: inherit; font-size: 12px; cursor: pointer; }}
    .filters button.on {{ background: var(--navy); color: white; border-color: var(--navy); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 16px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ color: var(--muted); font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase; font-weight: 600; }}
    tr:last-child td {{ border-bottom: 0; }}
    tr.fail {{ background: #fff7f6; }}
    tr.fail td:first-child {{ box-shadow: inset 3px 0 0 var(--fail); }}
    .page, .time {{ color: var(--muted); }}
    .time {{ text-align: right; }}
    th.time {{ text-align: right; }}
    .fit {{ white-space: nowrap; width: 1%; }}
    .tag {{ font-weight: 700; font-size: 12px; }}
    .tag.pass {{ color: var(--pass); }}
    .tag.fail {{ color: var(--fail); }}
    .tag.skipped {{ color: var(--muted); }}
    .detail {{ margin-top: 4px; color: var(--fail); font-size: 12px; }}
    .empty {{ display: none; padding: 28px 16px; color: var(--muted); }}
    @media (max-width: 720px) {{
      .stats {{ grid-template-columns: 1fr 1fr; }}
      .toolbar {{ flex-wrap: wrap; }}
      input[type="search"] {{ width: 100%; margin-left: 0; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="mark" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M3 13.5 9 3l6 10.5H3Z" stroke="#f3e6c8" stroke-width="1.6" stroke-linejoin="round"/></svg>
      </div>
      <div>
        <h1>Invoice Tracker QA</h1>
        <p class="sub">{when} · practice data only</p>
      </div>
    </div>
    <div class="pill {pill}"><span class="dot"></span>{status}</div>
  </header>
  <main>
    <section class="stats">
      <div class="stat pass"><span>Passed</span><strong>{passed}</strong></div>
      <div class="stat fail"><span>Failed</span><strong>{failed}</strong></div>
      <div class="stat"><span>Skipped</span><strong>{skipped}</strong></div>
      <div class="stat"><span>Time</span><strong>{duration}</strong></div>
    </section>
    <section class="panel">
      <div class="toolbar">
        <h2>Checks</h2>
        <input id="search" type="search" placeholder="Search check or page" />
        <div class="filters">
          <button type="button" data-filter="fail">Failed</button>
          <button type="button" data-filter="pass">Passed</button>
          <button type="button" data-filter="all" class="on">All</button>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Check</th>
            <th>Page</th>
            <th>Result</th>
            <th class="time">Duration</th>
          </tr>
        </thead>
        <tbody id="rows">
          {rows}
        </tbody>
      </table>
      <p class="empty" id="empty">No checks match.</p>
    </section>
  </main>
  <script>
    const rows = [...document.querySelectorAll("#rows tr")];
    const search = document.getElementById("search");
    const empty = document.getElementById("empty");
    let filter = "all";
    function apply() {{
      const query = search.value.trim().toLowerCase();
      let shown = 0;
      for (const row of rows) {{
        const text = row.innerText.toLowerCase();
        const result = row.dataset.result;
        const ok = (filter === "all" || result === filter) && (!query || text.includes(query));
        row.hidden = !ok;
        if (ok) shown += 1;
      }}
      empty.hidden = shown !== 0;
    }}
    search.addEventListener("input", apply);
    for (const button of document.querySelectorAll(".filters button")) {{
      button.addEventListener("click", () => {{
        filter = button.dataset.filter;
        for (const item of document.querySelectorAll(".filters button")) item.classList.toggle("on", item === button);
        apply();
      }});
    }}
  </script>
</body>
</html>
"""
