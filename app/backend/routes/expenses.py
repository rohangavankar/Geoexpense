import os
import json
from datetime import datetime
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, Expense, User
from deps import get_current_user, require_admin

router = APIRouter(prefix="/api/expenses", tags=["expenses"])

_claude = None


def get_claude():
    global _claude
    if _claude is None:
        _claude = anthropic.Anthropic()
    return _claude


# ── Pydantic models ───────────────────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    title: str = Field(..., max_length=200)
    amount: float = Field(..., gt=0, le=1_000_000)
    vendor: str = Field(..., max_length=200)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str = Field(..., max_length=200)
    category: Optional[str] = None
    date: Optional[datetime] = None
    receipt_url: Optional[str] = None


class ExpenseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    amount: Optional[float] = Field(None, gt=0, le=1_000_000)
    vendor: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = None
    date: Optional[datetime] = None


class ExpenseOut(BaseModel):
    id: int
    title: str
    amount: float
    category: str
    vendor: str
    latitude: float
    longitude: float
    city: str
    date: datetime
    tax_deductible: bool
    ai_note: Optional[str]
    receipt_url: Optional[str]
    status: str
    rejection_note: Optional[str]
    user_id: Optional[int]
    submitter_name: Optional[str] = None

    class Config:
        from_attributes = True


# ── AI categorization ─────────────────────────────────────────────────────────

CATEGORIZE_SYSTEM = """You are a business expense categorization expert with deep knowledge of IRS tax law.

CATEGORIES — pick the single best fit:
- Meals & Entertainment: any food/drink with a business purpose — client dinners, work lunches, team meals,
  coffee meetings, happy hours, work dinners, offsite meals, catered events, food delivery for team
- Travel: anything for a business trip — flights, hotels, Airbnb, car rentals, Uber/Lyft to/from airport,
  train tickets, taxis for out-of-town trips, baggage fees, travel insurance
- Transportation: local commuting costs — parking, tolls, subway/bus passes, local Uber/Lyft rides,
  gas for business driving, bike share
- Software & Tech: any digital tool — SaaS subscriptions, cloud hosting (AWS/GCP/Azure), software licenses,
  domains, APIs, hardware (laptop, monitor, keyboard), phone bill if business use
- Office Supplies: physical supplies — stationery, paper, printer ink/toner, office furniture,
  whiteboard, notebooks, pens, cleaning supplies for office
- Professional Development: investing in skills — conferences, courses, books, certifications,
  workshops, seminars, coaching, industry memberships, professional associations
- Other: anything that doesn't clearly fit the above

BUSINESS LANGUAGE TO RECOGNIZE:
- "work dinner / work lunch / work breakfast" → Meals & Entertainment
- "team dinner / team lunch / team offsite" → Meals & Entertainment
- "client dinner / client meeting / prospect lunch" → Meals & Entertainment
- "offsite / company retreat" → Travel (if overnight) or Meals & Entertainment (if just food)
- "flight / hotel / lodging / airfare" → Travel
- "Uber / Lyft / taxi" → Travel (if airport/trip) or Transportation (if local)
- "AWS / GCP / Azure / Vercel / Heroku" → Software & Tech
- "Notion / Slack / Linear / Figma / GitHub / Zoom" → Software & Tech
- "conference / summit / meetup" → Professional Development

TAX DEDUCTIBILITY:
- Meals & Entertainment: 50% deductible — ALWAYS mention the 50% limit in the note
- Travel: 100% deductible for business trips — note "keep receipts and document business purpose"
- Transportation: 100% deductible for business use
- Software & Tech: 100% deductible
- Office Supplies: 100% deductible
- Professional Development: 100% deductible if directly related to current role

The note should be one clear sentence: what it is, deductibility, and any important caveat.

Return ONLY a raw JSON object, no markdown, no explanation:
{"category": "...", "tax_deductible": true, "note": "..."}"""


def ai_categorize(title: str, vendor: str, amount: float, city: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "Uncategorized", False, None
    try:
        client = get_claude()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=CATEGORIZE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Title: {title}\nVendor: {vendor or 'unknown'}\nAmount: ${amount:.2f}\nLocation: {city or 'unknown'}",
                },
            ],
        )
        raw = response.content[0].text
        # Extract JSON from response (strip markdown fences if present)
        start, end = raw.find("{"), raw.rfind("}") + 1
        raw = raw[start:end] if start != -1 else raw
        result = json.loads(raw)
        return result.get("category", "Uncategorized"), result.get("tax_deductible", False), result.get("note")
    except Exception as e:
        print(f"AI categorization error: {e}")
        return "Uncategorized", False, None


# ── Routes ────────────────────────────────────────────────────────────────────

class PreviewBody(BaseModel):
    title: str
    vendor: Optional[str] = ""
    amount: Optional[float] = 0
    city: Optional[str] = ""


@router.post("/preview")
def preview_category(
    body: PreviewBody,
    current_user: User = Depends(get_current_user),
):
    if not body.title.strip():
        return {"category": None, "tax_deductible": None, "note": None}
    category, tax_deductible, note = ai_categorize(
        body.title, body.vendor or "", body.amount or 0, body.city or ""
    )
    return {"category": category, "tax_deductible": tax_deductible, "note": note}

