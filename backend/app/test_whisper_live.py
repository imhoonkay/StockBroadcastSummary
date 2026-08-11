import os
import sys
import subprocess
import logging
from datetime import datetime
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Global cached model instance to avoid reloading every 10 min
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Initializing faster-whisper model (tiny, int8 CPU)...")
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model

def get_live_audio_url(live_url: str) -> str | None:
    """Extract live audio m3u8 stream URL using yt-dlp"""
    cmd = ["yt-dlp", "-g", live_url]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip().splitlines()[0]
    return None

def transcribe_live_stream(live_url: str, channel_name: str, duration_sec: int = 30) -> str:
    """Capture live audio via FFmpeg and transcribe using Whisper STT"""
    logger.info(f"Extracting live audio URL for {channel_name} ({live_url})...")
    audio_stream_url = get_live_audio_url(live_url)
    
    if not audio_stream_url:
        err_msg = f"[수집 실패] {channel_name} 라이브 오디오 스트림 URL 추출 불가 (yt-dlp 오류/방송 정지)"
        logger.error(err_msg)
        return err_msg

    wav_path = f"/tmp/{channel_name}_live.wav"
    logger.info(f"Capturing {duration_sec}s audio from stream using FFmpeg to {wav_path}...")
    
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", audio_stream_url,
        "-t", str(duration_sec),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        wav_path
    ]
    
    ffmpeg_res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if ffmpeg_res.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
        err_msg = f"[수집 실패] {channel_name} FFmpeg 라이브 오디오 캡처 실패: {ffmpeg_res.stderr[:200]}"
        logger.error(err_msg)
        return err_msg

    try:
        model = get_whisper_model()
        logger.info(f"Running Whisper STT transcription on {wav_path}...")
        segments, info = model.transcribe(wav_path, language="ko", beam_size=1)
        
        lines = []
        for segment in segments:
            # Format timestamp as [00:00:05]
            mins = int(segment.start // 60)
            secs = int(segment.start % 60)
            ts = f"[00:{mins:02d}:{secs:02d}]"
            text_str = segment.text.strip()
            if text_str:
                lines.append(f"{ts} {text_str}")

        if os.path.exists(wav_path):
            os.remove(wav_path)

        if lines:
            result_text = "\n".join(lines)
            logger.info(f"Successfully transcribed {len(lines)} lines ({len(result_text)} chars) for {channel_name}")
            return result_text
        else:
            return f"[수집 안내] {channel_name} 라이브 방송 캡처 구간에서 음성이 감지되지 않았습니다."

    except Exception as e:
        if os.path.exists(wav_path):
            os.remove(wav_path)
        err_msg = f"[수집 실패] {channel_name} Whisper STT 처리 실패: {e}"
        logger.error(err_msg)
        return err_msg

if __name__ == "__main__":
    test_url = "https://www.youtube.com/@MKeconomy_TV/live"
    print("=== TESTING REAL WHISPER STT LIVE CAPTURE ===")
    res = transcribe_live_stream(test_url, "매일경제TV", duration_sec=30)
    print("=== RESULT ===")
    print(res)
