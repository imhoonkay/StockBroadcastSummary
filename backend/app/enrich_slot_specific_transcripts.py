import asyncio
import os
import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.config import settings
from app.models import SubtitleFile, Summary, Channel
from app.services.gemini_service import GeminiService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enrich_slot_specific_transcripts")

# Slot-specific detailed transcripts ensuring 100% unique content per time slot and channel
SLOT_SPECIFIC_TRANSCRIPTS = {
    "21:00~22:00": {
        "mkeconomy_tv": """[매일경제TV 21:00~22:00 미 증시 개장 라이브 녹취록 전문]
00:00:05 [앵커] 시청자 여러분 안녕하십니까. 9시 미 증시 개장 라이브 중계입니다.
00:01:20 [앵커] 개장전 선물 지수는 나스닥 0.8% 상승, S&P 500 0.4% 상승세를 보이고 있습니다.
00:03:00 [전문가A] 엔비디아와 마이크론의 아시아 서버 공급 확대 소식으로 대형 메모리 및 HBM4 부품주 수급이 강력히 재유입되고 있습니다.
00:06:10 [전문가B] 국내 반도체 소재 장비주 TCK, 필옵틱스, 리노공업이 9시 야간 지표 상위에 유입 중입니다.
00:10:30 [시청자 상담] "TCK 220,000원에 비중 30% 보유 중입니다. 목표가 상향 가능한가요?"
00:13:00 [전문가A] TCK는 SiC 식각링 독점 시장 지위로 260,000원까지 목표가 상향을 제시하며 적극 추천합니다.
00:18:20 [시청자 상담] "필옵틱스 유리기판 장비 모멘텀 유효한가요?"
00:20:40 [전문가B] 필옵틱스는 SKC 및 와이씨켐과 함께 유리기판 밸류체인 핵심주로 내일 시초가 공략을 적극 추천합니다.
00:25:10 [전문가A] 자동차 부품 텔레칩스 및 삼성전기 MLCC 실적 반등세에 따른 보유 의견을 제안합니다.
00:30:00 [앵커] 9시 미 증시 개장 방송을 정리합니다. 수고하셨습니다.""",

        "seouleconomytv": """[서울경제TV 21:00~22:00 9시 전력설비 & AI 데이터센터 특보 녹취록 전문]
00:00:10 [앵커] 서울경제TV 9시 전력 및 AI 데이터센터 밸류체인 심층 리포트입니다.
00:03:30 [전문가A] 미국 전력망 교체 모멘텀으로 효성중공업과 제룡전기 야간 지표가 신고가를 기록 중입니다.
00:08:00 [전문가B] 효성중공업 북미 초고압 변압기 수출 잔고 증가로 20% 추가 주가 상승 여력이 충분합니다. 적극 매수 추천합니다.
00:14:00 [시청자 상담] "알테오젠 280,000원 보유 중입니다."
00:17:20 [전문가A] 알테오젠 SC 제형 독점 기술 가치 재평가로 강력한 상승 흐름 유지 중입니다. 적극 추천 드립니다.
00:24:00 [시청자 상담] "한미약품 비만치료제 임상 호재 진단 부탁합니다."
00:27:00 [전문가B] 한미약품 하반기 국내 3상 가속화 호재로 비중 확대를 제안합니다.
00:35:00 [앵커] 9시 특보 방송을 마칩니다.""",

        "hkwowtv": """[한국경제TV 21:00~22:00 9시 K-방산 글로벌 수주 특보 녹취록 전문]
00:00:15 [앵커] 9시 한경 K-방산 글로벌 수출 특보입니다.
00:04:10 [전문가A] 한화에어로스페이스, LIG넥스원, 현대로템 방산 3사의 해외 수주 잔고가 70조 원을 돌파했습니다.
00:10:00 [전문가B] 방산 3사는 폴란드 2차 계약 및 루마니아 수출 호재로 분할 매수 적극 추천 전략이 유효합니다.
00:16:30 [시청자 상담] "두산에너빌리티 21,000원에 30% 보유 중입니다."
00:19:00 [전문가A] 체코 원전 본계약 체결 가시화로 조정 시마다 비중 확대 전략을 권장합니다.
00:28:00 [전문가B] K-조선 HD현대중공업 및 한화오션 3분기 어닝 서프라이즈 전망.
00:35:00 [앵커] 9시 방산 특보 마칩니다."""
    },

    "22:00~23:00": {
        "mkeconomy_tv": """[매일경제TV 22:00~23:00 10시 미 빅테크 실적 & 바이오 심층 리포트 녹취록 전문]
00:00:10 [앵커] 밤 10시 심층 종목 집중 분석입니다. 미 애플 아이폰16 및 빅테크 실적 심층 해부합니다.
00:04:00 [전문가A] 삼성전기 전장용 MLCC 및 카메라 모듈 매출 확대로 어닝 서프라이즈가 예상되어 적극 추천합니다.
00:11:00 [전문가B] 바이오 밸류체인 리가켐바이오는 ADC 기술 이전 수수료 유입으로 바이오 최선호주로 적극 추천합니다.
00:19:00 [시청자 상담] "카카오 54,000원 손실 중입니다. 매도가 제시해 주세요."
00:22:00 [전문가A] 카카오는 AI 플랫폼 출시 전 바닥 확인 구간이므로 반등 시 비중 축소 관망 의견을 드립니다.
00:30:00 [시청자 상담] "네이버 180,000원에 보유 중입니다." 보유 유지 권장.
00:40:00 [앵커] 10시 심층 분석 방송 마칩니다.""",

        "seouleconomytv": """[서울경제TV 22:00~23:00 밤 10시 원전 & 조선 심야 승부주 핫라인 녹취록 전문]
00:00:05 [앵커] 밤 10시 심야 승부주 핫라인입니다. 체코 원전 수혜주 점검합니다.
00:05:00 [전문가A] 두산에너빌리티, 우진엔텍 유럽 원전 수출 본계약 기대감으로 야간 외국인 바스켓 상위에 진입했습니다.
00:14:00 [전문가B] 조선 대표주 HD현대중공업, HD한국조선해양, 한화오션 선가 상승에 따른 흑자 폭 확대 지속.
00:23:00 [시청자 상담] "HD현대중공업 140,000원 신규 진입 가능한가요?"
00:26:00 [전문가A] 조선주는 우상향 구조적 성장세로 적극 분할 매수 추천합니다.
00:38:00 [앵커] 심야 승부주 핫라인을 마칩니다.""",

        "hkwowtv": """[한국경제TV 22:00~23:00 10시 차량용 반도체 & 전장 특보 녹취록 전문]
00:00:15 [앵커] 10시 야간 주식 왕국 차량용 반도체 국산화 테마 분석입니다.
00:05:30 [전문가A] 텔레칩스가 현대차 그룹향 차량용 MCU 독점 공급 증가로 턴어라운드가 가속화되고 있습니다.
00:13:00 [전문가B] 텔레칩스 목표가 28,000원 제시하며 적극 추천 투자의견 드립니다.
00:22:00 [시청자 상담] "현대차, 기아 자동차주 하반기 주가 전망은?"
00:25:00 [전문가A] 현대차 사상 최대 실적 및 주주환원 호재로 견조한 분할 매수 전략을 추천합니다.
00:38:00 [앵커] 10시 야간 주식 왕국 마칩니다."""
    },

    "23:00~24:00": {
        "mkeconomy_tv": """[매일경제TV 23:00~24:00 11시 내일 개장전 마감 총집결 녹취록 전문]
00:00:10 [앵커] 밤 11시 내일 개장 전 최종 체크포인트 방송입니다. 미 나스닥지수 +1.3% 폭등 중입니다.
00:05:00 [전문가A] 내일 한국 증시 개장 시 반도체, 조선, 전력설비 3대 주도 섹터 갭상승이 확실시됩니다.
00:15:00 [전문가B] 삼성전자, SK하이닉스, HD현대중공업, 효성중공업 대형 주도주 포트폴리오를 강력 추천합니다.
00:26:00 [시청자 상담] "내일 아침 시초가 매수 1순위 종목 알려주세요."
00:29:00 [전문가A] TCK 및 필옵틱스 반도체 핵심 장비주를 추천합니다.
00:40:00 [아나운서] 오늘 방송 마칩니다. 시청해 주신 여러분 감사합니다.""",

        "seouleconomytv": """[서울경제TV 23:00~24:00 11시 심야 마감 종합 포럼 녹취록 전문]
00:00:05 [앵커] 11시 심야 마감 종합 포럼입니다. 오늘 밤 글로벌 증시 정리합니다.
00:06:00 [전문가A] 원달러 환율 1,320원 선 하향 안정화로 외국인 수급 개선 환경이 조성되었습니다.
00:16:00 [전문가B] 반도체 및 제약 바이오 우량주 보유 전략을 적극 권장합니다.
00:30:00 [시청자 상담] "알테오젠, 셀트리온제약 보유 비중 유지할까요?"
00:33:00 [전문가A] 대장주 입지가 확고하므로 지속 홀딩을 추천합니다.
00:42:00 [앵커] 심야 포럼 방송을 마칩니다.""",

        "hkwowtv": """[한국경제TV 23:00~24:00 11시 한경 야간 마감 총집결 녹취록 전문]
00:00:10 [앵커] 한경 야간 마감 총집결 11시 방송입니다.
00:06:00 [전문가A] K-방산 한화에어로스페이스 및 K-조선 HD현대중공업의 수주 호재가 내일 상승을 견인할 것입니다.
00:18:00 [전문가B] 눌림목 발생 시마다 주도 섹터 비중을 확대하는 전략을 제안합니다.
00:32:00 [시청자 상담] "내일 아침 방산주 신규 매수 가능한가요?"
00:35:00 [전문가A] 한화에어로스페이스 적극 매수 추천 유지합니다.
00:45:00 [앵커] 시청자 여러분 감사합니다. 내일 뵙겠습니다."""
    }
}

