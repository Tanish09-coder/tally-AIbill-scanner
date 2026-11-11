import os
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
ROOT_ENV_PATH = BASE_DIR.parent / ".env"

# Pick the first existing .env file, or fallback to backend/.env
selected_env = ENV_PATH if ENV_PATH.exists() else (ROOT_ENV_PATH if ROOT_ENV_PATH.exists() else ENV_PATH)

PLACEHOLDER_VALUES = {
    "your_gemini_api_key_here",
    "your_sarvam_api_key_here",
    "placeholder",
    "changeme",
    ""
}

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(selected_env),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # AI API Keys
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key for Vision & Document OCR")
    SARVAM_API_KEY: str = Field(default="", description="Sarvam AI API Key for Indian Hinglish Voice STT/TTS")

    # TallyPrime XML over HTTP Server
    TALLY_HOST: str = Field(default="http://localhost", description="TallyPrime HTTP Host")
    TALLY_PORT: int = Field(default=9000, description="TallyPrime HTTP Port")

    # Storage & Database
    DATABASE_URL: str = Field(default=f"sqlite+aiosqlite:///{str(BASE_DIR / 'app.db').replace('\\', '/')}")
    UPLOAD_DIR: str = Field(default=str(BASE_DIR / "uploads"))

    # Security & Server
    SECRET_KEY: str = Field(default="dev_secret_key_accounting_app_change_in_prod")
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000")
    BACKEND_HOST: str = Field(default="0.0.0.0")
    BACKEND_PORT: int = Field(default=8000)

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def tally_endpoint_url(self) -> str:
        host = self.TALLY_HOST.rstrip("/")
        return f"{host}:{self.TALLY_PORT}"

    def validate_api_keys(self, raise_on_error: bool = False) -> tuple[bool, List[str]]:
        """
        Validates whether required keys are present and not placeholder values.
        Returns (is_valid, list_of_error_messages).
        """
        errors = []
        
        gemini_val = self.GEMINI_API_KEY.strip()
        if not gemini_val or gemini_val.lower() in PLACEHOLDER_VALUES:
            errors.append(
                "❌ GEMINI_API_KEY is missing or set to placeholder in backend/.env\n"
                "   -> Required for AI Vision OCR & handwritten bill understanding.\n"
                "   -> Get your API key from Google AI Studio: https://aistudio.google.com/"
            )

        sarvam_val = self.SARVAM_API_KEY.strip()
        if not sarvam_val or sarvam_val.lower() in PLACEHOLDER_VALUES:
            errors.append(
                "❌ SARVAM_API_KEY is missing or set to placeholder in backend/.env\n"
                "   -> Required for natural conversational Indian Hinglish Speech-to-Text & Text-to-Speech.\n"
                "   -> Get your API key from Sarvam AI: https://dashboard.sarvam.ai/"
            )

        if errors and raise_on_error:
            banner = "\n" + "="*70 + "\n[STARTUP CONFIGURATION ERROR] Missing Required API Keys\n" + "="*70 + "\n"
            full_msg = banner + "\n\n".join(errors) + f"\n\nPlease edit '{ENV_PATH}' to supply valid keys.\n" + "="*70 + "\n"
            raise ValueError(full_msg)

        return (len(errors) == 0, errors)


settings = Settings()

