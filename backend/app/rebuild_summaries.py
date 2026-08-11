import asyncio
import logging
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import SubtitleFile, Summary, Channel
from app.services.gemini_service import GeminiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rebuild_summaries")

async def main():
    db: Session = SessionLocal()
    try:
        # 1. Clear all existing rows in summaries table
        logger.info("Wiping all existing summaries data clean...")
        deleted_count = db.query(Summary).delete()
        db.commit()
        logger.info(f"Successfully deleted {deleted_count} old summary records.")

        # 2. Get all subtitle files from database
        subtitle_files = db.query(SubtitleFile).order_by(SubtitleFile.id.asc()).all()
        logger.info(f"Found {len(subtitle_files)} subtitle file(s) to summarize.")

        channels = db.query(Channel).all()
        ch_map = {ch.id: ch.name for ch in channels}

        for index, sub in enumerate(subtitle_files, start=1):
            ch_name = ch_map.get(sub.channel_id, sub.channel_identifier)
            logger.info(f"[{index}/{len(subtitle_files)}] Summarizing subtitle file #{sub.id} ({ch_name} - {sub.window_label})...")

            summary_text = await GeminiService.summarize_transcript(
                channel_title=ch_name,
                window_label=sub.window_label,
                concatenated_transcript=sub.transcript_text
            )

            summary_rec = Summary(
                channel_id=sub.channel_id,
                subtitle_file_id=sub.id,
                channel_identifier=sub.channel_identifier,
                window_label=sub.window_label,
                summary_text=summary_text,
                created_at=sub.collected_at
            )
            db.add(summary_rec)
            db.commit()
            db.refresh(summary_rec)
            logger.info(f"Saved fresh Summary ID #{summary_rec.id} for {ch_name} ({sub.window_label})")

        logger.info("All AI summaries rebuilt clean from scratch successfully!")

    except Exception as e:
        logger.error(f"Error rebuilding summaries: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
