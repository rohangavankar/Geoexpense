from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./geoexpense.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="company", foreign_keys="User.company_id")
    expenses = relationship("Expense", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    name = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    role = Column(String, default="member")  # owner, admin, member
    google_id = Column(String, nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="users", foreign_keys=[company_id])
    expenses = relationship("Expense", back_populates="user", foreign_keys="Expense.user_id")


class InviteToken(Base):
    __tablename__ = "invite_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    role = Column(String, default="member")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    vendor = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    city = Column(String, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    tax_deductible = Column(Boolean, default=False)
    ai_note = Column(String, nullable=True)
    receipt_url = Column(String, nullable=True)
    status = Column(String, default="approved")  # pending, approved, rejected
    rejection_note = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="expenses", foreign_keys=[user_id])
    company = relationship("Company", back_populates="expenses")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
