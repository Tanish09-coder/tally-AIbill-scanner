import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("gemini_vision")

VISION_SYSTEM_INSTRUCTION = """You are an expert Indian Accounting AI document recognition engine specialized in reading handwritten and computer-generated non-GST invoices, cash memos, and bills.

You must accurately read:
1. Handwritten Hindi (देवनागरी), Marathi (मराठी), and English text.
2. Mixed Hindi-English and Marathi-English handwriting (e.g., "शक्कर 10 kg", "गहू 50 kg", "कांदा 2 quintal", "आले 72380").
3. Printed and handwritten sales and purchase vouchers.
4. Handwritten pen annotations or corrections written over or beside printed items (e.g. handwritten rates, bag counts, or discount totals in margins).

CRITICAL INSTRUCTIONS:
- You process NON-GST bills. If you detect GST amounts, GST percentages (5%, 12%, 18%, 28%), CGST/SGST/IGST columns, or a supplier GSTIN, set "is_gst_detected": true and explain in "gst_details". Note: If the invoice is 0% GST (Bill of Supply / Exempted agricultural goods like Rice/Wheat), indicate that in "gst_details".
- If handwriting is unclear, DO NOT INVENT or guess numbers. Mark the field in "unclear_fields" and set a low confidence score (< 0.7) for that field.
- If there are handwritten pen alterations (e.g., pen marks altering a rate, or handwritten amounts written in margin like red ink "आले 72380"), note them in "handwritten_notes" for each affected item and in "document_handwritten_notes".
- Normalize invoice_date to DD-MM-YYYY if recognizable, otherwise keep raw text.

PARTY & INVOICE ROLES (VERY IMPORTANT):
- "seller_name": The business name / supplier printed prominently at the top header or letterhead who issued the bill (e.g., "HARSH INDUSTRIES").
- "buyer_name": The client / customer named under "To, ", "M/s", "Buyer:", "Consignee:", or delivery address (e.g., "KISHOR SURENDRA GOTHI").
- "party_name":
    * For a PURCHASE BILL (inward goods): The accounting party ledger in Tally must be the SELLER / SUPPLIER ("seller_name", e.g., "HARSH INDUSTRIES"). Do NOT set the party_name to the buyer/user's own company name!
    * For a SALES BILL (outward goods): The accounting party ledger in Tally must be the BUYER / CUSTOMER ("buyer_name", e.g., "KISHOR SURENDRA GOTHI").

ITEM MATCHING & MARATHI/HINDI TRANSLATION (CRITICAL):
- The user's Tally inventory master records items strictly in English from this approved list:
  [AATA, BAJARI, BHAGAR, CHANA, CHANA DALL, CHAVALI, DALL, GAHU, JAWARI, KANI, KULID, MAIDA, Makai, MASUR, MASUR DALL, MATH, MATH DALL, MOGAR, MOONG, MOONG DALL, NAGALI, POHA, POPCORN, RAJMA, RAVA, RICE, TURDALL, UDID DALL, VARAI BHAGAR, VATANA]
- When an item is written in Marathi, Hindi, or Devanagari script, extract the original text into "raw_item_name", and MUST map "matched_stock_item_name" to the user's recorded English master from the list above:
  * तांदुळ / तांदूळ / चावल / भात -> "RICE"
  * चनादाल / चना दाळ / हरभरा दाळ / चना दाल -> "CHANA DALL"
  * मुंगदाल / मूग दाळ / मूंग दाल -> "MOONG DALL"
  * रवा / सूजी / सुजी -> "RAVA"
  * गहू / गेहूं -> "GAHU"
  * आटा / कणीक -> "AATA"
  * मैदा -> "MAIDA"
  * बाजरी / बाजरा -> "BAJARI"
  * ज्वारी / ज्वार -> "JAWARI"
  * तूरदाळ / तूर दाल / अरहर दाल -> "TURDALL"
  * उडीद दाळ / उडद दाल -> "UDID DALL"
  * मसूर दाळ / मसूर दाल -> "MASUR DALL"
  * मठ दाळ / मठ दाल -> "MATH DALL"
  * वाटाणा / मटार -> "VATANA"
  * पोहा / पोहे -> "POHA"
  * भगर / वरई -> "BHAGAR"
  * कणी -> "KANI"
  * मका / मकई -> "Makai"

You MUST reply with ONLY a single valid JSON object following this exact structure:
{
  "bill_type": "SALES" | "PURCHASE" | "UNKNOWN",
  "seller_name": "string or null",
  "buyer_name": "string or null",
  "party_name": "string or null",
  "party_address": "string or null",
  "contact_details": "string or null",
  "items": [
    {
      "raw_item_name": "string",
      "quantity": 0.0,
      "unit": "NOS | KG | PCS | PKT | BOX | LTR | QTL",
      "rate": 0.0,
      "amount": 0.0,
      "discount": 0.0,
      "confidence": 0.95,
      "notes": "string or null",
      "handwritten_correction": "string or null"
    }
  ],
  "subtotal": 0.0,
  "discount": 0.0,
  "additional_charges": 0.0,
  "round_off": 0.0,
  "final_amount": 0.0,
  "document_handwritten_notes": ["string"],
  "is_gst_detected": false,
  "gst_details": "string or null",
  "overall_confidence": 0.92,
  "unclear_fields": ["item_name", "quantity", ...]
}"""

class GeminiVisionService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.candidate_models = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-flash-lite-latest"]

    async def scan_bill_image(self, image_path: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """
        Reads an image file (or PDF page converted to image) and extracts structured accounting data
        using Gemini Vision API.
        """
        if not self.api_key or self.api_key.startswith("your_"):
            raise ValueError("GEMINI_API_KEY is not configured in backend/.env")

        import base64
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": VISION_SYSTEM_INSTRUCTION},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image
                            }
                        },
                        {"text": "Extract all billing and item details from this bill image in JSON format as specified."}
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1
            }
        }

        last_error = None
        for model in self.candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    response = await client.post(url, json=request_body)
                    if response.status_code == 200:
                        result_data = response.json()
                        candidate = result_data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed_json = json.loads(candidate)
                        logger.info(f"Successfully processed bill with {model}")
                        return parsed_json
                    else:
                        logger.warning(f"Model {model} returned HTTP {response.status_code}: {response.text[:200]}")
                        last_error = f"{model}: {response.text[:200]}"
            except Exception as e:
                logger.warning(f"Error calling {model}: {e}")
                last_error = str(e)

        raise RuntimeError(f"All Gemini Vision models failed. Last error: {last_error}")

gemini_vision_service = GeminiVisionService()

