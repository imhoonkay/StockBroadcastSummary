import asyncio
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.config import settings
from app.models import Channel, SubtitleFile, Summary
from app.services.gemini_service import GeminiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("add_ad_and_nonstock_slots")

NON_STOCK_SLOTS = {
    "12:00~13:00": {
        "mkeconomy_tv": """[매일경제TV 12:00~13:00 건강 100세 시대 스페셜 & 하이라이트 자막 전문]
00:00:10 [MC] 시청자 여러분 안녕하십니까. 100세 건강시대 진행을 맡은 아나운서입니다.
00:02:00 [전문가] 오늘은 관절 건강과 무릎 연골 관리를 위한 관절보궁 및 한방 요법에 대해 자세히 알아보겠습니다.
00:15:00 [광고] [기업 PR 광고] 프리미엄 관절 영양제 1+1 특별 이벤트 안내. 문의전화 080-123-4567.
00:25:00 [전문가] 퇴행성 관절염 예방을 위해서는 매일 30분씩 가벼운 산책과 유산소 운동이 필수적입니다.
00:40:00 [MC] 100세 건강시대 오늘 방송 마칩니다. 시청해 주신 여러분 감사합니다.""",

        "seouleconomytv": """[서울경제TV 12:00~13:00 기업 PR 및 하이라이트 컬렉션 자막 전문]
00:00:15 [안내] 본 방송은 서울경제TV 기업 홍보 및 인포머셜 하이라이트 시간입니다.
00:05:00 [광고] 친환경 전기차 충전 인프라 솔루션 기업 홍보 영상입니다.
00:20:00 [광고] 스마트팜 데이터 기반 자동화 영농 시스템 소개.
00:40:00 [안내] 서울경제TV 기업 PR 하이라이트 방송을 마칩니다.""",

        "hkwowtv": """[한국경제TV 12:00~13:00 부동산 재테크 및 자산 관리 가이드 자막 전문]
00:00:10 [MC] 부동산 재테크 가이드 12시 방송입니다.
00:05:00 [전문가] 수도권 광역교통망(GTX-A) 개통에 따른 인근 주거 단지 임대 수익률 분석을 진행합니다.
00:20:00 [전문가] 주택 수 계산 및 상가 임대차 보호법 관련 법률 가이드 안내.
00:40:00 [MC] 부동산 재테크 가이드 오늘 순서 마칩니다."""
    }
}

async def main():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}

        for slot_label, slot_content in NON_STOCK_SLOTS.items():
            window_label = f"2026-08-04 {slot_label}"
            hour_str = slot_label.split(":")[0]
            collected_dt = datetime.strptime(f"2026-08-04 {hour_str}:00:00", "%Y-%m-%d %H:%M:%S")

            for ch_ident, transcript_text in slot_content.items():
                ch = ch_map.get(ch_ident)
                if not ch:
                    continue

                file_ts = collected_dt.strftime("%Y%m%d_%H%M%S")
                file_name = f"{ch.identifier}_{file_ts}.txt"
                file_path = os.path.join(settings.SUBTITLE_DIR, file_name)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(transcript_text)

                file_size = os.path.getsize(file_path)

                sub_file = db.query(SubtitleFile).filter(
                    SubtitleFile.channel_identifier == ch.identifier,
                    SubtitleFile.window_label == window_label
                ).first()

                if not sub_file:
                    sub_file = SubtitleFile(
                        channel_id=ch.id,
                        channel_identifier=ch.identifier,
                        file_name=file_name,
                        file_path=file_path,
                        file_size=file_size,
                        window_label=window_label,
                        transcript_text=transcript_text,
                        collected_at=collected_dt
                    )
                    db.add(sub_file)
                    db.commit()
                    db.refresh(sub_file)
                else:
                    sub_file.transcript_text = transcript_text
                    sub_file.file_size = file_size
                    db.commit()

                summary_text = await GeminiService.summarize_transcript(
                    channel_title=ch.name,
                    window_label=window_label,
                    concatenated_transcript=transcript_text
                )

                summary_rec = db.query(Summary).filter(Summary.subtitle_file_id == sub_file.id).first()
                if not summary_rec:
                    summary_rec = Summary(
                        channel_id=ch.id,
                        subtitle_file_id=sub_file.id,
                        channel_identifier=ch.identifier,
                        window_label=window_label,
                        summary_text=summary_text,
                        created_at=collected_dt
                    )
                    db.add(summary_rec)
                else:
                    summary_rec.summary_text = summary_text

                db.commit()
                logger.info(f"Updated non-stock slot for {ch.name} ({window_label})")

    except Exception as e:
        logger.error(f"Error adding non-stock slots: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
