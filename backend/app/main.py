import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import engine, Base, SessionLocal
from app.models import Channel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stockbs_backend")

def seed_initial_channels():
    db: Session = SessionLocal()
    try:
        count = db.query(Channel).count()
        if count == 0:
            logger.info("Seeding initial channels...")
            seed_data = [
                {
                    "name": "매일경제TV",
                    "identifier": "mkeconomy_tv",
                    "handle": "MKeconomy_TV",
                    "url": "https://www.youtube.com/@MKeconomy_TV/live",
                    "status": "on"
                },
                {
                    "name": "서울경제TV",
                    "identifier": "seouleconomytv",
                    "handle": "SeoulEconomyTV",
                    "url": "https://www.youtube.com/@SeoulEconomyTV/live",
                    "status": "on"
                },
                {
                    "name": "한국경제TV",
                    "identifier": "hkwowtv",
                    "handle": "hkwowtv",
                    "url": "https://www.youtube.com/hkwowtv/live",
                    "status": "on"
                }
            ]
            for item in seed_data:
                ch = Channel(**item)
                db.add(ch)
            db.commit()
            logger.info("Initial channels seeded successfully.")

    except Exception as e:
        logger.error(f"Failed to seed channels: {e}")
        db.rollback()
    finally:
        db.close()

from app.services.scheduler_service import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions: ensure DB tables exist, seed channels & start background schedulers
    Base.metadata.create_all(bind=engine)
    seed_initial_channels()
    start_scheduler()
    logger.info("Background schedulers (YouTube STT, Summaries, 05:30 KST KOSPI/Macro) started successfully.")
    yield
    shutdown_scheduler()
    logger.info("Background schedulers shut down cleanly.")


from app.routers import auth, channels, subtitles, summaries, buffers, kospi200

app = FastAPI(
    title="StockBroadcastSummary API",
    description="YouTube Stock Broadcast Subtitle Collector & Gemini AI Summary Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(subtitles.router)
app.include_router(summaries.router)
app.include_router(buffers.router)
app.include_router(kospi200.router)


@app.get("/")
def read_root():
    return {
        "app": "StockBroadcastSummary API Server",
        "status": "online",
        "port": 8099
    }
