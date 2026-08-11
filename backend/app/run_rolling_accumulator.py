import asyncio
import logging
from app.database import SessionLocal
from app.services.scheduler_service import accumulate_10min_chunk, collect_and_summarize_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_rolling_accumulator")

async def main():
    logger.info("Executing 10-minute rolling buffer accumulator job...")
    db = SessionLocal()
    try:
        # Step 1: Accumulate 10-minute chunk
        await accumulate_10min_chunk(db)
        logger.info("Successfully accumulated 10-minute chunk into SubtitleBuffer.")

        # Step 2: Finalize hourly transcript using accumulated chunks and Gemini System/User Prompt
        logger.info("Finalizing hourly transcript from accumulated buffers...")
        results = await collect_and_summarize_all(db)
        logger.info(f"Rolling Accumulator Finalization Finished: {results}")

    except Exception as e:
        logger.error(f"Error in rolling accumulator runner: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