@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Expense).filter(Expense.company_id == current_user.company_id)

    # Members only see their own expenses
    if current_user.role == "member":
        q = q.filter(Expense.user_id == current_user.id)

    if status_filter:
        q = q.filter(Expense.status == status_filter)
    if category:
        q = q.filter(Expense.category == category)
    if date_from:
        q = q.filter(Expense.date >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Expense.date <= datetime.fromisoformat(date_to))

    expenses = q.order_by(Expense.date.desc()).all()

    result = []
    for e in expenses:
        out = ExpenseOut.model_validate(e)
        out.submitter_name = e.user.name if e.user else None
        result.append(out)
    return result


@router.get("/summary")
def expense_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Expense).filter(
        Expense.company_id == current_user.company_id,
        Expense.status != "rejected",
    )
    if current_user.role == "member":
        q = q.filter(Expense.user_id == current_user.id)
    if date_from:
        q = q.filter(Expense.date >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Expense.date <= datetime.fromisoformat(date_to))

    expenses = q.all()
    total = sum(e.amount for e in expenses)
    deductible = sum(e.amount for e in expenses if e.tax_deductible)
    by_category: dict[str, float] = {}
    pending_count = sum(1 for e in expenses if e.status == "pending")
    for e in expenses:
        by_category[e.category] = by_category.get(e.category, 0) + e.amount

    return {
        "total": round(total, 2),
        "tax_deductible": round(deductible, 2),
        "potential_savings": round(deductible * 0.25, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
        "count": len(expenses),
        "pending_count": pending_count,
    }


@router.post("", response_model=ExpenseOut)
def create_expense(
    data: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    category = data.category or "Uncategorized"
    tax_deductible = False
    ai_note = None

    if not data.category:
        category, tax_deductible, ai_note = ai_categorize(
            data.title, data.vendor, data.amount, data.city
        )

    # Owners/admins are auto-approved; members need approval
    initial_status = "approved" if current_user.role in ("owner", "admin") else "pending"

    expense = Expense(
        title=data.title,
        amount=data.amount,
        category=category,
        vendor=data.vendor,
        latitude=data.latitude,
        longitude=data.longitude,
        city=data.city,
        date=data.date or datetime.utcnow(),
        tax_deductible=tax_deductible,
        ai_note=ai_note,
        receipt_url=data.receipt_url,
        status=initial_status,
        user_id=current_user.id,
        company_id=current_user.company_id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    out = ExpenseOut.model_validate(expense)
    out.submitter_name = current_user.name
    return out


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.company_id == current_user.company_id,
    ).first()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if expense.user_id != current_user.id and current_user.role not in ("owner", "admin"):
        raise HTTPException(403, "Cannot edit another member's expense")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(expense, field, value)

    if data.title or data.vendor or data.amount or data.city:
        expense.category, expense.tax_deductible, expense.ai_note = ai_categorize(
            expense.title, expense.vendor, expense.amount, expense.city
        )

    db.commit()
    db.refresh(expense)
    out = ExpenseOut.model_validate(expense)
    out.submitter_name = expense.user.name if expense.user else None
    return out


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.company_id == current_user.company_id,
    ).first()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if expense.user_id != current_user.id and current_user.role not in ("owner", "admin"):
        raise HTTPException(403, "Cannot delete another member's expense")
    db.delete(expense)
    db.commit()
    return {"ok": True}


@router.patch("/{expense_id}/deductible")
def set_deductible(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.company_id == current_user.company_id,
    ).first()
    if not expense:
        raise HTTPException(404, "Expense not found")
    if expense.user_id != current_user.id and current_user.role not in ("owner", "admin"):
        raise HTTPException(403, "Cannot edit another member's expense")
    expense.tax_deductible = not expense.tax_deductible
    if not expense.tax_deductible:
        expense.ai_note = "Marked as personal — not tax deductible."
    db.commit()
    return {"ok": True, "tax_deductible": expense.tax_deductible}


@router.patch("/{expense_id}/approve")
def approve_expense(
    expense_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.company_id == current_user.company_id,
    ).first()
    if not expense:
        raise HTTPException(404, "Expense not found")
    expense.status = "approved"
    expense.approved_by = current_user.id
    expense.approved_at = datetime.utcnow()
    expense.rejection_note = None
    db.commit()
    return {"ok": True, "status": "approved"}


class RejectBody(BaseModel):
    note: Optional[str] = None


@router.patch("/{expense_id}/reject")
def reject_expense(
    expense_id: int,
    body: RejectBody = RejectBody(),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.company_id == current_user.company_id,
    ).first()
    if not expense:
        raise HTTPException(404, "Expense not found")
    expense.status = "rejected"
    expense.rejection_note = body.note
    db.commit()
    return {"ok": True, "status": "rejected"}


@router.get("/export/csv")
def export_csv(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Expense).filter(
        Expense.company_id == current_user.company_id,
        Expense.status == "approved",
    )
    if current_user.role == "member":
        q = q.filter(Expense.user_id == current_user.id)
    if date_from:
        q = q.filter(Expense.date >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Expense.date <= datetime.fromisoformat(date_to))

    expenses = q.order_by(Expense.date.desc()).all()

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Title", "Vendor", "Category", "Amount", "City", "Tax Deductible", "Submitted By", "AI Note"])
    for e in expenses:
        writer.writerow([
            e.date.strftime("%Y-%m-%d"),
            e.title, e.vendor, e.category,
            f"{e.amount:.2f}", e.city,
            "Yes" if e.tax_deductible else "No",
            e.user.name if e.user else "",
            e.ai_note or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )
