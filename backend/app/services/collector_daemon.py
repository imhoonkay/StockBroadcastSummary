import os
import sys
import time
import logging
import multiprocessing
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import SessionLocal
from app.models import Channel, SubtitleBuffer, get_kst_now
from app.services.youtube_service import YoutubeService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [CollectorDaemon] %(message)s"
)
logger = logging.getLogger("stockbs_collector")

def _collect_channel_worker(channel_id: int, name: str, identifier: str, url: str, window_label: str):
    """Worker process executed in parallel for each channel"""
    logger.info(f"[Worker-{identifier}] Starting 10-minute audio capture & Whisper STT for {name}...")
    try:
        # Perform 10-minute (600s) synchronous capture and Whisper STT
        chunk_text = YoutubeService._fetch_transcript_sync(url, name, duration_sec=600, channel_identifier=identifier)
        
        if not chunk_text or chunk_text.startswith("[수집 실패]"):
            logger.error(f"[Worker-{identifier}] Collection failed for {name}: {chunk_text}. Skipping DB insert.")
            return

        db = SessionLocal()
        try:
            buf = SubtitleBuffer(
                channel_id=channel_id,
                channel_identifier=identifier,
                window_label=window_label,
                chunk_text=chunk_text,
                created_at=get_kst_now()
            )
            db.add(buf)
            db.commit()
            logger.info(f"[Worker-{identifier}] Saved 10-minute chunk to DB successfully ({len(chunk_text)} chars).")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[Worker-{identifier}] Error collecting transcript for {name}: {e}")

def run_collection_cycle():
    """Triggered strictly at wall-clock 10-minute marks (10m, 20m, 30m, 40m, 50m, 00m)"""
    now = get_kst_now()
    # Format window label for exact 10-minute interval (e.g. 10:50~11:00)
    minute_bucket = (now.minute // 10) * 10
    bucket_start = now.replace(minute=minute_bucket, second=0, microsecond=0)
    bucket_end = bucket_start + timedelta(minutes=10)
    window_label = f"{bucket_start.strftime('%Y-%m-%d %H:%M')}~{bucket_end.strftime('%H:%M')}"

    db = SessionLocal()
    try:
        channels = db.query(Channel).filter(Channel.status == "on").all()
        logger.info(f"Triggering wall-clock 10-minute collection for {len(channels)} active channel(s) ({window_label})...")

        processes = []
        for ch in channels:
            p = multiprocessing.Process(
                target=_collect_channel_worker,
                args=(ch.id, ch.name, ch.identifier, ch.url, window_label)
            )
            p.start()
            processes.append((ch.name, p))

        # Wait for all channel worker processes to complete
        for name, p in processes:
            p.join()
            logger.info(f"Worker process for {name} finished.")

    except Exception as e:
        logger.error(f"Error in collection cycle: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("==================================================")
    logger.info(" Starting StockBS 10-Min Collector Daemon Service ")
    logger.info(" Strictly aligned to wall-clock 10-min marks (KST) ")
    logger.info("==================================================")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_collection_cycle,
        trigger=CronTrigger(minute="*/10"),
        id="collector_10min_job",
        max_instances=5,
        misfire_grace_time=300,
        replace_existing=True
    )

    try:
        logger.info("Collector daemon scheduler started. Waiting for next wall-clock 10-min trigger (00m, 10m, 20m, 30m, 40m, 50m)...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Collector daemon stopped.")
