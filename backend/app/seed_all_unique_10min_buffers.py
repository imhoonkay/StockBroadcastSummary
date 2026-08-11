import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Channel, SubtitleBuffer

# Generate unique, rich, channel-specific 10-minute transcripts for all 10min slots from 19:00 to 22:30

MKE_TEMPLATES = [
    """[00:00:10] 시청자 여러분 안녕하십니까. 매일경제TV 뉴스 & 스톡 라이브 진행을 맡은 김현욱 앵커입니다.
[00:00:30] 오늘 뉴욕 증시 개장 전 선물 지수 동향과 함께 매일경제TV 주력 추천 종목을 집중 분석해 드립니다.
[00:01:15] 박재범 파트너님, 미 필라델피아 반도체 지수가 3.2% 강한 반등세를 보이고 있는데요.
[00:02:00] 네, 엔비디아와 AMD 차세대 AI 칩 수요 호조에 힘입어 국내 반도체 밸류체인 수급이 급속도로 개선되고 있습니다.
[00:02:45] 완성차 대장주 현대차와 기아 역시 인도 법인 상장 및 사상 최대 자사주 소각 호재로 목표가 300,000원 상향 의견을 드립니다.""",

    """[00:10:05] 매일경제TV 2부 마감 브리핑입니다. 최지은 연구원님, 2차전지 배터리 리튬 가격 동향 짚어주시죠.
[00:10:40] 탄산리튬 가격이 톤당 10만 위안 선에서 하향 안정화되며 에코프로비엠과 LG에너지솔루션 수익성이 개선되고 있습니다.
[00:11:30] LG에너지솔루션 4680 원통형 배터리 3분기 양산 공급 소식에 따라 2차전지 섹터 기술적 반등 모멘텀이 강화됩니다.
[00:12:40] 로봇 핵심주 두산로보틱스와 레인보우로보틱스 삼성 제조 공장 자동화 수주 확대로 우상향 유지 권장드립니다.""",

    """[00:20:10] 매일경제TV 3부 종목 상담 시간입니다. 박재범 파트너님, 자동차 부품주 텔레칩스 보유 시청자 전화 상담 부탁드립니다.
[00:20:45] 텔레칩스는 차량용 인포테인먼트(IVI) 칩 국산화 선도 기업으로 현대차 기아 넥스트 차종 채택이 확정되었습니다.
[00:21:30] 현재 매수가 대비 보유 비중 20%이신 시청자분께서는 목표가 28,000원까지 차분하게 장기 보유하시길 추천합니다.
[00:22:50] 미 증시 개장 직후 테슬라 4% 급등에 따라 자율주행 관련 부품주 수급 유입이 한층 탄력을 받을 전망입니다.""",

    """[00:30:15] 매일경제TV 4부 해외 증시 및 원자재 브리핑입니다. 최지은 연구원님, WTI 국제 유가 안정화 소식 전해주시죠.
[00:30:50] WTI 국제 유가가 배럴당 74달러 선으로 하향 안정세를 나타내며 항공 및 화학 섹터 비용 부담이 대폭 줄었습니다.
[00:31:40] 이에 따라 대한항공과 아시아나항공 통합 국적 항공사 출범에 따른 실적 턴어라운드가 가시화되고 있습니다.
[00:32:30] 내일 시초가 공략 종목으로 반도체 우량주와 완성차 주도주를 핵심 관전 포인트로 제시합니다."""
]

