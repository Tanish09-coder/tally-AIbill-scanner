import pytest
from app.core.config import Settings

def test_config_defaults():
    test_settings = Settings(
        GEMINI_API_KEY="test_gemini",
        SARVAM_API_KEY="test_sarvam",
        TALLY_HOST="http://localhost",
        TALLY_PORT=9000
    )
    assert test_settings.tally_endpoint_url == "http://localhost:9000"
    assert test_settings.GEMINI_API_KEY == "test_gemini"
    assert test_settings.SARVAM_API_KEY == "test_sarvam"

def test_missing_keys_validation():
    test_settings = Settings(
        GEMINI_API_KEY="",
        SARVAM_API_KEY=""
    )
    is_valid, errors = test_settings.validate_api_keys(raise_on_error=False)
    assert is_valid is False
    assert len(errors) == 2
    assert "GEMINI_API_KEY" in errors[0]
    assert "SARVAM_API_KEY" in errors[1]

def test_placeholder_keys_validation():
    test_settings = Settings(
        GEMINI_API_KEY="your_gemini_api_key_here",
        SARVAM_API_KEY="your_sarvam_api_key_here"
    )
    is_valid, errors = test_settings.validate_api_keys(raise_on_error=False)
    assert is_valid is False
    assert len(errors) == 2

