import os
import sys
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import anthropic

sys.path.insert(0, os.path.dirname(__file__))
from database import get_db, init_db, Expense
from sample_data import seed_database

app = FastAPI(title="GeoExpense API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

_claude_client = None


def get_claude():
    global _claude_client
    if _claude_client is None:
        _claude_client = anthropic.Anthropic()
    return _claude_client


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    vendor: str
    latitude: float
    longitude: float
    city: str
    category: Optional[str] = None
    date: Optional[datetime] = None


class ExpenseResponse(BaseModel):
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

    class Config:
        from_attributes = True


@app.on_event("startup")
async def startup():
    init_db()
    db = next(get_db())
    seed_database(db)


@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/expenses", response_model=list[ExpenseResponse])
def list_expenses(db: Session = Depends(get_db)):
    return db.query(Expense).order_by(Expense.date.desc()).all()


@app.get("/api/expenses/summary")
def expense_summary(db: Session = Depends(get_db)):
    expenses = db.query(Expense).all()
    total = sum(e.amount for e in expenses)
    deductible = sum(e.amount for e in expenses if e.tax_deductible)
    by_category: dict[str, float] = {}
    for e in expenses:
        by_category[e.category] = by_category.get(e.category, 0) + e.amount
    return {
        "total": round(total, 2),
        "tax_deductible": round(deductible, 2),
        "potential_savings": round(deductible * 0.25, 2),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
        "count": len(expenses),
    }


@app.post("/api/expenses", response_model=ExpenseResponse)
async def create_expense(data: ExpenseCreate, db: Session = Depends(get_db)):
    category = data.category or "Uncategorized"
    tax_deductible = False
    ai_note = None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import json as _json
            client = get_claude()
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system="""You are a business expense categorization expert with deep knowledge of IRS tax rules.

Category definitions — pick the BEST fit:
- Meals & Entertainment: restaurants, cafes, bars, food delivery, coffee, team lunches, client dinners
- Travel: flights, hotels, Airbnb, car rentals, Uber/Lyft/taxi TO/FROM airports or for multi-day trips
- Transportation: local parking, tolls, subway, bus, Uber/Lyft for short local trips (not airport runs)
- Software & Tech: SaaS, subscriptions, cloud services (AWS/GCP/Azure), software licenses, APIs, domains, hardware
- Office Supplies: stationery, paper, printer ink, office furniture, small equipment
- Professional Development: conferences, courses, books, certifications, workshops, training
- Other: anything that doesn't clearly fit above

Tax rules:
- Meals & Entertainment: 50% deductible — always note this
- Travel & Transportation: 100% deductible when for business
- Everything else: 100% deductible

Return ONLY a raw JSON object — no markdown, no explanation, no code fences:
{"category": "...", "tax_deductible": true, "note": "..."}""",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Title: {data.title}\n"
                            f"Vendor: {data.vendor}\n"
                            f"Amount: ${data.amount:.2f}\n"
                            f"Location: {data.city}"
                        ),
                    },
                    # Prefill forces the model to start directly with JSON
                    {"role": "assistant", "content": "{"},
                ],
            )
            raw = "{" + response.content[0].text
            result = _json.loads(raw)
            category = result.get("category", category)
            tax_deductible = result.get("tax_deductible", False)
            ai_note = result.get("note")
        except Exception as e:
            print(f"AI categorization error: {e}")

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
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"ok": True}