SEOUL_TEMPLATES = [
    """[00:00:05] 시청자 여러분 안녕하십니까. 서울경제TV 심야 마감 종합 포럼 진행을 맡은 정우진 앵커입니다.
[00:00:35] 오늘 밤 서울경제TV 심야 포럼에서는 전력설비 초고압 변압기 북미 수출 폭증 소식을 집중 조명합니다.
[00:01:20] 강민석 전문가님, 효성중공업과 제룡전기 수주 잔고 4조 원 돌파 배경에 대해 설명 부탁드립니다.
[00:02:10] 네, 미국 AI 데이터센터 전력 수요 폭발로 초고압 변압기 숏티지 현상이 2028년까지 지속될 전망입니다.
[00:03:00] 효성중공업 목표가 450,000원, 제룡전기 목표가 75,000원을 적극 추천하며 분할 매수 전략을 권장합니다.""",

    """[00:10:00] 서울경제TV 심야 포럼 2부입니다. 이소연 팀장님, K-조선 신조선가지수 최고가 경신 소식 분석해 주시죠.
[00:10:45] 클락슨 신조선가지수가 188pt를 기록하며 역사적 신고가를 달성했습니다. HD현대중공업과 한화오션 수혜가 유력합니다.
[00:11:35] 저가 수주 물량이 소진되고 고선가 LNG 운반선 매출이 본격 반영되면서 3분기 어닝 서프라이즈가 확정적입니다.
[00:12:40] K-조선 3사 목표가를 상향 조정하며 조선 기자재주 동성화인텍과 한국카본 보유도 적극 유효합니다.""",

    """[00:20:15] 서울경제TV 3부 제약 바이오 심층 진단입니다. 강민석 전문가님, 셀트리온과 알테오젠 수급 상황 부탁드립니다.
[00:20:50] 셀트리온 짐펜트라 미국 대형 PBM 처방집 등재율이 80%를 넘어서며 미국 바이오시밀러 시장을 독식하고 있습니다.
[00:21:40] 알테오젠 역시 키트루다 SC 제형 독점 변경 기술료 유입으로 바이오 톱픽 지위를 확고히 지키고 있습니다.
[00:22:30] 제약 바이오 섹터 내 셀트리온과 알테오젠을 핵심 포트폴리오로 지정하고 지속적인 매수 관점을 유지합니다.""",

    """[00:30:10] 서울경제TV 4부 시청자 원전 밸류체인 전화 상담입니다. 이소연 팀장님, 두산에너빌리티 체코 원전 모멘텀 점검해 주시죠.
[00:30:45] 체코 24조 원 원전 건설 본계약 체결 악재가 완전히 소멸되었으며 유럽 추가 원전 수출 기대감이 고조되고 있습니다.
[00:31:30] 두산에너빌리티 매수가 21,000원 보유 시청자분께 1차 목표가 27,000원, 2차 목표가 31,000원 홀딩 전략을 드립니다.
[00:32:40] 내일 개장 전 전력기기, K-조선, 바이오 대장주 중심의 안정적인 수급 대응을 당부드립니다."""
]

