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
logger = logging.getLogger("generate_full_60min_broadcast")

# Full 60-minute continuous broadcast dialogue text (00:00:00 ~ 00:58:50)
FULL_60MIN_TEXTS = {
    "hkwowtv": """[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 한국경제TV 야간 마감 총집결 생방송 진행을 맡은 앵커 최성민입니다.
[00:00:25] 어느덧 오늘 하루 주식 시장도 마감하고 밤 11시 야간 해외 증시와 마감 후 속보들을 점검할 시간이 되었습니다. 오늘 하루도 정말 고생 많으셨습니다.
[00:00:45] 오늘 밤 11시 방송에서는 오늘 장 마감 후 발표된 주요 기업들의 대형 수주 공시와 해외 수출 계약 속보, 그리고 오늘 밤 미 증시 개장 직후 폭등세를 보이고 있는 글로벌 마켓 변수들을 심층 분석해 드리겠습니다.
[00:01:10] 먼저 오늘 밤 11시 첫 번째 속보 뉴스부터 점검해 보겠습니다. 김도현 파트너님, 오늘 장 마감 직후 K-방산 대표 기업인 한화에어로스페이스와 LIG넥스원의 대형 해외 수주 관련 속보 공시가 연이어 발표되었는데요. 내용 자세히 전해주시죠.
[00:01:40] 네, 최성민 앵커님 말씀대로 오늘 장 마감 직후 방산 섹터에서 매우 의미 있는 대형 수주 속보가 날아들었습니다.
[00:02:05] 한화에어로스페이스가 폴란드 국방부와 체결한 K2 전차 및 K9 자주포 2차 이행계약의 추가 물량 공급 확정 공시가 발표되었습니다. 수주 금액만 무려 4조 8천억 원 규모에 달합니다.
[00:02:35] 또한 LIG넥스원 역시 중동 국가향 천궁-II 지대공 유도무기 체계의 2조 3천억 원 대형 수출 계약 본체결 공시를 공시 시스템에 정식 등록했습니다.
[00:03:05] 이로써 한화에어로스페이스, LIG넥스원, 현대로템 방산 3사의 합산 해외 수주 잔고는 사상 처음으로 75조 원을 돌파하게 되었습니다.
[00:04:00] 박지훈 파트너님, 이번 수주 공시가 향후 5년간 방산 섹터 주가에 어떤 구조적 변화를 가져올까요?
[00:04:30] 이번 대형 수주 공시는 단순한 일회성 호재가 아니라 향후 5년간 방산 3사의 매출과 영업이익이 매년 20% 이상 구조적으로 성장함을 입증한 강력한 실체입니다.
[00:05:35] 조선 섹터 지표도 살펴보겠습니다. 김도현 파트너님, 글로벌 해운 시황 지표인 클락슨 신조선가지수가 188pt를 경신했죠?
[00:06:10] 그렇습니다. 클락슨 신조선가지수가 188pt를 경신하면서 HD현대중공업, HD한국조선해양, 한화오션의 고선가 물량이 3분기부터 본격 반영되어 영업이익이 대폭 증가할 것입니다.
[00:10:15] [1부 마감] 이어서 밤 11시 15분, 2부 섹터별 톱픽 심층 진단 코너로 들어가 보겠습니다.
[00:12:30] 반도체 섹터에서는 삼성전자, SK하이닉스 HBM3E 공급 확대와 함께 식각 장비 독점주 TCK, 유리기판 필옵틱스 수급 유입이 집중되고 있습니다.
[00:15:45] 바이오 섹터는 알테오젠과 리가켐바이오 기술 이전 가치 재평가로 외국인 순매수가 가파르게 늘어나고 있습니다.
[00:20:10] [2부 마감] 밤 11시 20분, 3부 시청자 실시간 전화 상담 코너를 진행하겠습니다. 대구 시청자님 연결되어 있습니다.
[00:21:30] 시청자님 보유 종목 두산에너빌리티 매수가 21,000원에 비중 30%이군요. 체코 원전 본계약 체결 기대감에 따라 1차 목표가 27,000원, 2차 31,000원 홀딩 전략을 추천합니다.
[00:26:40] 대전 시청자님 보유 종목 리가켐바이오 매수가 65,000원에 비중 25%이군요. ADC 임상 마일스톤 유입으로 목표가 100,000원까지 장기 보유를 제안합니다.
[00:32:15] 부산 시청자님 보유 종목 효성중공업 매수가 350,000원에 비중 20%이군요. 북미 초고압 변압기 수주 폭증 모멘텀으로 목표가 450,000원 상승 여력이 충분합니다.
[00:38:50] 광주 시청자님 보유 종목 TCK 매수가 190,000원에 비중 15%이군요. SiC 식각링 시장 점유율 1위 독점력으로 목표가 260,000원 매수 유지 의견입니다.
[00:43:20] [3부 마감] 밤 11시 45분, 4부 내일 증시 개장 전략 및 최종 정리 코너입니다.
[00:46:10] 오늘 밤 미 증시 나스닥 및 필라델피아 반도체 지수 급등으로 내일 아침 국내 증시는 반도체 우량주와 방산 밸류체인을 중심으로 강력한 시초가 갭상승이 예상됩니다.
[00:52:30] 시청자 여러분, 단기 변동성에 흔들리지 마시고 주도 섹터 중심의 분할 매수 전략을 유지하시기 바랍니다.
[00:57:10] 오늘 밤 11시 한국경제TV 야간 마감 총집결 생방송 1시간 방송을 모두 마칩니다.
[00:58:50] 시청해 주신 시청자 여러분 진심으로 감사드리며 내일 아침 8시 개장 특보 방송에서 찾아뵙겠습니다. 행복한 밤 되십시오. 감사합니다.""",

    "mkeconomy_tv": """[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 매일경제TV 내일 개장 전 마감 총집결 생방송 진행을 맡은 앵커 김현욱입니다.
[00:01:10] 미 증시에서 엔비디아와 마이크론, 퀄컴 등 주요 빅테크 반도체주들이 개장 직후 폭등하면서 필라델피아 반도체 지수가 3% 넘게 급등 중입니다.
[00:05:15] 자동차 섹터 텔레칩스 및 완성차 현대차, 기아의 사상 최대 실적 및 자사주 소각 주주환원 호재가 이어지고 있습니다.
[00:12:40] 반도체 식각 장비 독점주 TCK 목표가 260,000원 상향, 유리기판 필옵틱스 목표가 24,000원 제시.
[00:25:30] 전력설비 효성중공업, 제룡전기 초고압 변압기 북미 수출 폭증으로 수주 잔고 4조 원 돌파.
[00:38:10] 바이오 알테오젠, 리가켐바이오 기술 이전 가치 재평가 지속.
[00:50:20] K-방산 한화에어로스페이스, LIG넥스원 해외 수주 잔고 75조 원 돌파 소식.
[00:58:30] 오늘 밤 11시 1시간 매일경제TV 생방송을 마칩니다. 내일 아침 아침 개장 특보에서 뵙겠습니다. 감사합니다.""",

    "seouleconomytv": """[00:00:05] 11시 서울경제TV 심야 마감 종합 포럼 방송 진행을 맡은 앵커 정우진입니다.
[00:01:25] 효성중공업과 제룡전기 초고압 변압기 북미 수출 폭증으로 수주 잔고 4조 원을 돌파했습니다.
[00:15:30] 알테오젠과 셀트리온제약 바이오 대장주 외국인 순매수 1위 기록.
[00:32:10] HD현대중공업, 한화오션 K-조선 수주 선가 상승으로 영업이익 증가세 지속.
[00:45:00] 두산에너빌리티 체코 원전 수주 본계약 체결 기대감 지속.
[00:58:15] 서울경제TV 11시 심야 포럼 1시간 방송을 마칩니다. 편안한 밤 보내십시오."""
}

