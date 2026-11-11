import base64
import logging
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("sarvam_service")

class SarvamVoiceService:
    """
    Integrates with Sarvam AI for natural Indian Hinglish Speech-to-Text (STT)
    and Text-to-Speech (TTS).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.tts_url = "https://api.sarvam.ai/text-to-speech"
        self.stt_url = "https://api.sarvam.ai/speech-to-text"
        self.default_speaker = "priya"
        self.tts_model = "bulbul:v3"
        self.stt_model = "saarika:v2"

    async def text_to_speech(self, text: str, speaker: Optional[str] = None) -> Dict[str, Any]:
        """
        Converts Hinglish text into spoken Indian voice audio.
        Returns base64 encoded audio string and format.
        """
        if not self.api_key or self.api_key.startswith("your_"):
            raise ValueError("SARVAM_API_KEY is not configured in backend/.env")

        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [text],
            "target_language_code": "hi-IN",
            "speaker": speaker or self.default_speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.0,
            "speech_sample_rate": 8000,
            "enable_preprocessing": True,
            "model": self.tts_model
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(self.tts_url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"Sarvam TTS failed: {resp.text}")
                raise RuntimeError(f"Sarvam TTS error ({resp.status_code}): {resp.text}")

            data = resp.json()
            # Returns list of base64 audio strings in data['audios']
            audios = data.get("audios", [])
            if not audios:
                raise RuntimeError("No audio returned from Sarvam TTS")

            return {
                "audio_base64": audios[0],
                "format": "wav",
                "text": text,
                "speaker": speaker or self.default_speaker
            }

    async def speech_to_text(self, audio_bytes: bytes, filename: str = "voice_input.wav") -> Dict[str, Any]:
        """
        Transcribes spoken audio into Hinglish text using Sarvam AI Saarika.
        """
        if not self.api_key or self.api_key.startswith("your_"):
            raise ValueError("SARVAM_API_KEY is not configured in backend/.env")

        headers = {
            "api-subscription-key": self.api_key
        }
        files = {
            "file": (filename, audio_bytes, "audio/wav")
        }
        data = {
            "model": self.stt_model,
            "language_code": "unknown" # Automatically detect Indian language / Hinglish
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(self.stt_url, headers=headers, files=files, data=data)
            if resp.status_code != 200:
                logger.error(f"Sarvam STT failed: {resp.text}")
                raise RuntimeError(f"Sarvam STT error ({resp.status_code}): {resp.text}")

            result = resp.json()
            transcript = result.get("transcript", "").strip()
            return {
                "transcript": transcript,
                "language_code": result.get("language_code", "hi-IN")
            }

sarvam_voice_service = SarvamVoiceService()

