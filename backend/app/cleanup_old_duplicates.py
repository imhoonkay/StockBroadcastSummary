import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import SubtitleFile, Summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanup_old_duplicates")

def cleanup():
    db: Session = SessionLocal()
    try:
        # Delete old temporary test records containing '%00' or default generic placeholder header
        old_subs = db.query(SubtitleFile).filter(
            (SubtitleFile.window_label.like("%:%00%")) |
            (SubtitleFile.transcript_text.like("%[매일경제TV 유튜브 라이브 방송 1시간 실시간 수집 녹취록]%"))
        ).all()

        logger.info(f"Found {len(old_subs)} old test records to remove.")
        
        for sub in old_subs:
            # Delete corresponding summary
            db.query(Summary).filter(Summary.subtitle_file_id == sub.id).delete()
            db.delete(sub)

        db.commit()
        logger.info("Cleanup completed successfully!")

    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
