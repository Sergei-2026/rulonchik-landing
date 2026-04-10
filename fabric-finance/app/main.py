import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import engine, Base, SessionLocal
from app.models import Category
from app.routers import transactions, categories, reports
from app.tbank import sync_tbank_transactions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = [
    ("Продажа", "income"),
    ("Аренда", "expense"),
    ("Зарплата", "expense"),
    ("Закупка товара", "expense"),
    ("Коммунальные", "expense"),
    ("Реклама", "expense"),
    ("Прочее", "expense"),
]

scheduler = AsyncIOScheduler()


def seed_categories():
    db = SessionLocal()
    try:
        for name, cat_type in DEFAULT_CATEGORIES:
            exists = db.query(Category).filter(
                Category.name == name, Category.type == cat_type
            ).first()
            if not exists:
                db.add(Category(name=name, type=cat_type, is_default=True))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    seed_categories()
    logger.info("База данных инициализирована")

    # T-Bank sync every hour
    scheduler.add_job(sync_tbank_transactions, "interval", hours=1, id="tbank_sync")
    scheduler.start()
    logger.info("Планировщик T-Bank запущен (каждый час)")

    yield

    # Shutdown
    scheduler.shutdown()


app = FastAPI(title="Fabric Finance", lifespan=lifespan)

app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


@app.post("/api/tbank/sync")
async def manual_tbank_sync():
    saved = await sync_tbank_transactions()
    return {"saved": saved, "message": f"Синхронизировано: {saved} новых операций"}


# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(frontend_dir, "index.html"))
