from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)          # "income" | "expense"
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    description = Column(String, nullable=True)
    source = Column(String, default="manual")      # "manual" | "tbank"
    tbank_id = Column(String, nullable=True, unique=True)
    transaction_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)          # "income" | "expense"
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
