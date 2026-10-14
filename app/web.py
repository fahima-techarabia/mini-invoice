"""HTML pages for the invoice tracker."""
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app import services as s

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["urlencode"] = lambda value: urlencode({"": value})[1:]

NOTICES = {
    "saved": "Invoice {number} saved.",
    "updated": "Invoice {number} updated.",
    "deleted": "Invoice {number} deleted.",
}


def today_from(request: Request) -> str:
    return s.calendar_today(s.parse_offset(request.cookies.get("tz_offset_minutes")))


def _notice(code: str | None, number: str | None) -> str | None:
    if code not in NOTICES or not s.INVOICE_NUMBER.fullmatch(number or ""):
        return None
    return NOTICES[code].format(number=number)


def _redirect(url: str, notice: str | None = None, number: str | None = None):
    if notice and number:
        url = f"{url}?{urlencode({'notice': notice, 'number': number})}"
    return RedirectResponse(url, status_code=303)


def _payload(form) -> dict:
    descriptions = form.getlist("description")
    quantities = form.getlist("quantity")
    prices = form.getlist("unit_price")
    count = max(len(descriptions), len(quantities), len(prices))
    lines = []
    for index in range(count):
        lines.append({
            "description": descriptions[index] if index < len(descriptions) else "",
            "quantity": quantities[index] if index < len(quantities) else "",
            "unitPrice": prices[index] if index < len(prices) else "",
        })
    return {
        "customerId": form.get("customer_id", ""),
        "customerName": form.get("customer_name", ""),
        "customerEmail": form.get("customer_email", ""),
        "issueDate": form.get("issue_date", ""),
        "dueDate": form.get("due_date", ""),
        "notes": form.get("notes", ""),
        "amountPaid": form.get("amount_paid", ""),
        "currency": "AED",
        "lineItems": lines,
    }


def render_message(request: Request, status: int, message: str):
    headings = {403: "Not allowed", 404: "Not found", 409: "Conflict", 422: "Check the form"}
    return templates.TemplateResponse(
        request, "message.html",
        {"status": status, "heading": headings.get(status, "Something went wrong"), "message": message,
         "errors": [], "notice": None, "page": ""},
        status_code=status,
    )


@router.get("/")
def home():
    return _redirect("/invoices")


def _form_page(request: Request, **extra):
    customers, _cities = s.customer_choices()
    extra.setdefault("customers", customers)
    extra.setdefault("errors", [])
    extra.setdefault("notice", None)
    extra.setdefault("today", today_from(request))
    return extra


@router.get("/invoices")
def invoice_list(
    request: Request,
    q: str = "",
    status: str = "",
    customer: str = "",
    due: str = "",
    city: str = "",
    notice: str | None = None,
    number: str | None = None,
):
    today = today_from(request)
    invoices, counts, selected = s.list_invoices(q, status, today, customer, due, city)
    customers, cities = s.customer_choices()
    filtering = bool(q or customer or city or due or selected)
    return templates.TemplateResponse(request, "list.html", {
        "invoices": invoices, "counts": counts, "selected": selected, "statuses": s.STATUSES,
        "q": q, "customer": customer, "due": due, "city": city,
        "customers": customers, "cities": cities, "book": s.book_summary(today),
        "filtering": filtering,
        "today": today, "total": sum(counts.values()), "page": "list",
        "notice": _notice(notice, number), "errors": [],
    })


@router.get("/queries")
def query_checks(request: Request):
    from app.checks import ten_questions

    today = today_from(request)
    rows = ten_questions(today)
    return templates.TemplateResponse(request, "queries.html", {
        "rows": rows, "today": today, "page": "queries",
        "passed": sum(1 for row in rows if row["match"]),
        "notice": None, "errors": [],
    })


@router.get("/invoices/new")
def new_page(request: Request):
    return templates.TemplateResponse(request, "form.html", _form_page(
        request, mode="new", values=s.blank_form(), page="new",
    ))


@router.post("/invoices/new")
async def new_invoice(request: Request):
    form = await request.form()
    payload = _payload(form)
    try:
        invoice = s.create_invoice(payload, today_from(request))
    except s.AppError as exc:
        return templates.TemplateResponse(request, "form.html", _form_page(
            request, mode="new", values=s.form_from_request(payload), errors=exc.messages, page="new",
        ), status_code=exc.status)
    return _redirect(f"/invoices/{invoice['invoiceNumber']}", "saved", invoice["invoiceNumber"])


@router.get("/invoices/{number}")
def view_invoice(request: Request, number: str, notice: str | None = None):
    invoice = s.get_invoice(number, today_from(request))
    shown = _notice(notice, number) if notice else None
    return templates.TemplateResponse(request, "detail.html", {
        "invoice": invoice, "notice": shown, "errors": [], "page": "list", "today": today_from(request),
    })


@router.get("/invoices/{number}/edit")
def edit_page(request: Request, number: str):
    invoice = s.get_invoice(number, today_from(request))
    return templates.TemplateResponse(request, "form.html", _form_page(
        request, mode="edit", invoice=invoice, values=s.form_from_invoice(invoice), page="list",
    ))


@router.post("/invoices/{number}/edit")
async def edit_invoice(request: Request, number: str):
    form = await request.form()
    payload = _payload(form)
    try:
        invoice = s.update_invoice(number, payload, today_from(request))
    except s.AppError as exc:
        if exc.status == 404:
            raise
        values = s.form_from_request(payload)
        return templates.TemplateResponse(request, "form.html", _form_page(
            request, mode="edit", invoice={"invoiceNumber": number}, values=values,
            errors=exc.messages, page="list",
        ), status_code=exc.status)
    return _redirect(f"/invoices/{invoice['invoiceNumber']}", "updated", invoice["invoiceNumber"])


@router.post("/invoices/{number}/delete")
def delete_invoice(number: str):
    deleted = s.delete_invoice(number)
    return _redirect("/invoices", "deleted", deleted)