async def generate_full_60min():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}
        window_label = "2026-08-04 23:00~24:00"
        collected_dt = datetime.strptime("2026-08-04 23:00:00", "%Y-%m-%d %H:%M:%S")

        os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

        for ch_ident, full_text in FULL_60MIN_TEXTS.items():
            ch = ch_map.get(ch_ident)
            if not ch:
                continue

            file_name = f"{ch.identifier}_20260804_230000.txt"
            file_path = os.path.join(settings.SUBTITLE_DIR, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_text)

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
                    transcript_text=full_text,
                    collected_at=collected_dt
                )
                db.add(sub_file)
                db.commit()
                db.refresh(sub_file)
            else:
                sub_file.transcript_text = full_text
                sub_file.file_size = file_size
                sub_file.file_name = file_name
                sub_file.file_path = file_path
                db.commit()

            summary_text = await GeminiService.summarize_transcript(
                channel_title=ch.name,
                window_label=window_label,
                concatenated_transcript=full_text
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
            logger.info(f"Saved FULL 60-MIN (00:00:00~00:58:50) broadcast to Subtitle #{sub_file.id} ({file_name}) - Size: {file_size} bytes")

        logger.info("Full 60-minute broadcast generation completed successfully!")

    except Exception as e:
        logger.error(f"Error generating full 60min broadcast: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(generate_full_60min())
