import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Channel, SubtitleBuffer

async def seed_buffers():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).filter(Channel.status == "on").all()
        window_label = "2026-08-05 02:00~03:00"

        sample_chunks = {
            "hkwowtv": [
                ("[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 한국경제TV 야간 마감 총집결 생방송 진행을 맡은 앵커 최성민입니다.\n"
                 "[00:00:25] 오늘 밤 11시 방송에서는 오늘 장 마감 후 발표된 주요 기업들의 대형 수주 공시를 점검하겠습니다.\n"
                 "[00:01:40] 한화에어로스페이스가 폴란드 국방부와 체결한 K2 전차 2차 이행계약 추가 물량 4조 8천억 원 공시가 발표되었습니다.",
                 datetime.strptime("2026-08-05 02:10:00", "%Y-%m-%d %H:%M:%S")),
                ("[00:10:15] 이어서 밤 11시 15분, 2부 주요 섹터 및 우량주 진단 코너로 넘어가 보겠습니다.\n"
                 "[00:12:30] 반도체 식각 장비 독점주 TCK, 유리기판 필옵틱스 수급 유입이 집중되고 있습니다.",
                 datetime.strptime("2026-08-05 02:20:00", "%Y-%m-%d %H:%M:%S"))
            ],
            "mkeconomy_tv": [
                ("[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 매일경제TV 마감 총집결 생방송 앵커 김현욱입니다.\n"
                 "[00:01:10] 미 증시 필라델피아 반도체 지수가 3% 넘게 급등 중입니다.",
                 datetime.strptime("2026-08-05 02:10:00", "%Y-%m-%d %H:%M:%S")),
                ("[00:10:20] 자동차 섹터 텔레칩스 및 완성차 현대차, 기아의 사상 최대 실적 호재 지속.",
                 datetime.strptime("2026-08-05 02:20:00", "%Y-%m-%d %H:%M:%S"))
            ],
            "seouleconomytv": [
                ("[00:00:05] 11시 서울경제TV 심야 마감 종합 포럼 앵커 정우진입니다.\n"
                 "[00:01:25] 효성중공업과 제룡전기 초고압 변압기 북미 수출 폭증으로 수주 잔고 4조 원을 돌파했습니다.",
                 datetime.strptime("2026-08-05 02:10:00", "%Y-%m-%d %H:%M:%S")),
                ("[00:10:15] 바이오 대장주 알테오젠과 리가켐바이오 외국인 순매수가 가파르게 늘어나고 있습니다.",
                 datetime.strptime("2026-08-05 02:20:00", "%Y-%m-%d %H:%M:%S"))
            ]
        }

        for ch in channels:
            chunks = sample_chunks.get(ch.identifier, [])
            for text_chunk, dt_time in chunks:
                buf = SubtitleBuffer(
                    channel_id=ch.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    chunk_text=text_chunk,
                    created_at=dt_time
                )
                db.add(buf)
        db.commit()
        print("Sample 10-minute rolling buffer chunks seeded successfully!")
    except Exception as e:
        print("Error seeding buffers:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(seed_buffers())
