from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models import Transaction
from app.schemas import TransactionCreate, TransactionOut

router = APIRouter()


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)
    if date_from:
        q = q.filter(Transaction.transaction_date >= date_from)
    if date_to:
        q = q.filter(Transaction.transaction_date <= date_to)
    if type:
        q = q.filter(Transaction.type == type)
    if category:
        q = q.filter(Transaction.category == category)
    q = q.order_by(desc(Transaction.transaction_date))
    return q.offset(offset).limit(limit).all()


@router.post("/", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    tx = Transaction(
        type=data.type,
        amount=data.amount,
        category=data.category,
        description=data.description,
        source="manual",
        transaction_date=data.transaction_date or datetime.now(),
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    db.delete(tx)
    db.commit()