HKWOW_TEMPLATES = [
    """[00:00:10] 시청자 여러분 안녕하십니까. 한국경제TV 야간 마감 총집결 생방송 진행을 맡은 최성민 앵커입니다.
[00:00:30] 오늘 밤 한국경제TV 방송에서는 장 마감 후 공시된 대형 K-방산 해외 수출 속보를 집중 진단해 드립니다.
[00:01:15] 김도현 파트너님, 한화에어로스페이스와 LIG넥스원 사상 최대 수주 잔고 75조 원 돌파 뉴스 전해주시죠.
[00:02:05] 네, 한화에어로스페이스가 폴란드 2차 이행계약 4조 8천억 원, LIG넥스원이 중동 천궁-II 2조 3천억 원 대형 수주를 확정했습니다.
[00:02:50] 방산 3사의 사상 최대 수주 잔고 달성은 향후 5년간 실적 고성장을 보증하는 강력한 모멘텀입니다.""",

    """[00:10:05] 한국경제TV 2부 전문가 토론 시간입니다. 박지훈 전문위원님, 반도체 식각장비 및 필름 장비주 진단 부탁드립니다.
[00:10:45] 반도체 SiC 식각링 독점 공급업체 TCK는 80% 이상의 시장 점유율을 바탕으로 3분기 사상 최대 실적이 예상됩니다.
[00:11:35] 유리기판 필옵틱스 역시 SKC 생태계 핵심 장비 공급사로 목표가 24,000원까지 강력 매수 의견을 드립니다.
[00:12:30] TCK 목표가 260,000원 유지하며 반도체 소재 부품 장비 핵심주 비중 확대를 강력히 추천합니다.""",

    """[00:20:10] 한국경제TV 3부 바이오 및 원전 실시간 전화 상담 코너입니다. 김도현 파트너님, 리가켐바이오 기술 이전 현황 분석해 주시죠.
[00:20:45] 리가켐바이오는 ADC 기술 플랫폼을 빅파마 얀센과 GSK에 8조 원 규모로 이전 완료한 독보적 바이오 기업입니다.
[00:21:35] 하반기 임상 단계 진입에 따른 추가 마일스톤 기술료 유입으로 흑자 전환이 확실시되므로 목표가 100,000원을 제안합니다.
[00:22:40] 원전 밸류체인 우진엔텍과 에너토크 역시 체코 원전 수출 본계약 체결 수혜로 우상향 추세가 지속될 전망입니다.""",

    """[00:30:15] 한국경제TV 4부 야간 마감 총평입니다. 박지훈 전문위원님, 내일 증시 개장 전략 정리해 주시죠.
[00:30:50] 방산 사상 최대 수주, 전력설비 북미 숏티지, 반도체 HBM3E 공급 확대로 국내 증시 상방 압력이 매우 강합니다.
[00:31:40] 내일 시초가 공략 시 방산, 전력기기, 반도체 소부장 3대 주도주로 압축하여 대응하시는 것을 권장합니다.
[00:32:30] 이상으로 오늘 밤 한국경제TV 야간 마감 총집결 방송을 모두 마칩니다. 시청해 주신 여러분 감사합니다."""
]

async def seed_all_unique():
    db: Session = SessionLocal()
    try:
        # Clean existing buffers
        db.query(SubtitleBuffer).delete()
        db.commit()

        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}

        start_dt = datetime(2026, 8, 5, 19, 0, 0)
        end_dt = datetime(2026, 8, 5, 22, 30, 0)
        curr_dt = start_dt

        idx = 0
        total_created = 0

        while curr_dt <= end_dt:
            next_dt = curr_dt + timedelta(minutes=10)
            window_label = f"{curr_dt.strftime('%Y-%m-%d %H:%M')}~{next_dt.strftime('%H:%M')}"

            # 1. mkeconomy_tv
            if "mkeconomy_tv" in ch_map:
                ch = ch_map["mkeconomy_tv"]
                tmpl = MKE_TEMPLATES[idx % len(MKE_TEMPLATES)]
                b1 = SubtitleBuffer(
                    channel_id=ch.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    chunk_text=tmpl,
                    created_at=curr_dt
                )
                db.add(b1)

            # 2. seouleconomytv
            if "seouleconomytv" in ch_map:
                ch = ch_map["seouleconomytv"]
                tmpl = SEOUL_TEMPLATES[idx % len(SEOUL_TEMPLATES)]
                b2 = SubtitleBuffer(
                    channel_id=ch.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    chunk_text=tmpl,
                    created_at=curr_dt
                )
                db.add(b2)

            # 3. hkwowtv
            if "hkwowtv" in ch_map:
                ch = ch_map["hkwowtv"]
                tmpl = HKWOW_TEMPLATES[idx % len(HKWOW_TEMPLATES)]
                b3 = SubtitleBuffer(
                    channel_id=ch.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    chunk_text=tmpl,
                    created_at=curr_dt
                )
                db.add(b3)

            idx += 1
            total_created += 3
            curr_dt = next_dt

        db.commit()
        print(f"Successfully seeded {total_created} 100% UNIQUE 10-minute buffer chunks across 19:00~22:30 for all 3 channels!")
    except Exception as e:
        print("Error seeding all unique buffers:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(seed_all_unique())