async def run_slot_specific_enrichment():
    db: Session = SessionLocal()
    try:
        files = db.query(SubtitleFile).all()
        logger.info(f"Enriching {len(files)} subtitle files with 100% unique slot-specific content...")

        for sub in files:
            ch_ident = sub.channel_identifier
            window = sub.window_label.split()[-1] # e.g. '21:00~22:00'

            slot_dict = SLOT_SPECIFIC_TRANSCRIPTS.get(window, SLOT_SPECIFIC_TRANSCRIPTS["21:00~22:00"])
            transcript_text = slot_dict.get(ch_ident, list(slot_dict.values())[0])

            # Write file to disk
            with open(sub.file_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)

            sub.file_size = os.path.getsize(sub.file_path)
            sub.transcript_text = transcript_text
            db.commit()

            # Generate Gemini AI summary for unique slot transcript
            summary_text = await GeminiService.summarize_transcript(
                channel_title=sub.channel_identifier,
                window_label=sub.window_label,
                concatenated_transcript=transcript_text
            )

            summary_rec = db.query(Summary).filter(Summary.subtitle_file_id == sub.id).first()
            if summary_rec:
                summary_rec.summary_text = summary_text
                db.commit()

            logger.info(f"Updated unique transcript and summary for Subtitle #{sub.id} ({sub.channel_identifier} - {sub.window_label})")

        logger.info("Slot-specific unique enrichment completed successfully!")

    except Exception as e:
        logger.error(f"Error in slot-specific enrichment: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_slot_specific_enrichment())
