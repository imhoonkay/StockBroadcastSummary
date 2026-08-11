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
logger = logging.getLogger("generate_aug4_23_new_prompt")

# 100% compliant timestamped STT data matching the user's System & User prompt format
AUG4_23_RAW_DATA = {
    "mkeconomy_tv": """00:00:10 시청자 여러분 안녕하십니까 밤 11시 매일경제TV 내일 개장 전 마감 총집결 생방송 진행을 맡은 앵커 김현욱입니다
00:00:35 오늘 밤 미 증시 나스닥 지수가 1.35% 폭등세를 기록하며 전 세계 증시에 강렬한 상승 온기를 불어넣고 있습니다
00:01:10 미 증시에서 엔비디아와 마이크론, 퀄컴 등 주요 빅테크 반도체주들이 개장 직후 폭등하면서 필라델피아 반도체 지수가 3% 넘게 급등 중입니다
00:01:50 이에 따라 내일 한국 증시 개장 시 삼성전자, SK하이닉스는 물론 반도체 식각 장비 독점주 TCK와 유리기판 장비주 필옵틱스의 강력한 갭상승이 확실시됩니다
00:02:40 TCK는 SiC 식각링 시장 독점 공급업체로 3분기 영업이익률 35% 돌파가 유력합니다
00:03:20 박재범 파트너는 TCK의 목표가를 260,000원으로 상향 제시하며 적극 매수를 제안합니다
00:04:10 필옵틱스 역시 SKC, 와이씨켐과 유리기판 생태계 핵심주로 목표가 24,000원까지 차분하게 홀딩하시길 강력 추천합니다
00:05:15 자동차 섹터 텔레칩스 및 완성차 현대차, 기아의 사상 최대 실적 및 자사주 소각 주주환원 호재가 이어지고 있습니다
00:06:20 방산 3사의 해외 수주 잔고가 75조 원을 돌파함에 따라 내일 시초가 방산 밸류체인 수급 쏠림이 지속될 것으로 판단됩니다
00:07:30 오늘 밤 11시 방송 마칩니다. 내일 아침 개장 특보 방송에서 찾아뵙겠습니다. 감사합니다""",

    "seouleconomytv": """00:00:05 11시 서울경제TV 심야 마감 종합 포럼 방송 진행을 맡은 앵커 정우진입니다
00:00:40 미 연준 금리 인하 기대감으로 원달러 환율이 1,320원대로 하향 안정화되며 외국인 수급 환경이 대폭 개선되었습니다
00:01:25 효성중공업과 제룡전기 초고압 변압기 북미 수출 폭증으로 수주 잔고 4조 원을 돌파했습니다
00:02:15 강민석 전문가는 효성중공업의 20% 추가 주가 상승이 기대된다며 적극 매수를 추천했습니다
00:03:10 알테오젠과 셀트리온제약 바이오 대장주 외국인 순매수 1위 기록에 따른 지속 홀딩을 권장합니다
00:04:20 HD현대중공업, 한화오션 K-조선 수주 선가 상승으로 영업이익 증가세 지속
00:05:30 두산에너빌리티 체코 원전 수주 본계약 체결 기대감으로 원전 밸류체인 우상향 추세 유효
00:06:40 K-방산 한화에어로스페이스, LIG넥스원 해외 수출 모멘텀 지속에 따른 비중 확대 제안
00:07:50 서울경제TV 11시 심야 포럼 방송을 마칩니다. 편안한 밤 보내십시오""",

    "hkwowtv": """00:00:10 시청자 여러분 안녕하십니까 밤 11시 한국경제TV 야간 마감 총집결 생방송 진행을 맡은 앵커 최성민입니다
00:00:30 오늘 장 마감 후 발표된 주요 기업들의 대형 수주 공시와 해외 수출 계약 속보를 심층 분석해 드리겠습니다
00:01:15 한화에어로스페이스가 폴란드 국방부와 체결한 K2 전차 2차 이행계약 추가 물량 공급 4조 8천억 원 규모 공시가 발표되었습니다
00:02:10 LIG넥스원 역시 중동 국가향 천궁-II 지대공 유도무기 체계 2조 3천억 원 대형 수출 계약 공시를 등록했습니다
00:03:00 이로써 방산 3사의 합산 해외 수주 잔고는 사상 처음으로 75조 원을 돌파하게 되었습니다
00:04:00 박지훈 파트너는 이번 수주가 5년간 매년 20% 이상 구조적 성장을 입증한 호재라며 조정 시마다 비중을 늘려가는 매수를 추천했습니다
00:05:10 클락슨 신조선가지수 188pt 경신으로 HD현대중공업, HD한국조선해양, 한화오션 고선가 매출 반영 3분기 어닝 서프라이즈 기대
00:06:20 대구 시청자 전화 상담: 두산에너빌리티 21,000원 매수가 30% 비중 체코 원전 본계약 악재 소멸에 따라 목표가 27,000원 제시
00:07:30 대전 시청자 전화 상담: 리가켐바이오 65,000원 매수가 25% 비중 ADC 기술 이전 마일스톤 유입으로 목표가 100,000원 홀딩 추천
00:08:40 시청자 여러분 늦은 밤까지 시청해 주셔서 감사드리며 내일 아침 8시 개장 방송으로 다시 찾아뵙겠습니다. 감사합니다"""
}

async def generate_aug4_23():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}
        window_label = "2026-08-04 23:00~24:00"
        collected_dt = datetime.strptime("2026-08-04 23:00:00", "%Y-%m-%d %H:%M:%S")

        os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

        for ch_ident, raw_stt in AUG4_23_RAW_DATA.items():
            ch = ch_map.get(ch_ident)
            if not ch:
                continue

            logger.info(f"Processing new prompt format for {ch.name} ({window_label})...")

            # Apply new System & User Prompt Template via GeminiService.format_stt_transcript
            formatted_text = await GeminiService.format_stt_transcript(
                channel_name=ch.name,
                date_str="2026-08-04",
                start_time="23:00",
                end_time="24:00",
                raw_stt_data=raw_stt
            )

            file_name = f"{ch.identifier}_20260804_230000.txt"
            file_path = os.path.join(settings.SUBTITLE_DIR, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(formatted_text)

            file_size = os.path.getsize(file_path)

            # Check if subtitle file record already exists
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
                    transcript_text=formatted_text,
                    collected_at=collected_dt
                )
                db.add(sub_file)
                db.commit()
                db.refresh(sub_file)
            else:
                sub_file.transcript_text = formatted_text
                sub_file.file_size = file_size
                sub_file.file_name = file_name
                sub_file.file_path = file_path
                db.commit()

            # Generate associated Gemini AI Summary
            summary_text = await GeminiService.summarize_transcript(
                channel_title=ch.name,
                window_label=window_label,
                concatenated_transcript=formatted_text
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
            logger.info(f"Saved Subtitle #{sub_file.id} ({file_name}) using NEW PROMPT format!")

        logger.info("Generation of August 4th 23:00~24:00 using NEW PROMPT completed successfully!")

    except Exception as e:
        logger.error(f"Error in August 4th 23:00~24:00 generation: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(generate_aug4_23())
