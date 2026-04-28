import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, init_db, Expense, Company, User
from sample_data import seed_database
from routes.auth import router as auth_router
from routes.expenses import router as expenses_router
from routes.companies import router as companies_router
from routes.receipts import router as receipts_router

app = FastAPI(title="GeoExpense API", version="2.0.0")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(auth_router)
app.include_router(expenses_router)
app.include_router(companies_router)
app.include_router(receipts_router)


@app.on_event("startup")
async def startup():
    init_db()
    db = next(get_db())
    seed_database(db)


@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/login")
def login_page():
    return FileResponse(str(FRONTEND_DIR / "login.html"))


@app.get("/auth-callback.html")
def auth_callback():
    return FileResponse(str(FRONTEND_DIR / "auth-callback.html"))


@app.get("/profile")
def profile_page():
    return FileResponse(str(FRONTEND_DIR / "profile.html"))


@app.get("/members")
def members_page():
    return FileResponse(str(FRONTEND_DIR / "members.html"))


@app.get("/approvals")
def approvals_page():
    return FileResponse(str(FRONTEND_DIR / "approvals.html"))
