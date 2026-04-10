from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ── Transactions ──────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    type: str                        # "income" | "expense"
    amount: float
    category: Optional[str] = None
    description: Optional[str] = None
    transaction_date: Optional[datetime] = None


class TransactionOut(BaseModel):
    id: int
    type: str
    amount: float
    category: Optional[str]
    description: Optional[str]
    source: str
    transaction_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Categories ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    type: str                        # "income" | "expense"


class CategoryUpdate(BaseModel):
    name: str


class CategoryOut(BaseModel):
    id: int
    name: str
    type: str
    is_default: bool

    model_config = {"from_attributes": True}


# ── Reports ───────────────────────────────────────────────────────────────────

class DashboardOut(BaseModel):
    today_income: float
    today_expense: float
    today_profit: float
    month_income: float
    month_expense: float
    month_profit: float
    forecast_end_of_month: Optional[float]


class MonthlyRow(BaseModel):
    month: str                       # "Апрель 2026"
    income: float
    expense: float
    profit: float
    income_change: Optional[float]   # % vs previous month
    expense_change: Optional[float]
    profit_change: Optional[float]


class CategoryBreakdown(BaseModel):
    category: str
    amount: float
    percent: float
