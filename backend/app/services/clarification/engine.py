from typing import List, Dict, Any, Optional
import re
from app.models.clarification import ClarificationQuestion

class ClarificationEngine:
    """
    Manages conversational Hinglish clarification generation and response parsing.
    Behaves like an intelligent Indian accountant speaking natural Hinglish.
    """

    @staticmethod
    def generate_questions_for_bill(
        bill_data: Dict[str, Any],
        validation_issues: List[Any],
        unmatched_party: Optional[str] = None,
        unmatched_items: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        questions = []

        # 1. GST Detected Question
        if bill_data.get("is_gst_detected", False):
            questions.append({
                "field_name": "is_gst_detected",
                "question_type": "GST_DETECTED",
                "target_item_id": None,
                "question_hinglish": "Is bill mein GST tax lines detect hui hain. Ye system strictly Non-GST vouchers ke liye configured hai. Kya aap isko Non-GST voucher ki tarah proceed karna chahte hain?"
            })

        # 2. Missing or Unclear Party
        if not bill_data.get("party_name"):
            questions.append({
                "field_name": "party_name",
                "question_type": "MISSING_PARTY",
                "target_item_id": None,
                "question_hinglish": "Bill par party ka naam clearly read nahi ho raha. Please party ka naam bataiye."
            })
        elif unmatched_party:
            questions.append({
                "field_name": "party_name",
                "question_type": "UNMATCHED_PARTY",
                "target_item_id": None,
                "question_hinglish": f"Ye party '{unmatched_party}' aapke Tally mein nahi mil rahi. Kya main iska new ledger create kar doon, ya existing ledger se match karna hai?"
            })

        # 3. Unclear Items or Unmatched Items or Handwritten Corrections
        items = bill_data.get("items", [])
        for idx, item in enumerate(items):
            raw_name = item.get("raw_item_name", "").strip()
            confidence = float(item.get("confidence", 1.0))
            qty = float(item.get("quantity", 0.0))
            rate = float(item.get("rate", 0.0))
            hw_corr = item.get("handwritten_correction")

            if hw_corr:
                questions.append({
                    "field_name": "rate",
                    "question_type": "HANDWRITTEN_CORRECTION",
                    "target_item_id": item.get("id"),
                    "question_hinglish": f"Item '{raw_name}' ke printed amount ke paas pen se '{hw_corr}' likha hai. Kya aap printed rate ya pen se likha amount use karna chahte hain?"
                })

            if confidence < 0.75 or not raw_name or "unclear" in raw_name.lower():
                questions.append({
                    "field_name": "item_name",
                    "question_type": "UNCLEAR_ITEM",
                    "target_item_id": item.get("id"),
                    "question_hinglish": f"Item number {idx+1} ka naam handwriting mein clear nahi hai. Please bataiye ye kaunsa item hai?"
                })
            elif unmatched_items and raw_name in unmatched_items:
                questions.append({
                    "field_name": "item_name",
                    "question_type": "UNMATCHED_ITEM",
                    "target_item_id": item.get("id"),
                    "question_hinglish": f"Stock item '{raw_name}' Tally mein nahi mila. Kya main new stock item create kar doon, ya kisi existing item se link karein?"
                })

            if qty <= 0:
                questions.append({
                    "field_name": "quantity",
                    "question_type": "UNCLEAR_QTY",
                    "target_item_id": item.get("id"),
                    "question_hinglish": f"Item '{raw_name or f'#{idx+1}'}' ki quantity clearly visible nahi hai. Please quantity bataiye."
                })

            if rate <= 0 and item.get("amount", 0.0) <= 0:
                questions.append({
                    "field_name": "rate",
                    "question_type": "UNCLEAR_RATE",
                    "target_item_id": item.get("id"),
                    "question_hinglish": f"Item '{raw_name or f'#{idx+1}'}' ka rate ya amount clearly read nahi ho raha. Please rate bataiye."
                })

        # 4. Handwritten Marginal Notes on document (e.g., 'आले 72380')
        hw_notes = bill_data.get("document_handwritten_notes", [])
        for note in hw_notes:
            note_str = str(note).strip()
            # Only ask about amount if note mentions monetary keywords or large numbers
            has_amount = any(w in note_str.lower() for w in ["rs", "rupay", "total", "आले", "बाकी", "final", "amt", "amount", "paid"]) or re.search(r'\b\d{3,}\b', note_str)
            if has_amount:
                questions.append({
                    "field_name": "final_amount",
                    "question_type": "HANDWRITTEN_NOTE",
                    "target_item_id": None,
                    "question_hinglish": f"Bill par pen se note '{note_str}' likha hai. Kya voucher mein printed total lena hai ya ye handwritten amount?"
                })

        # 5. Arithmetic issues from validator
        for issue in validation_issues:
            if getattr(issue, "issue_type", "") == "MATH_MISMATCH" and "final_amount" in getattr(issue, "field", ""):
                questions.append({
                    "field_name": "final_amount",
                    "question_type": "UNCLEAR_AMOUNT",
                    "target_item_id": None,
                    "question_hinglish": "Bill ka total amount verify nahi ho pa raha. Items ka sum aur bill ka total differ kar rahe hain. Please final total amount confirm kijiye."
                })

        return questions

    @staticmethod
    def parse_numeric_hinglish(user_input: str) -> Optional[float]:
        """
        Parses numbers from Hinglish spoken input (e.g. 'das kilo', 'so rupay', '2500', 'panch').
        """
        text = user_input.lower().strip()
        
        # Check standard digits first
        digits = re.findall(r"[-+]?\d*\.\d+|\d+", text)
        if digits:
            try:
                return float(digits[0])
            except ValueError:
                pass

        # Indian words map
        words_map = {
            "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
            "chhe": 6, "che": 6, "saat": 7, "aath": 8, "ath": 8, "nau": 9, "das": 10,
            "gyarah": 11, "barah": 12, "pandrah": 15, "bees": 20, "pachees": 25,
            "tees": 30, "chalis": 40, "pachas": 50, "sau": 100, "hazaar": 1000, "hazar": 1000
        }
        for word, val in words_map.items():
            if word in text:
                return float(val)

        return None

clarification_engine = ClarificationEngine()

