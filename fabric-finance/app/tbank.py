"""
T-Bank (Tinkoff) Business Open API integration.

Docs: https://business.tinkoff.ru/openapi/docs
API token: в личном кабинете T-Bank → Настройки → API
"""
import os
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Transaction

logger = logging.getLogger(__name__)

TBANK_BASE_URL = "https://business.tinkoff.ru/openapi/api/v1"


def _get_headers() -> dict:
    token = os.getenv("TBANK_API_TOKEN", "")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def sync_tbank_transactions() -> int:
    """
    Pulls last 7 days of transactions from T-Bank and saves new ones to the DB.
    Returns the count of newly saved transactions.
    """
    token = os.getenv("TBANK_API_TOKEN", "")
    account_number = os.getenv("TBANK_ACCOUNT_NUMBER", "")

    if not token or not account_number:
        logger.warning("T-Bank: TBANK_API_TOKEN или TBANK_ACCOUNT_NUMBER не заданы — синхронизация пропущена")
        return 0

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{TBANK_BASE_URL}/bank-statement",
                headers=_get_headers(),
                params={
                    "accountNumber": account_number,
                    "from": date_from,
                    "to": date_to,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("T-Bank API HTTP error: %s — %s", e.response.status_code, e.response.text)
        return 0
    except Exception as e:
        logger.error("T-Bank API error: %s", e)
        return 0

    operations = data.get("operationList", [])
    saved = 0

    db: Session = SessionLocal()
    try:
        for op in operations:
            op_id = op.get("operationId")
            if not op_id:
                continue

            # Skip if already imported
            exists = db.query(Transaction).filter(Transaction.tbank_id == op_id).first()
            if exists:
                continue

            op_type = op.get("type", "")        # "Credit" | "Debit"
            amount = float(op.get("amount", 0))
            description = op.get("description", "")
            op_time_str = op.get("operationTime") or op.get("chargeDate")

            try:
                op_time = datetime.fromisoformat(op_time_str.replace("Z", "+00:00"))
            except Exception:
                op_time = datetime.now()

            tx = Transaction(
                type="income" if op_type == "Credit" else "expense",
                amount=abs(amount),
                category="Т-Банк" if op_type == "Debit" else "Продажа",
                description=description,
                source="tbank",
                tbank_id=op_id,
                transaction_date=op_time,
            )
            db.add(tx)
            saved += 1

        db.commit()
    finally:
        db.close()

    logger.info("T-Bank sync: сохранено %d новых операций", saved)
    return saved
