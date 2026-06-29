"""
Audio Processing Module
- STT: Speech-to-Text via faster-whisper (incoming voice messages)
- TTS: Text-to-Speech via edge-tts (outgoing voice messages)
- WhatsApp voice messages use Opus codec in OGG container
"""

import os
import logging
import tempfile
import subprocess
import requests

logger = logging.getLogger(__name__)

# ---------- STT (Speech-to-Text) ----------

_whisper_model = None

def _get_whisper_model():
    """Lazy-load whisper model (heavy, only load when needed)."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model (base, CPU)...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _whisper_model


def transcribe_audio(audio_path: str, language: str = None) -> str:
    """
    Transcribe an audio file to text using faster-whisper.
    
    Args:
        audio_path: Path to audio file (ogg/opus, mp3, wav, etc.)
        language: Optional language hint (e.g. 'en', 'hi'). None = auto-detect.
    
    Returns:
        Transcribed text string.
    """
    try:
        model = _get_whisper_model()
        
        # faster-whisper can handle most formats via ffmpeg
        segments, info = model.transcribe(
            audio_path,
            language=language,  # None = auto-detect
            beam_size=5,
            vad_filter=True,  # Skip silence
        )
        
        text = " ".join([seg.text.strip() for seg in segments]).strip()
        logger.info(f"Transcribed ({info.language}, {info.language_probability:.2f}): {text[:100]}")
        return text
        
    except Exception as e:
        logger.error(f"STT error: {e}", exc_info=True)
        return ""


# ---------- TTS (Text-to-Speech) ----------

# Voice mapping — pick natural voices for English and Hindi
TTS_VOICES = {
    "en": "en-IN-NeerjaNeural",      # Indian English female voice
    "hi": "hi-IN-SwaraNeural",        # Hindi female voice
    "default": "en-IN-NeerjaNeural",  # Default to Indian English
}


def generate_speech(text: str, language: str = "en", output_path: str = None) -> str:
    """
    Convert text to speech using edge-tts.
    Returns path to the generated audio file (mp3 format).
    
    Args:
        text: Text to convert to speech
        language: Language code ('en', 'hi', etc.)
        output_path: Optional custom output path
    
    Returns:
        Path to generated mp3 file, or None on error.
    """
    if not text or not text.strip():
        return None
    
    try:
        import edge_tts
        
        voice = TTS_VOICES.get(language, TTS_VOICES["default"])
        
        if output_path is None:
            # Create temp file
            fd, output_path = tempfile.mkstemp(suffix=".mp3", prefix="tts_")
            os.close(fd)
        
        logger.info(f"Generating TTS with voice={voice}, text={text[:80]}...")
        
        # edge_tts is async — run in a separate thread to avoid
        # "asyncio.run() cannot be called from a running event loop" in FastAPI
        import asyncio
        import threading
        
        def _run_tts():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                communicate = edge_tts.Communicate(text, voice)
                loop.run_until_complete(communicate.save(output_path))
            finally:
                loop.close()
        
        t = threading.Thread(target=_run_tts)
        t.start()
        t.join(timeout=30)  # Wait up to 30s for TTS to complete
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"TTS generated: {output_path} ({os.path.getsize(output_path)} bytes)")
            return output_path
        else:
            logger.error("TTS generated empty file")
            return None
            
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        return None


def convert_mp3_to_ogg(mp3_path: str, output_ogg_path: str = None) -> str:
    """
    Convert mp3 to OGG/Opus format (WhatsApp audio message format).
    WhatsApp requires audio in OGG container with Opus codec.
    
    Args:
        mp3_path: Path to source mp3 file
        output_ogg_path: Optional output path
    
    Returns:
        Path to OGG file, or None on error.
    """
    if output_ogg_path is None:
        output_ogg_path = mp3_path.rsplit(".", 1)[0] + ".ogg"
    
    try:
        # ffmpeg: mp3 → ogg/opus
        cmd = [
            "ffmpeg", "-y",
            "-i", mp3_path,
            "-c:a", "libopus",
            "-b:a", "64k",
            "-application", "voip",
            output_ogg_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr[:500]}")
            return None
        
        logger.info(f"Converted to OGG/Opus: {output_ogg_path} ({os.path.getsize(output_ogg_path)} bytes)")
        return output_ogg_path
        
    except Exception as e:
        logger.error(f"MP3→OGG conversion error: {e}")
        return None


# ---------- Utility: Download WhatsApp Media ----------

def download_whatsapp_media(media_id: str, access_token: str) -> str:
    """
    Download media from WhatsApp Cloud API.
    1. GET /media/{media_id} → get media URL
    2. GET media URL → download actual file
    
    Args:
        media_id: WhatsApp media ID from webhook
        access_token: Meta access token
    
    Returns:
        Path to downloaded file, or None on error.
    """
    try:
        phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "")
        
        # Step 1: Get media URL
        url = f"https://graph.facebook.com/v21.0/{media_id}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        resp.raise_for_status()
        media_info = resp.json()
        media_url = media_info.get("url", "")
        mime_type = media_info.get("mime_type", "audio/ogg")
        
        if not media_url:
            logger.error(f"No media URL returned for media_id={media_id}")
            return None
        
        # Step 2: Download the actual file
        ext = ".ogg"
        if "mp3" in mime_type:
            ext = ".mp3"
        elif "wav" in mime_type:
            ext = ".wav"
        elif "m4a" in mime_type:
            ext = ".m4a"
        elif "ogg" in mime_type:
            ext = ".ogg"
        
        fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="wa_audio_")
        os.close(fd)
        
        resp2 = requests.get(media_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=60)
        resp2.raise_for_status()
        
        with open(temp_path, "wb") as f:
            f.write(resp2.content)
        
        logger.info(f"Downloaded media {media_id} → {temp_path} ({len(resp2.content)} bytes, {mime_type})")
        return temp_path
        
    except Exception as e:
        logger.error(f"Media download error: {e}", exc_info=True)
        return None