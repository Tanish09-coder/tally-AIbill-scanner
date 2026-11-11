from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.services.voice.sarvam_service import sarvam_voice_service

router = APIRouter(prefix="/voice", tags=["Voice Assistant"])

class TTSRequest(BaseModel):
    text: str
    speaker: Optional[str] = "priya"

@router.post("/tts")
async def generate_speech(payload: TTSRequest):
    """
    Synthesizes conversational Hinglish text into spoken audio using Sarvam AI.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    try:
        res = await sarvam_voice_service.text_to_speech(payload.text, speaker=payload.speaker)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice synthesis failed: {str(e)}")

@router.post("/stt")
async def transcribe_speech(audio_file: UploadFile = File(...)):
    """
    Transcribes microphone audio from user (Hinglish/Hindi/English) into text using Sarvam AI STT.
    """
    content = await audio_file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file received.")

    try:
        res = await sarvam_voice_service.speech_to_text(content, filename=audio_file.filename or "recording.wav")
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech transcription failed: {str(e)}")

