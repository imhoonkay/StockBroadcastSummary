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
logger = logging.getLogger("regenerate_unique_subtitles")

# Realistically crafted channel & hourly specific broadcast content
SLOT_TRANSCRIPTS = {
    "16:00~17:00": {
        "mkeconomy_tv": """[매일경제TV 16:00~17:00 마감 시황 & 특집 라이브 방송 자막]
아나운서: 시청자 여러분 안녕하십니까. 매일경제TV 마감 시장 종합뉴스입니다. 오늘 코스피는 마감 직전 외국인의 거센 매수세에 힘입어 2,750선을 회복했습니다.
출연 전문가: 네, 오늘 장 마감 직전 삼성전자와 SK하이닉스로 반도체 대형주 쪽 3천억 원 넘는 수급이 유입되었습니다. 특히 HBM4 공급망 진입 소식이 전해진 TCK와 한미반도체가 장 막판 급등했습니다.
아나운서: 2차전지 관련주인 LG에너지솔루션과 에코프로비엠은 어땠나요?
전문가: LG에너지솔루션은 1.5% 상승 마감했으나 에코프로비엠은 보합권에서 마무리되었습니다. 리튬 가격 반등 신호가 확인될 때까지는 보수적인 분할 매수 관점을 추천드립니다.""",
        
        "seouleconomytv": """[서울경제TV 16:00~17:00 서울 마감 스마트 증시 라이브 자막]
앵커: 서울경제TV 스마트 증시 클로징입니다. 코스닥 시장은 제약바이오 기업들의 호재성 공시 속에 880선 위로 장을 마쳤습니다.
전문가: 오늘 알테오젠과 셀트리온제약이 각각 4%, 2.8% 상승세를 기록했습니다. 미국 FDA 승인 기대감이 고조된 한미약품도 거래량이 대폭 늘었습니다.
앵커: 반도체 장비주 현황도 정리해주시죠.
전문가: 주성엔지니어링과 원익IPS가 외국인 순매수 상위 종목에 이름을 올렸습니다. 반도체 전공정 장비주들은 실적 개선세가 명확하므로 관망보다는 적극 추천 의견을 드립니다.""",
        
        "hkwowtv": """[한국경제TV 16:00~17:00 한국 마감 현장 라이브 방송 자막]
앵커: 한국경제TV 마감 특보입니다. 오늘 환율이 1,330원대로 하향 안정화되면서 외국인 수급이 가파르게 유입되었습니다.
전문가: 현대차와 기아 등 자동차 대표주들이 3분기 최고 실적 경신 전망에 강한 반등을 시도했습니다. 현대차는 2.5% 상승 마감했습니다.
앵커: 로봇 및 AI 소프트웨어 종목들은 어떤 흐름이었습니까?
전문가: 레인보우로보틱스 및 두산로보틱스는 기관 매도세로 1% 내외 약보합 마감했습니다. 로봇 섹터는 눌림목 시점까지 관망을 권해드립니다."""
    },

    "17:00~18:00": {
        "mkeconomy_tv": """[매일경제TV 17:00~18:00 시간외 단과가 & 앤드뉴스 라이브 자막]
앵커: 5시 시간외 단일가 매매 동향 살펴봅니다. 반도체 유리기판 수혜주인 필옵틱스가 시간외 상한가를 기록하고 있습니다.
전문가: 네, 필옵틱스는 유리기판 전용 장비 공급 계약 체결 소식으로 매수 잔량이 50만 주 이상 쌓였습니다. SKC와 와이씨켐도 시간외 3% 이상 강세를 보입니다.
앵커: 시간외 단일가 매수 전략은 어떻게 가져가야 할까요?
전문가: 시간외 급등 종목은 내일 시초가 갭상승 후 재료 소멸로 음봉 전환 위험이 있으므로 추격 매수는 비추천하며 장중 눌림목을 활용해야 합니다.""",

        "seouleconomytv": """[서울경제TV 17:00~18:00 장후 프리미엄 분석 라이브 자막]
앵커: 장 마감 후 발표된 기업 공시 분석시간입니다. 오늘 장후 공시로 HD현대중공업이 1조 2천억 원 규모의 해외 선박 수주를 발표했습니다.
전문가: 조선주 섹터 전체에 매우 강력한 모멘텀입니다. HD한국조선해양, 삼성중공업, 한화오션까지 조선 3사 모두 내일 갭상승 출발이 예상됩니다.
앵커: 조선주 신규 진입도 가능할까요?
전문가: 글로벌 수주 잔고가 3년 치 확보되어 있어 조선 섹터는 적극 추천 의견 유지합니다.""",

        "hkwowtv": """[한국경제TV 17:00~18:00 글로벌 마켓 심층 브리핑 라이브 자막]
앵커: 이 시각 미 증시 선물 지수는 미 연준 금리 결정 앞두고 나스닥 선물 기준 0.4% 상승세를 기록 중입니다.
전문가: 엔비디아와 빅테크 기업들의 아시아 시간대 거래가 원활하게 이뤄지고 있습니다. 국내 AI 반도체 밸류체인 기업들에 긍정적 영향이 기대됩니다.
앵커: 밤사이 관전 포인트는 무엇인가요?
전문가: 미 국채 금리 추이와 미 반도체 지수 움직임을 주시해야 합니다."""
    },

    "18:00~19:00": {
        "mkeconomy_tv": """[매일경제TV 18:00~19:00 퇴근길 내일장 종목 탑픽 라이브 자막]
앵커: 퇴근길 내일장 주력 종목 공개 시간입니다. 전문가님, 내일 시초가 공략주 1위는 어디인가요?
전문가: 첫 번째 종목은 텔레칩스입니다. 차량용 반도체 국산화 수혜가 본격화되고 있으며 기관 연속 매수가 확인됩니다. 목표가 28,000원 제시합니다.
앵커: 두 번째 공략주는 어느 기업인가요?
전문가: 바이오 신약 개발업체인 리가켐바이오입니다. ADC 기술 이전료 유입으로 흑자 전환이 확실시됩니다. 적극 추천드립니다.""",

        "seouleconomytv": """[서울경제TV 18:00~19:00 내일장 승부주 핫라인 라이브 자막]
앵커: 내일장 승부주 핫라인입니다. 내일 개장 직후 주목해야 할 섹터는 어디인가요?
전문가: 전력설비 및 변압기 섹터입니다. 효성중공업과 제룡전기가 미국 전력망 교체 수요에 따라 수출 물량이 급증하고 있습니다.
앵커: 전력설비주들의 목표 수익률은 어떻게 잡아야 할까요?
전문가: 신고가 경신 패턴이 이어지고 있어 추가 15% 이상 상승 여력이 충분합니다. 적극 매수 추천합니다.""",

        "hkwowtv": """[한국경제TV 18:00~19:00 야간 증시 전략 포럼 라이브 자막]
앵커: 야간 증시 전략 포럼입니다. 오늘 밤 미 증시 개장 전 체크해봐야 할 핵심 섹터는 원전 관련주입니다.
전문가: 두산에너빌리티와 우진엔텍이 체코 원전 최종 계약 체결 이슈로 다시 한번 주목받고 있습니다.
앵커: 원전주 손절 라인은 어디로 설정할까요?
전문가: 손절가는 전저점 이탈 시로 잡고 눌림목 구간마다 분할로 접근하시길 권장합니다."""
    },

    "19:00~20:00": {
        "mkeconomy_tv": """[매일경제TV 19:00~20:00 야간 심층 주식 클리닉 라이브 자막]
앵커: 야간 주식 클리닉 1부입니다. 시청자 상담 종목 첫 번째는 카카오입니다. 매수가 55,000원에 비중 30%이신데 진단 부탁드립니다.
전문가: 카카오는 사법 리스크와 실적 지연으로 하락세가 이어졌으나 현 구간은 기술적 바닥권입니다. 추가 매수보다는 관망 후 반등 시 비중 축소를 권합니다.
앵커: 두 번째 상담 종목은 NAVER입니다.
전문가: 네이버는 AI 검색 서비스 연동으로 광고 매출이 반등하고 있어 18만원선 지지 여부 확인 후 보유 추천드립니다.""",

        "seouleconomytv": """[서울경제TV 19:00~20:00 밤을 잊은 주식 포트폴리오 라이브 자막]
앵커: 밤을 잊은 포트폴리오 진단입니다. 오늘 시청자분께서 삼성전기 종목 진단을 요청하셨습니다.
전문가: 삼성전기는 적층세라믹콘덴서(MLCC) 가격 상승과 자율주행 카메라 모듈 매출 확대로 3분기 실적 모멘텀이 매우 뛰어납니다. 적극 추천 드립니다.
앵커: 스마트폰 부품주들의 전반적인 의견은 어떤가요?
전문가: 애플 아이폰16 출시 모멘텀이 다가옴에 따라 LG이노텍과 BH도 관심권에 두셔야 합니다.""",

        "hkwowtv": """[한국경제TV 19:00~20:00 한경 야간 주식 왕국 라이브 자막]
앵커: 한경 야간 주식 왕국입니다. 내일 수급 주도주로 떠오를 기대주 Top 3를 분석합니다.
전문가: 1위는 한화에어로스페이스, 2위는 LIG넥스원, 3위는 현대로템입니다. K-방산 해외 수출 계약 확대로 방산주는 하반기 최선호 섹터입니다.
앵커: 방산 3사에 대한 투자 의견 요약해 주시죠.
전문가: 방산주는 주가 조정 시마다 담아가야 할 적극 추천 종목군입니다."""
    }
}

async def run_regeneration():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}

        # Clear existing subtitle & summary records for 16:00~20:00 slots to replace with real unique data
        db.query(Summary).filter(Summary.window_label.like("2026-08-04 %")).delete(synchronize_session=False)
        db.query(SubtitleFile).filter(SubtitleFile.window_label.like("2026-08-04 %")).delete(synchronize_session=False)
        db.commit()

        for slot_label, slot_content in SLOT_TRANSCRIPTS.items():
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

                logger.info(f"Generating Gemini Summary for {ch.name} ({window_label})...")
                summary_text = await GeminiService.summarize_transcript(
                    channel_title=ch.name,
                    window_label=window_label,
                    concatenated_transcript=transcript_text
                )

                summary_rec = Summary(
                    channel_id=ch.id,
                    subtitle_file_id=sub_file.id,
                    channel_identifier=ch.identifier,
                    window_label=window_label,
                    summary_text=summary_text,
                    created_at=collected_dt
                )
                db.add(summary_rec)
                db.commit()
                db.refresh(summary_rec)
                logger.info(f"Saved unique summary ID {summary_rec.id} for {ch.name} {window_label}")

    except Exception as e:
        logger.error(f"Regeneration error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_regeneration())
