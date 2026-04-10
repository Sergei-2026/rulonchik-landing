"""
Telegram bot для магазина тканей.

Команды продавца:
  приход 5000              → доход 5000 ₽
  приход 5000 описание     → доход 5000 ₽ с описанием
  расход аренда 15000      → расход 15000 ₽, категория "аренда"
  расход 15000             → расход 15000 ₽, категория "Прочее"

Команды для отчётов:
  /today  — сводка за сегодня
  /month  — сводка за текущий месяц
  /help   — список команд
"""
import os
import re
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from app.database import SessionLocal
from app.models import Transaction, Category

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(amount: float) -> str:
    return f"{amount:,.0f} ₽".replace(",", " ")


def _find_category(db, name: str, tx_type: str) -> str:
    """Ищет категорию по частичному совпадению (без учёта регистра)."""
    name_lower = name.lower().strip()
    cats = db.query(Category).filter(Category.type == tx_type).all()
    for cat in cats:
        if cat.name.lower() == name_lower:
            return cat.name
        if name_lower in cat.name.lower() or cat.name.lower() in name_lower:
            return cat.name
    # Default
    return "Продажа" if tx_type == "income" else "Прочее"


def _parse_message(text: str):
    """
    Разбирает сообщение продавца.
    Возвращает (type, amount, category_hint, description) или None если не распознано.
    """
    text = text.strip()
    lower = text.lower()

    # Найти сумму (целое или дробное число)
    amount_match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not amount_match:
        return None
    amount = float(amount_match.group(1).replace(",", "."))

    if lower.startswith("приход"):
        # "приход 5000" или "приход 5000 описание"
        rest = text[len("приход"):].strip()
        rest = re.sub(r"\d+(?:[.,]\d+)?", "", rest, count=1).strip()
        return ("income", amount, None, rest or None)

    if lower.startswith("расход"):
        # "расход аренда 15000" или "расход 15000 аренда"
        rest = text[len("расход"):].strip()
        # Убираем сумму из остатка
        rest_no_amount = re.sub(r"\d+(?:[.,]\d+)?", "", rest, count=1).strip()
        category_hint = rest_no_amount or None
        return ("expense", amount, category_hint, None)

    return None


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот учёта финансов магазина тканей.\n\n"
        "Как вносить данные:\n"
        "  приход 5000\n"
        "  приход 5000 наличные\n"
        "  расход аренда 15000\n"
        "  расход 30000 зарплата\n\n"
        "Отчёты:\n"
        "  /today — за сегодня\n"
        "  /month — за месяц\n"
        "  /help  — эта справка"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.now().replace(hour=23, minute=59, second=59)

        from sqlalchemy import func
        income = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == "income",
            Transaction.transaction_date >= today_start,
            Transaction.transaction_date <= today_end,
        ).scalar() or 0

        expense = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == "expense",
            Transaction.transaction_date >= today_start,
            Transaction.transaction_date <= today_end,
        ).scalar() or 0

        profit = income - expense
        sign = "+" if profit >= 0 else ""
        await update.message.reply_text(
            f"Сводка за сегодня ({datetime.now().strftime('%d.%m.%Y')}):\n\n"
            f"  Приход:  {_fmt(income)}\n"
            f"  Расход:  {_fmt(expense)}\n"
            f"  Прибыль: {sign}{_fmt(profit)}"
        )
    finally:
        db.close()


async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        from sqlalchemy import func
        income = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == "income",
            Transaction.transaction_date >= month_start,
        ).scalar() or 0

        expense = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == "expense",
            Transaction.transaction_date >= month_start,
        ).scalar() or 0

        profit = income - expense
        sign = "+" if profit >= 0 else ""

        MONTHS_RU = {
            1: "январь", 2: "февраль", 3: "март", 4: "апрель",
            5: "май", 6: "июнь", 7: "июль", 8: "август",
            9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь"
        }
        month_name = MONTHS_RU[now.month]

        await update.message.reply_text(
            f"Сводка за {month_name} {now.year}:\n\n"
            f"  Приход:  {_fmt(income)}\n"
            f"  Расход:  {_fmt(expense)}\n"
            f"  Прибыль: {sign}{_fmt(profit)}"
        )
    finally:
        db.close()


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    parsed = _parse_message(text)

    if not parsed:
        await update.message.reply_text(
            "Не понял. Примеры:\n"
            "  приход 5000\n"
            "  расход аренда 15000\n\n"
            "Напишите /help для справки."
        )
        return

    tx_type, amount, category_hint, description = parsed

    db = SessionLocal()
    try:
        category = _find_category(db, category_hint, tx_type) if category_hint else (
            "Продажа" if tx_type == "income" else "Прочее"
        )
        tx = Transaction(
            type=tx_type,
            amount=amount,
            category=category,
            description=description,
            source="manual",
            transaction_date=datetime.now(),
        )
        db.add(tx)
        db.commit()

        label = "Приход" if tx_type == "income" else "Расход"
        await update.message.reply_text(
            f"Записано!\n"
            f"  {label}: {_fmt(amount)}\n"
            f"  Категория: {category}"
            + (f"\n  Описание: {description}" if description else "")
        )
    except Exception as e:
        logger.error("Bot DB error: %s", e)
        await update.message.reply_text("Ошибка при сохранении. Попробуйте ещё раз.")
    finally:
        db.close()


# ── App builder ───────────────────────────────────────────────────────────────

def build_application() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("month", cmd_month))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app
