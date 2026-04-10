from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional
import calendar

from app.database import get_db
from app.models import Transaction
from app.schemas import DashboardOut, MonthlyRow, CategoryBreakdown

router = APIRouter()

MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


def _sum(db: Session, tx_type: str, date_from: datetime, date_to: datetime) -> float:
    result = db.query(func.sum(Transaction.amount)).filter(
        Transaction.type == tx_type,
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to,
    ).scalar()
    return round(result or 0, 2)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = now

    today_income = _sum(db, "income", today_start, today_end)
    today_expense = _sum(db, "expense", today_start, today_end)
    month_income = _sum(db, "income", month_start, month_end)
    month_expense = _sum(db, "expense", month_start, month_end)

    # Simple linear forecast: daily_avg * days_in_month
    days_passed = now.day
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_left = days_in_month - days_passed

    if days_passed > 0:
        daily_income_avg = month_income / days_passed
        daily_expense_avg = month_expense / days_passed
        forecast = round(
            (month_income + daily_income_avg * days_left) -
            (month_expense + daily_expense_avg * days_left), 2
        )
    else:
        forecast = None

    return DashboardOut(
        today_income=today_income,
        today_expense=today_expense,
        today_profit=round(today_income - today_expense, 2),
        month_income=month_income,
        month_expense=month_expense,
        month_profit=round(month_income - month_expense, 2),
        forecast_end_of_month=forecast,
    )


@router.get("/monthly", response_model=list[MonthlyRow])
def monthly_report(months: int = 6, db: Session = Depends(get_db)):
    now = datetime.now()
    rows = []
    prev_income: Optional[float] = None
    prev_expense: Optional[float] = None
    prev_profit: Optional[float] = None

    for i in range(months - 1, -1, -1):
        point = now - relativedelta(months=i)
        start = point.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(point.year, point.month)[1]
        end = point.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

        income = _sum(db, "income", start, end)
        expense = _sum(db, "expense", start, end)
        profit = round(income - expense, 2)

        def pct(curr, prev):
            if prev is None or prev == 0:
                return None
            return round((curr - prev) / prev * 100, 1)

        rows.append(MonthlyRow(
            month=f"{MONTHS_RU[point.month]} {point.year}",
            income=income,
            expense=expense,
            profit=profit,
            income_change=pct(income, prev_income),
            expense_change=pct(expense, prev_expense),
            profit_change=pct(profit, prev_profit),
        ))
        prev_income, prev_expense, prev_profit = income, expense, profit

    return rows


@router.get("/expenses-breakdown", response_model=list[CategoryBreakdown])
def expenses_breakdown(month_offset: int = 0, db: Session = Depends(get_db)):
    now = datetime.now() - relativedelta(months=month_offset)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end = now.replace(day=last_day, hour=23, minute=59, second=59)

    rows = db.query(
        Transaction.category,
        func.sum(Transaction.amount).label("total")
    ).filter(
        Transaction.type == "expense",
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end,
    ).group_by(Transaction.category).all()

    total = sum(r.total for r in rows) or 1
    return [
        CategoryBreakdown(
            category=r.category or "Без категории",
            amount=round(r.total, 2),
            percent=round(r.total / total * 100, 1),
        )
        for r in sorted(rows, key=lambda x: x.total, reverse=True)
    ]
