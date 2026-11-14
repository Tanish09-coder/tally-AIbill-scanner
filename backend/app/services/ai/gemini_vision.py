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

DATE & INVOICE NUMBER EXTRACTION (CRITICAL):
- "invoice_date": Thoroughly inspect the bill header, corners, rubber stamps, handwritten margin notes, or date fields (labelled as दिनांक, Date, Dt, तारीख, or standalone DD/MM/YYYY or DD/MM/YY e.g. 15/04/2025, 12-5-25, etc.). Always convert and format as DD-MM-YYYY (e.g., "15-04-2025"). Never leave null if any date is printed, written or stamped on the bill!
- "invoice_number": Look for bill no., memo no., पावती क्र., बिल क्र., or inv no.

MARATHI & DEVANAGARI NUMERALS CONVERSION (ESSENTIAL FOR HANDWRITTEN BILLS):
- Many handwritten bills, Mandi parchas, and sales bill books in Maharashtra use Marathi/Devanagari numerals for quantities, rates, and amounts.
- You MUST recognize Devanagari digits and translate them directly into standard Western Arabic numbers:
  * ० -> 0
  * १ -> 1
  * २ -> 2
  * ३ -> 3
  * ४ -> 4
  * ५ -> 5
  * ६ -> 6
  * ७ -> 7
  * ८ -> 8
  * ९ -> 9
- Examples of Devanagari handwritten number translation:
  * संख्या "१५०" or "१५० कट्टे" -> quantity: 150.0
  * संख्या "१७०" -> quantity: 170.0
  * संख्या "१३०" -> quantity: 130.0
  * दर "१५००/-" or "१५००" -> rate: 1500.0
  * दर "८५००/-" -> rate: 8500.0
  * रक्कम "२२५००|००" or "२२५००।००" -> amount: 22500.0
  * रक्कम "१२६००|००" -> amount: 12600.0
  * रक्कम "१०२००|००" -> amount: 10200.0
  * एकूण / बाकी "४५३००|००" -> final_amount: 45300.0
  * हमाली "१०/-" or "१०" -> additional_charges: 10.0
- Mandi Table Columns & Notation:
  * In handwritten tables with "संख्या" (quantity), "दर" (rate), and "रक्कम / रुपये / पैसे" (amount):
    - The vertical pipe or danda `|` or `।` separates Rupees and Paise (e.g., `२२५०० | ००` means 22500.00).
    - A trailing slash-dash `/-` represents exact rupees (e.g. `१५००/-` = 1500).
    - "एकूण येणे बाकी", "एकूण बाकी", or "एकूण" indicates the final bill total ("final_amount").
    - If there are additions like "हमाली" or deductions like "कमिशन / सूट", map them to "additional_charges" or "discount".
- Photo Orientation & Sideways Bills:
  * If the bill was photographed horizontally / 90° sideways, rotate and read the headers, columns, and rows upright so you never confuse rows or misread handwritten digits.

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
  "invoice_number": "string or null",
  "invoice_date": "DD-MM-YYYY or null",
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
        self._key_index = 0

    def get_keys(self) -> List[str]:
        keys = settings.gemini_keys_list
        if not keys and self.api_key and not self.api_key.startswith("your_"):
            keys = [self.api_key]
        return keys

    async def scan_with_groq(self, b64_image: str, mime_type: str) -> Optional[Dict[str, Any]]:
        """Ultra-fast Llama-3.2 Vision OCR via Groq API when key is configured."""
        groq_key = settings.GROQ_API_KEY
        if not groq_key or groq_key.startswith("your_") or len(groq_key.strip()) < 10:
            return None

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{VISION_SYSTEM_INSTRUCTION}\nExtract all billing and item details from this bill image in JSON format as specified."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}}
                    ]
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info("Successfully processed bill using Groq Llama-3.2 Vision!")
                    return json.loads(content)
                else:
                    logger.warning(f"Groq Vision returned HTTP {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.warning(f"Groq Vision error: {e}")
        return None

    async def scan_bill_image(self, image_path: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
        """
        Reads an image file (or PDF page converted to image) and extracts structured accounting data
        using Groq (if provided) or Gemini Vision API with automatic multi-key rotation and model fallback.
        """
        import base64
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        # 1. Try Groq Vision first if user configured GROQ_API_KEY
        groq_res = await self.scan_with_groq(b64_image, mime_type)
        if groq_res:
            return groq_res

        # 2. Gemini Vision with multi-key rotation
        keys = self.get_keys()
        if not keys:
            raise ValueError("No valid GEMINI_API_KEY or GROQ_API_KEY is configured in backend/.env")

        # Rotate keys for concurrent load balancing
        start_idx = self._key_index % len(keys)
        self._key_index += 1
        ordered_keys = keys[start_idx:] + keys[:start_idx]

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
        for key in ordered_keys:
            masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"
            for model in self.candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                try:
                    async with httpx.AsyncClient(timeout=25.0) as client:
                        response = await client.post(url, json=request_body)
                        if response.status_code == 200:
                            result_data = response.json()
                            candidate = result_data["candidates"][0]["content"]["parts"][0]["text"]
                            parsed_json = json.loads(candidate)
                            logger.info(f"Successfully processed bill with {model} (key: {masked_key})")
                            return parsed_json
                        else:
                            logger.warning(f"Model {model} with key {masked_key} returned HTTP {response.status_code}: {response.text[:200]}")
                            last_error = f"{model} ({masked_key}): {response.text[:200]}"
                except Exception as e:
                    logger.warning(f"Error calling {model} with key {masked_key}: {e}")
                    last_error = str(e)

        raise RuntimeError(f"All Vision models/keys failed. Last error: {last_error}")

gemini_vision_service = GeminiVisionService()

