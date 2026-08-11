import re
import os
import asyncio
import subprocess
import httpx
import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

import uuid

# Global cached whisper model instance
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Initializing faster-whisper model (tiny, int8 CPU)...")
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model


class YoutubeService:
    @staticmethod
    def _get_live_audio_url_sync(live_url: str) -> str | None:
        """Extract live stream audio m3u8 URL using yt-dlp"""
        cmd_args_list = [
            ["yt-dlp", "-g", "-f", "bestaudio/best", live_url],
            ["yt-dlp", "-g", live_url]
        ]
        for cmd in cmd_args_list:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                url = res.stdout.strip().splitlines()[0]
                logger.info(f"Successfully extracted live audio URL: {url[:60]}...")
                return url
            else:
                logger.warning(f"yt-dlp attempt failed for {live_url}: {res.stderr.strip()[:200]}")
        return None

    @classmethod
    def _fetch_transcript_sync(cls, live_url: str, channel_name: str, duration_sec: int, channel_identifier: str = "") -> str:
        """Synchronous implementation of live audio capture & Whisper STT"""
        logger.info(f"Extracting live audio URL for {channel_name} ({live_url})...")
        audio_stream_url = cls._get_live_audio_url_sync(live_url)

        if not audio_stream_url:
            err_msg = f"[수집 실패] {channel_name} 라이브 오디오 스트림 URL 추출 불가 (yt-dlp/방송정지)"
            logger.error(err_msg)
            return err_msg

        # Unique filename with channel identifier prefix for easy log tracking and zero collision
        prefix = channel_identifier if channel_identifier else "channel"
        wav_path = f"/tmp/live_{prefix}_{uuid.uuid4().hex[:8]}.wav"
        logger.info(f"Capturing {duration_sec}s audio from stream using FFmpeg to {wav_path}...")

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", audio_stream_url,
            "-t", str(duration_sec),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            wav_path
        ]

        ffmpeg_res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if ffmpeg_res.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
            if os.path.exists(wav_path):
                os.remove(wav_path)
            err_msg = f"[수집 실패] {channel_name} FFmpeg 라이브 오디오 캡처 실패"
            logger.error(err_msg)
            return err_msg

        try:
            model = get_whisper_model()
            logger.info(f"Running Whisper STT transcription on {wav_path}...")
            segments, info = model.transcribe(wav_path, language="ko", beam_size=1)

            lines = []
            for segment in segments:
                mins = int(segment.start // 60)
                secs = int(segment.start % 60)
                ts = f"[00:{mins:02d}:{secs:02d}]"
                text_str = segment.text.strip()
                if text_str:
                    lines.append(f"{ts} {text_str}")

            if lines:
                result_text = "\n".join(lines)
                logger.info(f"Successfully transcribed {len(lines)} lines for {channel_name}")
                return result_text
            else:
                return f"[수집 완료] {channel_name} 방송 진행 중 (대사 없음)"
        except Exception as e:
            logger.error(f"Error transcribing audio for {channel_name}: {e}")
            return f"[수집 실패] {channel_name} Whisper STT 에러: {e}"
        finally:
            if os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    @classmethod
    async def fetch_transcript(cls, live_url: str, channel_name: str, duration_sec: int = 600) -> str:
        """Asynchronous wrapper that runs heavy FFmpeg audio capture and Whisper STT in worker thread"""
        return await asyncio.to_thread(cls._fetch_transcript_sync, live_url, channel_name, duration_sec)
