import os
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.config import settings
from app.models import Channel, SubtitleFile, Summary, SubtitleBuffer, get_kst_now
from app.services.youtube_service import YoutubeService
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def accumulate_10min_chunk(db: Session):
    """Collects 10-minute live subtitle chunks and appends into SubtitleBuffer."""
    now = get_kst_now()
    start_time = now.replace(minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    window_label = f"{start_time.strftime('%Y-%m-%d %H:00')}~{end_time.strftime('%H:00')}"

    channels = db.query(Channel).filter(Channel.status == "on").all()
    logger.info(f"Running 10-minute rolling buffer accumulation for {len(channels)} channel(s) ({window_label})...")

    for ch in channels:
        try:
            chunk = await YoutubeService.fetch_transcript(ch.url, ch.name, duration_sec=600)
            buf = SubtitleBuffer(
                channel_id=ch.id,
                channel_identifier=ch.identifier,
                window_label=window_label,
                chunk_text=chunk,
                created_at=now
            )
            db.add(buf)
            db.commit()
            logger.info(f"Appended 10-minute chunk for {ch.name} to SubtitleBuffer.")
        except Exception as e:
            logger.error(f"Error accumulating 10min chunk for {ch.name}: {e}")
            db.rollback()

async def run_hourly_collection_job():
    logger.info("Starting hourly channel subtitle collection and AI summary job...")
    db = SessionLocal()
    try:
        # 1. Accumulate latest chunk before finalize
        await accumulate_10min_chunk(db)
        # 2. Finalize hourly full transcript and generate AI summary
        await collect_and_summarize_all(db)
    except Exception as e:
        logger.error(f"Error during hourly collection job: {e}")
    finally:
        db.close()

async def collect_and_summarize_all(db: Session, channel_id: int = None):
    now = get_kst_now()
    # E.g. Window label for the past hour: 2026-08-04 20:00~21:00
    start_time = now.replace(minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=1)
    window_label = f"{start_time.strftime('%Y-%m-%d %H:00')}~{end_time.strftime('%H:00')}"

    query = db.query(Channel)
    if channel_id:
        query = query.filter(Channel.id == channel_id)
    else:
        query = query.filter(Channel.status == "on")

    channels = query.all()
    logger.info(f"Finalizing {len(channels)} channel(s) for window {window_label}...")

    os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

    results = []

    for channel in channels:
        try:
            # 1. Gather accumulated 10-minute buffer chunks from SubtitleBuffer
            buffers = db.query(SubtitleBuffer).filter(
                SubtitleBuffer.channel_identifier == channel.identifier,
                SubtitleBuffer.window_label == window_label
            ).order_by(SubtitleBuffer.created_at.asc()).all()

            if buffers:
                # Deduplicate and combine accumulated chunks
                combined_lines = []
                seen = set()
                for b in buffers:
                    for l in b.chunk_text.splitlines():
                        clean_l = l.strip()
                        if clean_l and clean_l not in seen:
                            seen.add(clean_l)
                            combined_lines.append(clean_l)
                raw_transcript = "\n".join(combined_lines)
            else:
                raw_transcript = await YoutubeService.fetch_transcript(channel.url, channel.name)

            date_str = start_time.strftime("%Y-%m-%d")
            start_time_str = start_time.strftime("%H:00")
            end_time_str = end_time.strftime("%H:00")

            # Process combined 1-hour raw STT using custom System & User Prompt Template
            formatted_transcript = await GeminiService.format_stt_transcript(
                channel_name=channel.name,
                date_str=date_str,
                start_time=start_time_str,
                end_time=end_time_str,
                raw_stt_data=raw_transcript
            )

            # Save clean formatted transcript to txt file
            file_timestamp = now.strftime("%Y%m%d_%H%M%S")
            file_name = f"{channel.identifier}_{file_timestamp}.txt"
            file_path = os.path.join(settings.SUBTITLE_DIR, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(formatted_transcript)

            file_size = os.path.getsize(file_path)

            # Save subtitle file record to database
            sub_file = SubtitleFile(
                channel_id=channel.id,
                channel_identifier=channel.identifier,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                window_label=window_label,
                transcript_text=formatted_transcript,
                collected_at=now
            )
            db.add(sub_file)
            db.commit()
            db.refresh(sub_file)

            # Generate Gemini AI summary
            logger.info(f"Generating Gemini summary for {channel.name}...")
            summary_text = await GeminiService.summarize_transcript(
                channel_title=channel.name,
                window_label=window_label,
                concatenated_transcript=formatted_transcript
            )

            # Save summary record to database
            summary_rec = Summary(
                channel_id=channel.id,
                subtitle_file_id=sub_file.id,
                channel_identifier=channel.identifier,
                window_label=window_label,
                summary_text=summary_text,
                created_at=now
            )
            db.add(summary_rec)
            db.commit()
            db.refresh(summary_rec)

            results.append({
                "channel": channel.name,
                "subtitle_file": file_name,
                "summary_id": summary_rec.id,
                "status": "success"
            })
        except Exception as e:
            logger.error(f"Failed to process channel {channel.name}: {e}")
            db.rollback()
            results.append({
                "channel": channel.name,
                "error": str(e),
                "status": "failed"
            })

    return results

async def scheduled_accumulate_job():
    db = SessionLocal()
    try:
        await accumulate_10min_chunk(db)
    finally:
        db.close()

async def scheduled_kospi200_macro_job():
    logger.info("Executing scheduled KOSPI 200 & Macro Indicators & AI Prediction Job (05:30 KST)...")
    db = SessionLocal()
    try:
        from app.services.kospi200_daemon import (
            fetch_top_200_kospi_stocks,
            update_kospi200_master,
            fetch_and_save_kospi200_daily,
            fetch_and_save_night_futures,
            fetch_and_save_macro_indicators,
            generate_and_save_kospi_prediction
        )
        stock_list = fetch_top_200_kospi_stocks()
        if stock_list:
            update_kospi200_master(db, stock_list)
            fetch_and_save_kospi200_daily(db, stock_list)
        fetch_and_save_night_futures(db)
        fetch_and_save_macro_indicators(db)
        generate_and_save_kospi_prediction(db)
        logger.info("Successfully completed 05:30 KST KOSPI 200 & Macro daily collection & AI prediction job.")
    except Exception as e:
        logger.error(f"Error during scheduled KOSPI 200 & Macro job: {e}")
    finally:
        db.close()

def start_scheduler():
    # YouTube 10-min FFmpeg audio capture is executed separately in dedicated stockbs_collector container.
    # In web backend, we only schedule the 05:30 KST daily KOSPI 200 & Macro AI prediction job.
    scheduler.add_job(
        func=scheduled_kospi200_macro_job,
        trigger=CronTrigger(hour=5, minute=30, timezone="Asia/Seoul"),
        id="kospi200_macro_daily_job",
        replace_existing=True
    )
    scheduler.start()
    logger.info("APScheduler started in backend for 05:30 KST KOSPI 200 & Macro daily job.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()


