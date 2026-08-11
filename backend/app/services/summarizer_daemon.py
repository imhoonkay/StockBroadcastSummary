import os
import sys
import time
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import SessionLocal
from app.config import settings
from app.models import Channel, SubtitleFile, Summary, SubtitleBuffer, get_kst_now
from app.services.gemini_service import GeminiService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SummarizerDaemon] %(message)s"
)
logger = logging.getLogger("stockbs_summarizer")

def run_hourly_summary_cycle(channel_id: int = None):
    """Triggered every hour at minute 0: consolidates 10min buffers, saves TXT file & runs Gemini AI analysis"""
    now = get_kst_now()
    # Finalize the completed 1-hour window (e.g. at 02:00, finalize 01:00~02:00)
    end_time = now.replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=1)
    window_label = f"{start_time.strftime('%Y-%m-%d %H:00')}~{end_time.strftime('%H:00')}"

    db = SessionLocal()
    try:
        query = db.query(Channel)
        if channel_id:
            query = query.filter(Channel.id == channel_id)
        else:
            query = query.filter(Channel.status == "on")

        channels = query.all()
        logger.info(f"Starting hourly finalize & Gemini AI summary for {len(channels)} channel(s) ({window_label})...")
        os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

        for ch in channels:
            try:
                # 1. Fetch all accumulated 10-minute buffer chunks for this channel
                buffers = db.query(SubtitleBuffer).filter(
                    SubtitleBuffer.channel_id == ch.id
                ).order_by(SubtitleBuffer.id.asc()).all()

                if not buffers:
                    logger.warning(f"No subtitle buffer chunks found for {ch.name}. Skipping summary.")
                    continue

                chunk_texts = [b.chunk_text for b in buffers if b.chunk_text]
                full_transcript = "\n\n".join(chunk_texts)

                # 2. Write consolidated full transcript to TXT file
                file_name = f"{ch.identifier}_{start_time.strftime('%Y%m%d_%H00')}.txt"
                file_path = os.path.join(settings.SUBTITLE_DIR, file_name)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(full_transcript)

                file_size = os.path.getsize(file_path)

                # Save SubtitleFile record
                sub_file = SubtitleFile(
                    channel_id=ch.id,
                    channel_identifier=ch.identifier,
                    file_name=file_name,
                    file_path=file_path,
                    file_size=file_size,
                    window_label=window_label,
                    transcript_text=full_transcript,
                    collected_at=now
                )
                db.add(sub_file)
                db.commit()
                db.refresh(sub_file)
                logger.info(f"Saved SubtitleFile record #{sub_file.id} for {ch.name}.")

                # 3. Call Gemini AI API for stock recommendations analysis
                logger.info(f"Invoking Gemini AI analysis for {ch.name}...")
                summary_text = GeminiService.generate_stock_summary(
                    channel_name=ch.name,
                    window_label=window_label,
                    transcript_text=full_transcript
                )

                summary_rec = Summary(
                    channel_id=ch.id,
                    subtitle_file_id=sub_file.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    summary_text=summary_text,
                    created_at=now
                )
                db.add(summary_rec)
                db.commit()
                logger.info(f"Saved Gemini AI Summary record #{summary_rec.id} for {ch.name}.")

                # 4. Clear consumed buffer chunks for this channel so next hour starts clean
                buffer_ids = [b.id for b in buffers]
                db.query(SubtitleBuffer).filter(SubtitleBuffer.id.in_(buffer_ids)).delete(synchronize_session=False)
                db.commit()
                logger.info(f"Cleared {len(buffer_ids)} consumed buffer chunks for {ch.name}.")

            except Exception as e:
                logger.error(f"Error finalizing hourly summary for {ch.name}: {e}")
                db.rollback()

    except Exception as e:
        logger.error(f"Error in hourly summary cycle: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("====================================================")
    logger.info(" Starting StockBS Hourly Summarizer Daemon Service ")
    logger.info("====================================================")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_hourly_summary_cycle,
        trigger=CronTrigger(minute=0),
        id="summarizer_hourly_job",
        replace_existing=True
    )

    try:
        logger.info("Summarizer daemon scheduler started. Waiting for minute 0 triggers...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Summarizer daemon stopped.")
