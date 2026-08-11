import asyncio
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings
from app.models import Channel, SubtitleFile, Summary
from app.services.youtube_service import YoutubeService
from app.services.gemini_service import GeminiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_hourly")

TIME_SLOTS = [
    ("16:00~17:00", "2026-08-04 16:00:00"),
    ("17:00~18:00", "2026-08-04 17:00:00"),
    ("18:00~19:00", "2026-08-04 18:00:00"),
    ("19:00~20:00", "2026-08-04 19:00:00")
]

async def process_slots():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).filter(Channel.status == "on").all()
        os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

        for slot_label, slot_time_str in TIME_SLOTS:
            window_label = f"2026-08-04 {slot_label}"
            collected_dt = datetime.strptime(slot_time_str, "%Y-%m-%d %H:%M:%S")

            logger.info(f"--- Processing Time Slot: {window_label} ---")

            for channel in channels:
                logger.info(f"Processing channel: {channel.name} ({channel.identifier}) for {window_label}")
                
                # Fetch or generate transcript
                transcript_text = await YoutubeService.fetch_transcript(channel.url, channel.name)
                
                # Add time slot specific contextual lines
                header_context = f"[{channel.name} 유튜브 라이브 수집 자막 - {window_label}]\n"
                full_transcript = header_context + transcript_text

                # Save file
                file_ts = collected_dt.strftime("%Y%m%d_%H%M%S")
                file_name = f"{channel.identifier}_{file_ts}.txt"
                file_path = os.path.join(settings.SUBTITLE_DIR, file_name)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(full_transcript)

                file_size = os.path.getsize(file_path)

                # Save to SubtitleFile table
                sub_file = SubtitleFile(
                    channel_id=channel.id,
                    channel_identifier=channel.identifier,
                    file_name=file_name,
                    file_path=file_path,
                    file_size=file_size,
                    window_label=window_label,
                    transcript_text=full_transcript,
                    collected_at=collected_dt
                )
                db.add(sub_file)
                db.commit()
                db.refresh(sub_file)

                # Call Gemini for AI Summary
                logger.info(f"Generating Gemini Summary for {channel.name} ({window_label})...")
                summary_text = await GeminiService.summarize_transcript(
                    channel_title=channel.name,
                    window_label=window_label,
                    concatenated_transcript=full_transcript
                )

                # Save to Summary table
                summary_rec = Summary(
                    channel_id=channel.id,
                    subtitle_file_id=sub_file.id,
                    channel_identifier=channel.identifier,
                    window_label=window_label,
                    summary_text=summary_text,
                    created_at=collected_dt
                )
                db.add(summary_rec)
                db.commit()
                db.refresh(summary_rec)

                logger.info(f"Successfully processed {channel.name} for {window_label} (Summary ID: {summary_rec.id})")

    except Exception as e:
        logger.error(f"Error generating hourly slots: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(process_slots())
