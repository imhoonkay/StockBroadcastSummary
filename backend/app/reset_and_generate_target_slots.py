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
logger = logging.getLogger("reset_and_generate_target_slots")

TARGET_SLOTS = {
    "21:00~22:00": {
        "mkeconomy_tv": """[매일경제TV 21:00~22:00 미 증시 개장 실시간 중계 라이브 실시간 녹취록 전문]
00:00:05 [앵커] 9시 30분 미 증시 본장 개장 실시간 중계입니다. 다우지수 +0.3%, 나스닥지수 +0.7% 강세 출발했습니다.
00:03:30 [전문가A] 엔비디아와 마이크로소프트가 개장 직후 2% 이상 갭상승하며 반도체 지수를 강하게 끌어올리고 있습니다.
00:08:15 [전문가B] 대형 메모리 업체인 Micron과 서버 부품주 반등에 힘입어 국내 HBM4 관련주 TCK, 한미반도체가 야간 수급 지표 상위에 위치합니다.
00:15:00 [앵커] 국내 반도체 관련주들에 미치는 영향은 어떠한가요?
00:17:40 [전문가A] 삼성전자, SK하이닉스 ADR 주가가 2.5% 동반 상승 중입니다. 내일 한국 증시 개장 직후 갭상승이 확실시됩니다.
00:25:00 [시청자 상담] "TCK 220,000원에 보유 중인데 21시 야간 반등 시 목표가 상향 가능한가요?"
00:27:30 [전문가B] TCK는 SiC 식각링 시장 독점 지위로 인해 260,000원까지 목표가 상향 제시하며 적극 추천 유지합니다.
00:38:00 [앵커] 내일 아침 시초가 공략 종목으로 유리기판 수혜주 필옵틱스와 SKC를 적극 추천합니다.
00:45:00 [아나운서] 9시 미 증시 개장 라이브 중계 마칩니다. 감사합니다.""",

        "seouleconomytv": """[서울경제TV 21:00~22:00 9시 전력 & AI 밸류체인 심층 리포트 실시간 녹취록 전문]
00:00:10 [앵커] 9시 전력 및 AI 데이터센터 밸류체인 심층 리포트 방송입니다.
00:04:00 [전문가A] 미국 전력망 교체 및 AI 변압기 수주가 폭증하고 있는 효성중공업과 제룡전기가 9시 야간 시장에서 큰 관심을 받고 있습니다.
00:12:00 [전문가B] 효성중공업은 북미 현지 공장 증설 효과로 추가 20% 이상 주가 상승 여력이 충분합니다. 적극 매수 추천합니다.
00:20:00 [앵커] 제약 바이오 대장주 알테오젠과 셀트리온제약 수급도 짚어주시죠.
00:22:30 [전문가A] 알테오젠 피하주사 제형 변경 기술 이전 가치 재평가로 강세를 지속하고 있으며 적극 추천 투자의견 유지합니다.
00:35:00 [종목 진단] 삼성전기 IT 및 전장용 MLCC 실적 개선 기대감에 따라 보유 의견을 드립니다.
00:45:00 [앵커] 9시 전력 및 AI 밸류체인 리포트 방송을 마칩니다.""",

        "hkwowtv": """[한국경제TV 21:00~22:00 9시 K-방산 글로벌 수주 특보 라이브 실시간 녹취록 전문]
00:00:15 [앵커] 9시 K-방산 글로벌 수출 수주 특보입니다.
00:05:00 [전문가A] 한화에어로스페이스, LIG넥스원, 현대로템 방산 3사의 해외 수주 잔고 합계가 70조 원을 돌파했습니다.
00:14:00 [전문가B] K2 전차 및 천궁-II 수주 모멘텀이 확실하며 방산 섹터는 조정 때마다 꾸준히 담아가는 적극 추천 핵심 업종입니다.
00:22:00 [앵커] 체코 원전 수혜주 두산에너빌리티 점검해 보겠습니다.
00:24:00 [전문가A] 두산에너빌리티는 원전 본계약 기대감으로 하반기 지속 모멘텀을 형성할 것입니다.
00:38:00 [시청자 상담] "한화에어로스페이스 290,000원 보유 중입니다." 보유 의견 제안.
00:45:00 [앵커] 9시 방산 특보 마칩니다. 감사합니다."""
    },

    "22:00~23:00": {
        "mkeconomy_tv": """[매일경제TV 22:00~23:00 10시 심층 종목 집중 분석 라이브 실시간 녹취록 전문]
00:00:10 [앵커] 밤 10시 심층 종목 집중 분석 시간입니다. 오늘 밤 미 증시 빅테크 실적 발표 심층 해부합니다.
00:06:00 [전문가A] 애플 아이폰16 출시에 따른 국내 부품 공급망인 삼성전기, LG이노텍, BH의 매출 증가세가 돋보입니다.
00:15:00 [전문가B] 삼성전기는 AI 서버용 고용량 MLCC 출하량 확대로 3분기 어닝 서프라이즈가 예상됩니다. 적극 추천 드립니다.
00:25:00 [앵커] 바이오 밸류체인 리가켐바이오 기술 이전 모멘텀 분석해 주시죠.
00:27:30 [전문가A] 리가켐바이오는 ADC 플랫폼 수수료 유입으로 흑자 전환이 확실시되어 바이오 최선호주로 적극 추천합니다.
00:38:00 [시청자 상담] 카카오 및 NAVER 야간 진단 진행.
00:45:00 [앵커] 10시 방송 마칩니다.""",

        "seouleconomytv": """[서울경제TV 22:00~23:00 밤 10시 심야 승부주 핫라인 라이브 실시간 녹취록 전문]
00:00:05 [앵커] 밤 10시 심야 승부주 핫라인입니다. 체코 원전 및 유럽 신재생 에너지 수혜주 분석합니다.
00:05:30 [전문가A] 두산에너빌리티와 우진엔텍이 원전 본계약 체결 가시화로 야간 지표 매수 상위에 진입했습니다.
00:16:00 [전문가B] 조선주 HD현대중공업, HD한국조선해양, 한화오션도 3분기 최고 실적 경신 전망에 강한 상승세를 지속합니다.
00:24:00 [앵커] 원전 및 조선 섹터 보유 전략은 분할 매수를 제안합니다.
00:40:00 [앵커] 심야 승부주 핫라인 마칩니다.""",

        "hkwowtv": """[한국경제TV 22:00~23:00 10시 야간 주식 왕국 라이브 실시간 녹취록 전문]
00:00:15 [앵커] 10시 야간 주식 왕국입니다. 차량용 반도체 국산화 테마 분석 진행합니다.
00:06:00 [전문가A] 텔레칩스가 현대차 그룹 향 MCU 독점 공급 물량 증가로 하반기 실적 턴어라운드가 가속화되고 있습니다.
00:18:00 [전문가B] 텔레칩스는 목표가 28,000원, 손절가 19,500원 제시하며 적극 추천 투자의견 드립니다.
00:30:00 [시청자 상담] 현대차, 기아 완성차 주주환원 정책 호평.
00:45:00 [앵커] 10시 야간 주식 왕국 마칩니다."""
    },

    "23:00~24:00": {
        "mkeconomy_tv": """[매일경제TV 23:00~24:00 11시 내일 개장전 최종 점검 라이브 실시간 녹취록 전문]
00:00:10 [앵커] 밤 11시 내일 개장 전 최종 체크포인트 점검 시간입니다. 미 나스닥 지수가 1.2% 폭등세를 기록 중입니다.
00:05:00 [전문가A] 내일 아침 한국 증시 개장 시 반도체, 조선, 전력설비 3대 주도 섹터의 강한 갭상승이 확실시됩니다.
00:18:00 [전문가B] 삼성전자, SK하이닉스, HD현대중공업, 효성중공업 중심의 대형 주도주 포트폴리오 구성을 강력 추천합니다.
00:35:00 [앵커] 내일 시초가 공략 1순위 반도체 우량주 대응 지침 전달합니다.
00:45:00 [아나운서] 내일 아침 개장 방송에서 뵙겠습니다. 감사합니다.""",

        "seouleconomytv": """[서울경제TV 23:00~24:00 11시 심야 최종 전략 포럼 라이브 실시간 녹취록 전문]
00:00:05 [앵커] 11시 심야 최종 전략 포럼입니다. 오늘 밤 글로벌 증시 종합 정리입니다.
00:06:00 [전문가A] 미 연준 금리 인하 기대감으로 원달러 환율이 1,320원 선으로 하향 안정화되며 국내 수급 환경이 대폭 개선되었습니다.
00:20:00 [전문가B] 반도체 및 제약 바이오 대표 우량주 보유 전략을 적극 권장합니다.
00:40:00 [앵커] 11시 심야 최종 전략 포럼 마칩니다.""",

        "hkwowtv": """[한국경제TV 23:00~24:00 11시 한경 야간 마감 총집결 라이브 실시간 녹취록 전문]
00:00:10 [앵커] 한경 야간 마감 총집결 11시 방송입니다.
00:05:30 [전문가A] K-방산 한화에어로스페이스, LIG넥스원 및 조선 HD현대중공업의 글로벌 수주 호재가 내일 아침 국내 증시 상승을 주도할 것입니다.
00:22:00 [전문가B] 방산 및 반도체 밸류체인은 조정을 활용한 적극 매수를 제안합니다.
00:45:00 [앵커] 오늘 하루 고생 많으셨습니다. 방송 마칩니다."""
    }
}

async def reset_and_generate():
    db: Session = SessionLocal()
    try:
        # 1. Clear tables completely
        logger.info("1. Wiping ALL existing records from summaries and subtitle_files tables...")
        db.query(Summary).delete()
        db.query(SubtitleFile).delete()
        db.commit()
        logger.info("Tables wiped clean successfully!")

        # 2. Get active channels
        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}

        os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

        total_created = 0
        # 3. Generate only 21~22, 22~23, 23~24 slots
        for slot_label, slot_content in TARGET_SLOTS.items():
            window_label = f"2026-08-04 {slot_label}"
            hour_str = slot_label.split(":")[0]
            collected_dt = datetime.strptime(f"2026-08-04 {hour_str}:00:00", "%Y-%m-%d %H:%M:%S")

            logger.info(f"--- Generating Target Slot: {window_label} ---")

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

                logger.info(f"Generating Gemini AI Summary for {ch.name} ({window_label})...")
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

                total_created += 1
                logger.info(f"Created Subtitle #{sub_file.id} and Summary #{summary_rec.id} for {ch.name} ({window_label})")

        logger.info(f"Reset and target generation completed! Total {total_created} entries created.")

    except Exception as e:
        logger.error(f"Reset and generation error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(reset_and_generate())
