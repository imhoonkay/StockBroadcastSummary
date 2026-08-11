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
logger = logging.getLogger("generate_night_slots")

NIGHT_SLOTS = {
    "20:00~21:00": {
        "mkeconomy_tv": """[매일경제TV 20:00~21:00 야간 해외 증시 & 미 연준 특보 라이브 실시간 녹취록 전문]
00:00:10 [아나운서] 시청자 여러분 안녕하십니까. 매일경제TV 8시 야간 글로벌 마켓 특보입니다.
00:01:20 [앵커] 이 시각 미 증시 개장 전 개장전 선물 지수는 나스닥 0.5% 상승, S&P 500 0.3% 상승세를 기록하고 있습니다.
00:05:00 [전문가 A] 미 연준 금리 결정을 앞두고 유가 하락 및 국채 금리 안정세로 빅테크 기술주 수급이 강력히 재유입되고 있습니다.
00:12:30 [전문가 B] 특히 엔비디아와 마이크론의 아시아 서버 시장 점유율 확대 전망에 따라 국내 반도체 소재 장비주인 TCK, 필옵틱스, 리노공업에 수급 모멘텀이 집중되고 있습니다.
00:25:00 [종목 진단] 시청자 질문: "TCK 230,000원에 보유 중인데 20시 미 증시 선물 반등에 맞춰 목표가 상향 가능한가요?"
00:27:00 [전문가 A] TCK는 SiC 식각링 시장 독점 지위로 인해 실적 고성장이 보장됩니다. 270,000원까지 목표가 상향 제시하며 적극 추천 유지합니다.
00:40:00 [아나운서] 8시 방송 요약해 드립니다. 반도체 밸류체인 및 글로벌 수혜주 위주의 안정적 보유 전략을 제안합니다.""",

        "seouleconomytv": """[서울경제TV 20:00~21:00 밤 8시 주식 포트폴리오 메디컬 라이브 실시간 녹취록 전문]
00:00:15 [앵커] 서울경제TV 밤 8시 주식 포트폴리오 메디컬입니다.
00:03:00 [전문가] 바이오 섹터 내에서 피하주사(SC) 제형 변경 독점 기술을 보유한 알테오젠과 통합 시너지가 가시화된 셀트리온제약이 야간 수급 지표 상위에 유입되고 있습니다.
00:15:00 [앵커] 바이오주 상반기 대비 하반기 이익 모멘텀은 어떤가요?
00:18:20 [전문가] 글로벌 기술 이전 수수료 유입이 본궤도에 오른 리가켐바이오와 알테오젠은 적극 추천 투자의견을 드립니다.
00:35:00 [종목 진단] 한미약품 비만 치료제 국내 임상 3상 가속화 호재 분석. 적극 보유 권장.""",

        "hkwowtv": """[한국경제TV 20:00~21:00 한경 8시 글로벌 머니 쇼 라이브 실시간 녹취록 전문]
00:00:10 [앵커] 한경 8시 글로벌 머니 쇼입니다. 원달러 환율 1,320원대 하향 안정세 속 외국인 야간 수급 동향을 점검합니다.
00:04:00 [전문가] 조선주 섹터 선가 상승으로 HD현대중공업 및 한화오션의 하반기 영업이익률이 10%를 돌파할 것으로 기대됩니다.
00:20:00 [앵커] 조선주 신규 매수 타이밍은 언제로 보시나요?
00:22:00 [전문가] HD현대중공업과 HD한국조선해양은 갭상승 이후 눌림목이 올 때마다 분할로 담아가는 적극 추천 전략이 유효합니다."""
    },

    "21:00~22:00": {
        "mkeconomy_tv": """[매일경제TV 21:00~22:00 미 증시 개장 실시간 중계 라이브 실시간 녹취록 전문]
00:00:05 [앵커] 9시 30분 미 증시 본장 개장 실시간 방송입니다. 다우지수 +0.3%, 나스닥지수 +0.7% 강세 출발했습니다.
00:03:30 [전문가] 엔비디아와 마이크로소프트가 개장 직후 2% 이상 갭상승하며 반도체 지수를 강하게 끌어올리고 있습니다.
00:15:00 [앵커] 국내 반도체 관련주들에 미치는 영향은 어떠한가요?
00:17:40 [전문가] 삼성전자, SK하이닉스 ADR 주가가 2.5% 동반 상승 중입니다. 내일 한국 증시 개장 직후 갭상승이 확실시됩니다.
00:38:00 [앵커] 내일 아침 시초가 공략 종목으로 유리기판 수혜주 필옵틱스와 SKC를 적극 추천합니다.""",

        "seouleconomytv": """[서울경제TV 21:00~22:00 9시 전력 & AI 밸류체인 심층 리포트 실시간 녹취록 전문]
00:00:10 [앵커] 9시 전력 및 AI 데이터센터 밸류체인 심층 리포트입니다.
00:04:00 [전문가] 미국 전력망 교체 및 AI 변압기 수주가 폭증하고 있는 효성중공업과 제룡전기가 9시 야간 시장에서 큰 관심을 받고 있습니다.
00:20:00 [앵커] 전력주 목표가 상향 여력은 어느 정도인가요?
00:22:30 [전문가] 효성중공업은 북미 현지 공장 증설 효과로 추가 20% 이상 주가 상승 여력이 충분합니다. 적극 매수 추천합니다.""",

        "hkwowtv": """[한국경제TV 21:00~22:00 9시 K-방산 글로벌 수주 특보 라이브 실시간 녹취록 전문]
00:00:15 [앵커] 9시 K-방산 글로벌 수출 수주 특보입니다.
00:05:00 [전문가] 한화에어로스페이스, LIG넥스원, 현대로템 방산 3사의 해외 수주 잔고 합계가 70조 원을 돌파했습니다.
00:22:00 [앵커] 방산 3사 보유 시 주의해야 할 점은 무엇인가요?
00:24:00 [전문가] 방산주는 지정학적 리스크 완화 시 단기 조정이 올 수 있으나 구조적 성장세가 명확하므로 적극 추천 투자의견 유지합니다."""
    },

    "22:00~23:00": {
        "mkeconomy_tv": """[매일경제TV 22:00~23:00 10시 심층 종목 집중 분석 라이브 실시간 녹취록 전문]
00:00:10 [앵커] 밤 10시 심층 종목 집중 분석 시간입니다. 오늘 밤 미 증시 빅테크 실적 발표 심층 해부합니다.
00:06:00 [전문가] 애플 아이폰16 출시에 따른 국내 부품 공급망인 삼성전기, LG이노텍, BH의 매출 증가세가 돋보입니다.
00:25:00 [앵커] 삼성전기 MLCC 부문 수익성은 어떤가요?
00:27:30 [전문가] 전장용 MLCC 가격 인상과 AI 서버용 고용량 MLCC 출하량 확대로 삼성전기는 3분기 어닝 서프라이즈가 예상됩니다. 적극 추천 드립니다.""",

        "seouleconomytv": """[서울경제TV 22:00~23:00 밤 10시 심야 승부주 핫라인 라이브 실시간 녹취록 전문]
00:00:05 [앵커] 밤 10시 심야 승부주 핫라인입니다. 체코 원전 및 유럽 신재생 에너지 수혜주 분석합니다.
00:05:30 [전문가] 두산에너빌리티와 우진엔텍이 원전 본계약 체결 가시화로 외국인 야간 지표 매수 상위에 진입했습니다.
00:22:00 [앵커] 원전 관련주 매수 전략 정리해 주시죠.
00:24:00 [전문가] 눌림목 발생 시마다 비중을 늘려가는 분할 매수 추천 전략을 제안합니다.""",

        "hkwowtv": """[한국경제TV 22:00~23:00 10시 야간 주식 왕국 라이브 실시간 녹취록 전문]
00:00:15 [앵커] 10시 야간 주식 왕국입니다. 차량용 반도체 및 아날로그 반도체 국산화 테마 분석 진행합니다.
00:06:00 [전문가] 텔레칩스가 현대차 그룹 향 MCU 독점 공급 물량 증가로 하반기 실적 턴어라운드가 가속화되고 있습니다.
00:25:00 [앵커] 텔레칩스 손절가 및 목표가 제시 부탁드립니다.
00:27:00 [전문가] 목표가 28,000원, 손절가 19,500원 제시하며 적극 추천 투자의견 드립니다."""
    },

    "23:00~24:00": {
        "mkeconomy_tv": """[매일경제TV 23:00~24:00 11시 내일 개장전 최종 점검 라이브 실시간 녹취록 전문]
00:00:10 [앵커] 밤 11시 내일 개장 전 최종 체크포인트 점검 시간입니다. 미 나스닥 지수가 1.2% 폭등세를 기록 중입니다.
00:05:00 [전문가] 내일 아침 한국 증시 개장 시 반도체, 조선, 전력설비 3대 주도 섹터의 강한 갭상승이 확실시됩니다.
00:25:00 [앵커] 시청자분들을 위한 내일 아침 최종 투자 가이드 정리해 주시죠.
00:28:00 [전문가] 삼성전자, SK하이닉스, HD현대중공업, 효성중공업 중심의 대형 주도주 포트폴리오 구성을 강력 추천합니다.""",

        "seouleconomytv": """[서울경제TV 23:00~24:00 11시 심야 최종 전략 포럼 라이브 실시간 녹취록 전문]
00:00:05 [앵커] 11시 심야 최종 전략 포럼입니다. 오늘 밤 글로벌 증시 종합 정리입니다.
00:06:00 [전문가] 미 연준 금리 인하 기대감으로 원달러 환율이 1,320원 선으로 하향 안정화되며 국내 수급 환경이 대폭 개선되었습니다.
00:24:00 [앵커] 내일 개장 직후 주목해야 할 한 줄 전략 알려주세요.
00:26:00 [전문가] 반도체 및 제약 바이오 대표 우량주 보유 전략을 적극 권장합니다.""",

        "hkwowtv": """[한국경제TV 23:00~24:00 11시 한경 야간 마감 총집결 라이브 실시간 녹취록 전문]
00:00:10 [앵커] 한경 야간 마감 총집결 11시 방송입니다.
00:05:30 [전문가] K-방산 한화에어로스페이스, LIG넥스원 및 조선 HD현대중공업의 글로벌 수주 호재가 내일 아침 국내 증시 상승을 주도할 것입니다.
00:28:00 [앵커] 시청자 여러분, 오늘 하루 고생 많으셨습니다. 내일 아침 8시 개장 방송에서 다시 찾아뵙겠습니다. 감사합니다."""
    }
}

async def run_night_generation():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}

        os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

        for slot_label, slot_content in NIGHT_SLOTS.items():
            window_label = f"2026-08-04 {slot_label}"
            hour_str = slot_label.split(":")[0]
            collected_dt = datetime.strptime(f"2026-08-04 {hour_str}:00:00", "%Y-%m-%d %H:%M:%S")

            logger.info(f"=== Processing Night Slot: {window_label} ===")

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
                logger.info(f"Saved Night Summary ID #{summary_rec.id} for {ch.name} ({window_label})")

    except Exception as e:
        logger.error(f"Night slots generation error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_night_generation())
