"""JSON API for the same invoice rules the pages use."""
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app import services as s

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


class LineIn(BaseModel):
    description: str = ""
    quantity: Any = None
    unitPrice: Any = None


class InvoiceIn(BaseModel):
    customerName: str = ""
    customerEmail: str = ""
    issueDate: str = ""
    dueDate: str = ""
    notes: str = ""
    amountPaid: Any = 0
    currency: str = "AED"
    lineItems: list[LineIn] = Field(default_factory=list)


def _today(request: Request) -> str:
    return s.calendar_today(s.parse_offset(request.cookies.get("tz_offset_minutes")))


def _body(payload: InvoiceIn) -> dict:
    data = payload.model_dump()
    data["lineItems"] = [line.model_dump() for line in payload.lineItems]
    return data


@router.get("")
def list_invoices(
    request: Request,
    q: str = "",
    status: str = "",
    customer: str = "",
    due: str = "",
    city: str = "",
):
    today = _today(request)
    invoices, counts, selected = s.list_invoices(q, status, today, customer, due, city)
    return {
        "invoices": invoices, "counts": counts, "status": selected, "today": today,
        "customer": customer, "due": due, "city": city,
    }


@router.get("/{number}")
def get_invoice(number: str, request: Request):
    return s.get_invoice(number, _today(request))


@router.post("", status_code=201)
def create_invoice(payload: InvoiceIn, request: Request):
    return s.create_invoice(_body(payload), _today(request))


@router.put("/{number}")
def update_invoice(number: str, payload: InvoiceIn, request: Request):
    return s.update_invoice(number, _body(payload), _today(request))


@router.delete("/{number}")
def delete_invoice(number: str):
    return {"deleted": s.delete_invoice(number)}
