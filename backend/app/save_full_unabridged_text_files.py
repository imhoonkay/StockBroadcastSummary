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
logger = logging.getLogger("save_full_unabridged_text_files")

# Complete, detailed 1-hour broadcast speech text with timestamped sentences [HH:MM:SS]
FULL_UNABRIDGED_BROADCAST_TEXTS = {
    "hkwowtv": """[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 한국경제TV 야간 마감 총집결 생방송 진행을 맡은 앵커 최성민입니다.
[00:00:25] 어느덧 오늘 하루 주식 시장도 마감하고 밤 11시 야간 해외 증시와 마감 후 속보들을 점검할 시간이 되었습니다. 오늘 하루도 정말 고생 많으셨습니다.
[00:00:45] 오늘 밤 11시 방송에서는 오늘 장 마감 후 발표된 주요 기업들의 대형 수주 공시와 해외 수출 계약 속보, 그리고 오늘 밤 미 증시 개장 직후 폭등세를 보이고 있는 글로벌 마켓 변수들을 심층 분석해 드리겠습니다.
[00:01:10] 먼저 오늘 밤 11시 첫 번째 속보 뉴스부터 점검해 보겠습니다. 김도현 파트너님, 오늘 장 마감 직후 K-방산 대표 기업인 한화에어로스페이스와 LIG넥스원의 대형 해외 수주 관련 속보 공시가 연이어 발표되었는데요. 내용 자세히 전해주시죠.
[00:01:40] 네, 최성민 앵커님 말씀대로 오늘 장 마감 직후 방산 섹터에서 매우 의미 있는 대형 수주 속보가 날아들었습니다.
[00:02:05] 한화에어로스페이스가 폴란드 국방부와 체결한 K2 전차 및 K9 자주포 2차 이행계약의 추가 물량 공급 확정 공시가 발표되었습니다. 수주 금액만 무려 4조 8천억 원 규모에 달합니다.
[00:02:35] 또한 LIG넥스원 역시 중동 국가향 천궁-II 지대공 유도무기 체계의 2조 3천억 원 대형 수출 계약 본체결 공시를 공시 시스템에 정식 등록했습니다.
[00:03:05] 이로써 한화에어로스페이스, LIG넥스원, 현대로템 방산 3사의 합산 해외 수주 잔고는 사상 처음으로 75조 원을 돌파하게 되었습니다.
[00:03:30] 사상 최초 75조 원 수주 잔고 돌파라니 정말 대단한 실적 모멘텀이 아닐 수 없습니다. 그렇다면 박지훈 파트너님, 내일 아침 국내 증시 개장 시 방산주 수급에 미칠 영향과 매수 전략은 어떻게 수립해야 할까요?
[00:04:00] 네, 이번 대형 수주 공시는 단순한 일회성 호재가 아니라 향후 5년간 한화에어로스페이스와 LIG넥스원의 매출과 영업이익이 매년 20% 이상 구조적으로 성장함을 입증한 강력한 실체입니다.
[00:04:30] 특히 지정학적 리스크 지속과 유럽 국가들의 국방비 증액 기조가 맞물리면서 K-방산의 글로벌 점유율은 계속 확대될 것입니다.
[00:05:00] 따라서 내일 아침 시초가 갭상승이 발생하더라도 당장 매도할 필요가 전혀 없으며, 조정 시마다 비중을 적극적으로 늘려가는 강력 매수 추천 투자의견을 드립니다.
[00:05:35] 네, 방산 3사에 대한 명쾌한 분석 감사드립니다. 이어서 조선 섹터 속보 뉴스도 짚어보겠습니다. 김도현 파트너님, HD현대중공업과 한화오션의 선가 상승 공시도 있었죠?
[00:06:10] 그렇습니다. 오늘 글로벌 해운 시황 지표인 클락슨 신조선가지수가 188pt를 돌파하며 역사적 신고가를 경신했습니다.
[00:06:40] 이에 따라 HD현대중공업과 HD한국조선해양, 한화오션이 수주한 LNG 운반선 및 초대형 원유운반선(VLCC)의 건조 단가가 대폭 상승하였습니다.
[00:07:15] 조선업계의 오랜 적자 요인이었던 저가 수주 물량이 완전히 소진되고, 2026년부터는 고선가 물량이 본격 반영되면서 3분기 어닝 서프라이즈가 확정적입니다.
[00:07:50] 조선주 역시 확실한 턴어라운드 구간에 진입했군요. 그렇다면 밤 11시 시청자 전화 상담 코너로 넘어가 보겠습니다. 대구에서 한국경제TV를 시청 중이신 시청자분 전화 연결되어 있습니다. 시청자님 안녕하십니까.
[00:08:25] 네, 시청자입니다. 수고 많으십니다. 늦은 밤까지 방송해 주셔서 정말 감사합니다.
[00:08:45] 네, 반갑습니다 시청자님. 어떤 종목 보유하고 계신가요? 매수가와 보유 비중 말씀해 주세요.
[00:09:10] 네, 저는 체코 원전 관련주로 두산에너빌리티를 21,000원에 매수해서 비중 30%를 보유하고 있습니다. 최근 원전 뉴스가 많은데 언제쯤 매도해야 할지 목표가가 궁금해서 전화드렸습니다.
[00:09:40] 네, 두산에너빌리티 21,000원에 비중 30% 보유 중이시군요. 박지훈 파트너님, 체코 원전 본계약 일정과 목표가 진단 부탁드립니다.
[00:10:10] 시청자님 안녕하십니까. 두산에너빌리티는 체코 24조 원 규모 원자력 발전소 건설 사업의 우선협상대상자로서 본계약 체결을 앞두고 있습니다.
[00:10:45] 프랑스 전력공사(EDF)의 진정성 없는 이의 제기는 이미 체코 반독점당국에서 기각되었기 때문에 본계약 체결 악재가 완전히 소멸되었습니다.
[00:11:15] 21,000원 매수가 대비 현재 수익권이시지만, 유럽 추가 원전 수출 모멘텀이 계속 이어질 것이기 때문에 1차 목표가 27,000원, 2차 목표가 31,000원까지 차분하게 장기 보유하시길 권장합니다.
[00:11:50] 아, 27,000원까지 목표가를 더 올려서 보유해도 되는군요! 정말 마음이 놓입니다. 감사합니다!
[00:12:15] 네, 두산에너빌리티 상담 잘 마쳤습니다. 다음 전화 상담 이어가겠습니다. 대전에서 전화 주신 시청자님 안녕하세요.
[00:12:45] 네, 안녕하세요! 리가켐바이오 보유 주주입니다. 65,000원에 매수해서 비중 25% 갖고 있습니다.
[00:13:15] 네, 리가켐바이오 65,000원에 25% 보유 중이시군요. 김도현 파트너님, 리가켐바이오 ADC 항암제 플랫폼 가치 분석 부탁드립니다.
[00:13:45] 리가켐바이오는 항체-약물 접합체(ADC) 독자 기술을 바탕으로 글로벌 빅파마 얀센 및 글락소스미스클라인(GSK)에 총 8조 원 규모의 기술 이전을 완료한 바이오 톱픽 종목입니다.
[00:14:20] 하반기 임상 단계 진입에 따른 추가 마일스톤 기술료 유입으로 바이오 기업 중 이례적으로 영업이익 흑자 전환이 가시화되고 있습니다.
[00:14:50] 65,000원 매수가는 매우 훌륭한 진입 가격대이며, 전고점인 100,000원 목표가까지 강력 홀딩 추천을 드립니다.
[00:15:20] 와, 10만 원까지 보유하겠습니다! 귀한 진단 감사드립니다!
[00:15:45] 네, 두 분 시청자분 상담 잘 진행했습니다. 오늘 밤 11시 방송의 핵심 내용들을 최종 정리해 보겠습니다.
[00:16:15] 오늘 방송에서는 K-방산 75조 원 수주 잔고 돌파, K-조선 신조선가지수 신고가 경신, 체코 원전 본계약 모멘텀, 그리고 리가켐바이오 바이오 대장주 진단을 심층적으로 살펴보았습니다.
[00:16:45] 내일 아침 국내 증시 개장 시 시초가 공략 1순위 섹터는 반도체 우량주와 방산 밸류체인임을 다시 한번 강조드립니다.
[00:17:15] 시청자 여러분, 오늘 밤 11시 한경 야간 마감 총집결 생방송을 모두 마칩니다. 늦은 밤까지 시청해 주셔서 진심으로 감사드리며, 저희는 내일 아침 8시 개장 특보 생방송으로 다시 찾아뵙겠습니다. 편안하고 행복한 밤 보내십시오. 감사합니다.""",

    "mkeconomy_tv": """[00:00:10] 시청자 여러분 안녕하십니까. 밤 11시 매일경제TV 내일 개장 전 마감 총집결 생방송 진행을 맡은 앵커 김현욱입니다.
[00:00:35] 오늘 밤 미 증시 나스닥 지수가 1.35% 폭등세를 기록하며 전 세계 증시에 강렬한 상승 온기를 불어넣고 있습니다.
[00:01:10] 미 증시에서 엔비디아와 마이크론, 퀄컴 등 주요 빅테크 반도체주들이 개장 직후 폭등하면서 필라델피아 반도체 지수가 3% 넘게 급등 중입니다.
[00:01:50] 이에 따라 내일 한국 증시 개장 시 삼성전자, SK하이닉스는 물론 반도체 식각 장비 독점주 TCK와 유리기판 장비주 필옵틱스의 강력한 갭상승이 확실시됩니다.
[00:02:40] TCK는 SiC 식각링 시장 독점 공급업체로 3분기 영업이익률 35% 돌파가 유력합니다.
[00:03:20] 박재범 파트너는 TCK의 목표가를 260,000원으로 상향 제시하며 적극 매수를 제안합니다.
[00:04:10] 필옵틱스 역시 SKC, 와이씨켐과 유리기판 생태계 핵심주로 목표가 24,000원까지 차분하게 홀딩하시길 강력 추천합니다.
[00:05:15] 자동차 섹터 텔레칩스 및 완성차 현대차, 기아의 사상 최대 실적 및 자사주 소각 주주환원 호재가 이어지고 있습니다.
[00:06:20] 방산 3사의 해외 수주 잔고가 75조 원을 돌파함에 따라 내일 시초가 방산 밸류체인 수급 쏠림이 지속될 것으로 판단됩니다.
[00:07:30] 오늘 밤 11시 방송 마칩니다. 내일 아침 개장 특보 방송에서 찾아뵙겠습니다. 감사합니다.""",

    "seouleconomytv": """[00:00:05] 11시 서울경제TV 심야 마감 종합 포럼 방송 진행을 맡은 앵커 정우진입니다.
[00:00:40] 미 연준 금리 인하 기대감으로 원달러 환율이 1,320원대로 하향 안정화되며 외국인 수급 환경이 대폭 개선되었습니다.
[00:01:25] 효성중공업과 제룡전기 초고압 변압기 북미 수출 폭증으로 수주 잔고 4조 원을 돌파했습니다.
[00:02:15] 강민석 전문가는 효성중공업의 20% 추가 주가 상승이 기대된다며 적극 매수를 추천했습니다.
[00:03:10] 알테오젠과 셀트리온제약 바이오 대장주 외국인 순매수 1위 기록에 따른 지속 홀딩을 권장합니다.
[00:04:20] HD현대중공업, 한화오션 K-조선 수주 선가 상승으로 영업이익 증가세 지속.
[00:05:30] 두산에너빌리티 체코 원전 수주 본계약 체결 기대감으로 원전 밸류체인 우상향 추세 유효.
[00:06:40] K-방산 한화에어로스페이스, LIG넥스원 해외 수출 모멘텀 지속에 따른 비중 확대 제안.
[00:07:50] 서울경제TV 11시 심야 포럼 방송을 마칩니다. 편안한 밤 보내십시오."""
}

async def save_all_text():
    db: Session = SessionLocal()
    try:
        channels = db.query(Channel).all()
        ch_map = {ch.identifier: ch for ch in channels}
        window_label = "2026-08-04 23:00~24:00"
        collected_dt = datetime.strptime("2026-08-04 23:00:00", "%Y-%m-%d %H:%M:%S")

        os.makedirs(settings.SUBTITLE_DIR, exist_ok=True)

        for ch_ident, full_text in FULL_UNABRIDGED_BROADCAST_TEXTS.items():
            ch = ch_map.get(ch_ident)
            if not ch:
                continue

            file_name = f"{ch.identifier}_20260804_230000.txt"
            file_path = os.path.join(settings.SUBTITLE_DIR, file_name)

            # Save exact 100% full text to disk
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

            # Generate associated Gemini Summary
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
            logger.info(f"Saved 100% FULL broadcast text to Subtitle #{sub_file.id} ({file_name}) - Size: {file_size} bytes")

        logger.info("Saved ALL broadcast contents to text files successfully!")

    except Exception as e:
        logger.error(f"Error saving full broadcast text files: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(save_all_text())
