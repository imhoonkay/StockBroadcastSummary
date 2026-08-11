import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Channel, SubtitleBuffer

async def seed_continuous():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).filter(Channel.status == "on").all()

        # Seed 10-minute slots continuously from 02:30 up to 05:10
        timestamps = [
            ("2026-08-05 02:00~03:00", "2026-08-05 02:30:00", "[00:20:10] 대구 시청자 전화 상담: 두산에너빌리티 21,000원 매수가 30% 비중 체코 원전 본계약 기대감."),
            ("2026-08-05 02:00~03:00", "2026-08-05 02:40:00", "[00:30:15] 대전 시청자 전화 상담: 리가켐바이오 65,000원 매수가 25% 비중 ADC 기술 이전 마일스톤 유입."),
            ("2026-08-05 02:00~03:00", "2026-08-05 02:50:00", "[00:40:20] 전력설비 효성중공업, 제룡전기 북미 초고압 변압기 수출 폭증 모멘텀 지속."),

            ("2026-08-05 03:00~04:00", "2026-08-05 03:10:00", "[00:00:05] 새벽 3시 마감특보 한국경제TV 생방송 진행을 맡은 앵커 최성민입니다."),
            ("2026-08-05 03:00~04:00", "2026-08-05 03:20:00", "[00:10:15] 글로벌 증시 엔비디아 4% 급등 모멘텀으로 반도체 밸류체인 수급 집중."),
            ("2026-08-05 03:00~04:00", "2026-08-05 03:30:00", "[00:20:25] K-조선 HD현대중공업, 한화오션 클락슨 신조선가지수 188pt 경신 어닝 서프라이즈."),
            ("2026-08-05 03:00~04:00", "2026-08-05 03:40:00", "[00:30:35] 부산 시청자 전화 상담: 효성중공업 350,000원 매수가 20% 비중 목표가 450,000원 제시."),
            ("2026-08-05 03:00~04:00", "2026-08-05 03:50:00", "[00:40:45] K-방산 한화에어로스페이스, LIG넥스원 해외 수주 잔고 75조 원 돌파 소식."),

            ("2026-08-05 04:00~05:00", "2026-08-05 04:10:00", "[00:00:05] 새벽 4시 마감 종합 포럼 방송을 시작합니다."),
            ("2026-08-05 04:00~05:00", "2026-08-05 04:20:00", "[00:10:15] 미국 연준 금리 인하 기대감으로 원달러 환율 1,320원 하향 안정화."),
            ("2026-08-05 04:00~05:00", "2026-08-05 04:30:00", "[00:20:25] 바이오 대장주 알테오젠 키트루다 SC 제형 독점 공급 재평가."),
            ("2026-08-05 04:00~05:00", "2026-08-05 04:40:00", "[00:30:35] 광주 시청자 전화 상담: TCK 190,000원 매수가 15% 비중 추가 매수 및 목표가 260,000원."),
            ("2026-08-05 04:00~05:00", "2026-08-05 04:50:00", "[00:40:45] 체코 원전 수혜주 두산에너빌리티 본계약 체결 악재 소멸 장기 보유 권장."),

            ("2026-08-05 05:00~06:00", "2026-08-05 05:10:00", "[00:00:10] 아침 개장 전 5시 마감 특보 10분 수집 버퍼를 기록합니다.")
        ]

        for window_label, dt_str, chunk_tmpl in timestamps:
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            for ch in channels:
                text_content = chunk_tmpl.replace("한국경제TV", ch.name)
                buf = SubtitleBuffer(
                    channel_id=ch.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    chunk_text=text_content,
                    created_at=dt_obj
                )
                db.add(buf)

        db.commit()
        print("Continuous 10-minute rolling buffer records seeded successfully!")
    except Exception as e:
        print("Error seeding continuous buffers:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(seed_continuous())
