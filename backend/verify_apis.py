"""
Connectivity and Configuration Verification Script
Tests:
1. Environment file (.env) and Key Validation
2. Gemini API Connection (Vision OCR)
3. Sarvam AI Connection (Hinglish Voice STT/TTS)
4. TallyPrime XML-over-HTTP Connection
"""

import sys
import os
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings

def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "[NOT SET / INVALID]"
    return f"{key[:4]}...{key[-4:]} (Length: {len(key)})"

async def test_gemini_api(api_key: str) -> dict:
    import httpx
    if not api_key or api_key.startswith("your_"):
        return {"status": "SKIPPED", "message": "GEMINI_API_KEY is not set in backend/.env"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "").split("/")[-1] for m in data.get("models", [])]
                flash_models = [m for m in models if "flash" in m or "pro" in m]
                return {
                    "status": "SUCCESS",
                    "message": f"Successfully authenticated with Gemini API. Available models: {', '.join(flash_models[:4])}"
                }
            else:
                return {
                    "status": "FAILED",
                    "message": f"Gemini API returned HTTP {response.status_code}: {response.text[:200]}"
                }
    except Exception as e:
        return {"status": "ERROR", "message": f"Could not connect to Gemini API: {str(e)}"}

async def test_sarvam_api(api_key: str) -> dict:
    import httpx
    if not api_key or api_key.startswith("your_"):
        return {"status": "SKIPPED", "message": "SARVAM_API_KEY is not set in backend/.env"}

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": ["Namaste, testing connection."],
        "target_language_code": "hi-IN",
        "speaker": "priya",
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.0,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v3"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return {
                    "status": "SUCCESS",
                    "message": "Successfully authenticated with Sarvam AI API and verified TTS endpoint."
                }
            elif response.status_code == 401 or response.status_code == 403:
                return {
                    "status": "FAILED",
                    "message": f"Sarvam AI authentication failed (HTTP {response.status_code}): Invalid subscription key."
                }
            else:
                return {
                    "status": "FAILED",
                    "message": f"Sarvam AI returned HTTP {response.status_code}: {response.text[:200]}"
                }
    except Exception as e:
        return {"status": "ERROR", "message": f"Could not connect to Sarvam AI: {str(e)}"}

async def test_tally_connection(host: str, port: int) -> dict:
    import httpx
    tally_url = f"{host.rstrip('/')}:{port}"
    # Standard Tally XML request for Company List
    xml_request = """<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>List of Companies</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.post(
                tally_url,
                content=xml_request.encode("utf-8"),
                headers={"Content-Type": "text/xml;charset=utf-8"}
            )
            if response.status_code == 200 and "<COMPANY" in response.text.upper():
                return {
                    "status": "CONNECTED",
                    "message": f"TallyPrime is reachable at {tally_url} and returned company data."
                }
            elif response.status_code == 200:
                return {
                    "status": "CONNECTED_NO_COMPANY",
                    "message": f"TallyPrime is reachable at {tally_url}, but no active company is loaded."
                }
            else:
                return {
                    "status": "ERROR_RESPONSE",
                    "message": f"Tally responded with HTTP {response.status_code}: {response.text[:150]}"
                }
    except httpx.ConnectError:
        return {
            "status": "DISCONNECTED",
            "message": f"Cannot connect to TallyPrime at {tally_url}. Ensure TallyPrime is running and HTTP Server is enabled on port {port} (F12 > Advanced Configuration)."
        }
    except Exception as e:
        return {
            "status": "DISCONNECTED",
            "message": f"Connection check failed: {str(e)}"
        }

async def main():
    print("=" * 70)
    print("AI BILL SCANNER & TALLYPRIME AUTOMATION - CONFIGURATION CHECK")
    print("=" * 70)
    
    print("\n[1] Environment & Keys Loaded:")
    print(f"  • GEMINI_API_KEY: {mask_key(settings.GEMINI_API_KEY)}")
    print(f"  • SARVAM_API_KEY: {mask_key(settings.SARVAM_API_KEY)}")
    print(f"  • TALLY_ENDPOINT: {settings.tally_endpoint_url}")
    print(f"  • DATABASE_URL  : {settings.DATABASE_URL}")

    is_valid, errors = settings.validate_api_keys(raise_on_error=False)
    if not is_valid:
        print("\n⚠️  CONFIGURATION ISSUES FOUND:")
        for err in errors:
            print(f"  {err}\n")
    else:
        print("\n✅ All required environment variables are set.")

    print("\n[2] Testing External Service Connectivity...")
    
    print("  Testing Google Gemini API...")
    gemini_result = await test_gemini_api(settings.GEMINI_API_KEY)
    print(f"  Result: [{gemini_result['status']}] {gemini_result['message']}")

    print("\n  Testing Sarvam AI API...")
    sarvam_result = await test_sarvam_api(settings.SARVAM_API_KEY)
    print(f"  Result: [{sarvam_result['status']}] {sarvam_result['message']}")

    print("\n  Testing Local TallyPrime Connection...")
    tally_result = await test_tally_connection(settings.TALLY_HOST, settings.TALLY_PORT)
    print(f"  Result: [{tally_result['status']}] {tally_result['message']}")

    print("\n" + "=" * 70)
    if not is_valid:
        print("NEXT STEP: Add your real API keys in 'backend/.env' to enable AI and Voice features.")
    else:
        print("ALL CONFIGURATION VALIDATION COMPLETED.")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())

