import asyncio
import logging
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.scheduler_service import collect_and_summarize_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_hourly_transcript")

async def main():
    logger.info("Starting hourly transcript generation and database insertion job...")
    db: Session = SessionLocal()
    try:
        results = await collect_and_summarize_all(db)
        logger.info(f"Hourly collection finished. Results: {results}")
    except Exception as e:
        logger.error(f"Error executing hourly transcript script: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
