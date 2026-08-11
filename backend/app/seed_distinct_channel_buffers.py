import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Channel, SubtitleBuffer

# Distinct, Channel-Specific 10-Minute Broadcast Speech Scripts for each channel
CHANNEL_SPECIFIC_10MIN_CHUNKS = {
    "hkwowtv": {
        "02:10": """[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 한국경제TV 야간 마감 총집결 생방송 진행을 맡은 앵커 최성민입니다.
[00:00:25] 오늘 밤 11시 한국경제TV에서는 장 마감 후 발표된 대형 방산 수주 속보와 글로벌 마켓 변수를 심층 분석해 드리겠습니다.
[00:01:10] 김도현 파트너님, 오늘 장 마감 직후 한화에어로스페이스와 LIG넥스원의 대형 해외 수주 공시가 발표되었는데요.
[00:01:40] 네, 한화에어로스페이스가 폴란드 국방부와 K2 전차 2차 이행계약 추가 물량 4조 8천억 원 공시를 등록했습니다.
[00:02:35] LIG넥스원 역시 중동향 천궁-II 2조 3천억 원 수출 계약을 체결하여 방산 3사 합산 수주 잔고가 75조 원을 돌파했습니다.""",

        "02:20": """[00:10:05] 한국경제TV 2부 순서입니다. 박지훈 파트너님, 미 필라델피아 반도체 지수 급등과 반도체 밸류체인 전망 부탁드립니다.
[00:10:45] 엔비디아 블랙웰 양산 호조로 삼성전자와 SK하이닉스 HBM3E 수혜가 집중되고 있습니다.
[00:11:50] 반도체 식각 장비 독점주 TCK 목표가 260,000원, 유리기판 필옵틱스 목표가 24,000원을 각각 상향 제안합니다.
[00:13:10] 제약 바이오 알테오젠 키트루다 SC 제형 플랫폼과 리가켐바이오 ADC 8조 원 기술 이전 모멘텀이 가파릅니다."""
    },

    "seouleconomytv": {
        "02:10": """[00:00:05] 시청자 여러분 안녕하십니까. 11시 서울경제TV 심야 마감 종합 포럼 진행을 맡은 앵커 정우진입니다.
[00:00:35] 오늘 밤 서울경제TV 포럼에서는 원달러 환율 1,320원대 하향 안정화와 전력설비 초고압 변압기 수출 호조를 집중 진단합니다.
[00:01:15] 강민석 전문가님, 효성중공업과 제룡전기의 북미 전력기기 수주 잔고 4조 원 돌파 소식 분석해 주시죠.
[00:02:00] 네, 미국 AI 데이터센터 전력 수요 폭발로 효성중공업의 2028년 납기 물량까지 계약이 마감된 상태입니다.
[00:02:45] 효성중공업 목표가 450,000원, 제룡전기 목표가 75,000원 분할 매수 의견을 드립니다.""",

        "02:20": """[00:10:00] 서울경제TV 심야 포럼 2부입니다. 바이오 대장주 셀트리온과 알테오젠 수급 동향을 살펴보겠습니다.
[00:10:40] 셀트리온 짐펜트라 미국 림프종 PBM 등재 확대에 따라 하반기 매출 급증이 확정적입니다.
[00:11:30] K-조선 HD현대중공업, 한화오션 신조선가지수 188pt 신고가 경신으로 고선가 매출 반영 어닝 서프라이즈 기대.
[00:12:45] 두산에너빌리티 체코 원전 본계약 악재 소멸에 따른 원전 밸류체인 우상향 추세를 적극 권장합니다."""
    },

    "mkeconomy_tv": {
        "02:10": """[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 매일경제TV 내일 개장 전 마감 총집결 생방송 진행을 맡은 앵커 김현욱입니다.
[00:00:40] 매일경제TV 오늘 밤 방송에서는 미 나스닥 1.35% 폭등과 자동차 완성차 현대차, 기아 실적 호재를 점검합니다.
[00:01:20] 박재범 파트너님, 현대차 기아 사상 최대 실적 및 자사주 소각 주주환원 호재 분석 부탁드립니다.
[00:02:10] 네, 현대차 인도 법인 상장 모멘텀과 기아 EV3 글로벌 판매 호조로 3분기 주주환원 수익률이 극대화될 것입니다.
[00:03:00] 차량용 반도체 텔레칩스 및 완성차 현대차 300,000원 목표가 홀딩 전략을 추천합니다.""",

        "02:20": """[00:10:15] 매일경제TV 2부에서는 이차전지 배터리 밸류체인 및 수급 반등 가능성을 점검해 보겠습니다.
[00:11:00] LG에너지솔루션 4680 원통형 배터리 3분기 공급 개시와 에코프로비엠 리튬 가격 하향 안정화 수혜.
[00:12:10] 로봇 핵심주 두산로보틱스, 레인보우로보틱스 삼성 현대 제조 공장 자동화 수주 확대로 우상향 유지.
[00:13:30] 내일 아침 개장 시 반도체, 완성차, 전력기기 주도주 위주의 시초가 분할 매수를 강력 제안합니다."""
    }
}

async def seed_distinct():
    db: Session = SessionLocal()
    try:
        db.query(SubtitleBuffer).delete()
        db.commit()

        channels = db.query(Channel).filter(Channel.status == "on").all()
        ch_map = {ch.identifier: ch for ch in channels}
        window_label = "2026-08-05 02:00~03:00"

        for ch_ident, time_dict in CHANNEL_SPECIFIC_10MIN_CHUNKS.items():
            ch = ch_map.get(ch_ident)
            if not ch:
                continue

            for time_key, dialogue_text in time_dict.items():
                dt_obj = datetime.strptime(f"2026-08-05 {time_key}:00", "%Y-%m-%d %H:%M:%S")
                buf = SubtitleBuffer(
                    channel_id=ch.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    chunk_text=dialogue_text,
                    created_at=dt_obj
                )
                db.add(buf)

        db.commit()
        print("Seeded DISTINCT channel-specific 10-minute buffers successfully!")
    except Exception as e:
        print("Error seeding distinct buffers:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(seed_distinct())
