import difflib
import re
from typing import List, Dict, Any, Optional, Tuple

class MasterMatcher:
    """
    Intelligent fuzzy matching engine for comparing extracted bill text
    (handwritten or printed) against existing TallyPrime masters (Ledgers & Stock Items).
    Handles Indian business naming patterns like location suffixes (', Ghoti', ', Rahata'),
    spelling variations, and punctuation.
    """

    @staticmethod
    def calculate_similarity(a: str, b: str) -> float:
        """
        Calculates normalized string similarity score (0.0 to 1.0) with
        token-subset, prefix boost, and Jaccard overlap.
        """
        if not a or not b:
            return 0.0

        clean_a = re.sub(r'[,.\-_/()[\]]', ' ', a).strip().lower()
        clean_b = re.sub(r'[,.\-_/()[\]]', ' ', b).strip().lower()
        clean_a = ' '.join(clean_a.split())
        clean_b = ' '.join(clean_b.split())

        if clean_a == clean_b:
            return 1.0

        words_a = set(clean_a.split())
        words_b = set(clean_b.split())

        seq_ratio = difflib.SequenceMatcher(None, clean_a, clean_b).ratio()

        # Prefix match boost (e.g. "harsh industries" inside "harsh industries , ghoti")
        if clean_b.startswith(clean_a) or clean_a.startswith(clean_b):
            min_len = min(len(clean_a), len(clean_b))
            max_len = max(len(clean_a), len(clean_b))
            prefix_score = 0.90 + (min_len / max_len) * 0.08
            seq_ratio = max(seq_ratio, prefix_score)

        # Word subset check (e.g. all words of "HARSH INDUSTRIES" are inside "Harsh Industries , Ghoti")
        if words_a and words_b and (words_a.issubset(words_b) or words_b.issubset(words_a)):
            common = len(words_a & words_b)
            total = max(len(words_a), len(words_b))
            token_score = 0.88 + (common / total) * 0.10
            seq_ratio = max(seq_ratio, token_score)

        # Jaccard word intersection
        intersection = words_a & words_b
        if intersection:
            jaccard = len(intersection) / len(words_a | words_b)
            if jaccard >= 0.5:
                seq_ratio = max(seq_ratio, 0.70 + (jaccard * 0.25))

        return round(seq_ratio, 3)

    @classmethod
    def find_best_ledger_match(
        cls,
        extracted_name: str,
        tally_ledgers: List[Dict[str, Any]],
        threshold: float = 0.60
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the single best matching ledger from Tally masters.
        Returns dict with name, parent, and score if >= threshold, else None.
        """
        if not extracted_name or not tally_ledgers:
            return None

        clean_ext = extracted_name.strip().lower()
        # Direct exact match check
        for l in tally_ledgers:
            if l.get("name", "").strip().lower() == clean_ext:
                return {"name": l["name"], "parent": l.get("parent"), "score": 1.0, "is_exact": True}

        best = None
        best_score = 0.0

        for l in tally_ledgers:
            name = l.get("name", "")
            score = cls.calculate_similarity(extracted_name, name)
            if score > best_score:
                best_score = score
                best = {"name": name, "parent": l.get("parent"), "score": score, "is_exact": score >= 0.98}

        if best and best_score >= threshold:
            return best
        return None

    @classmethod
    def get_top_ledger_matches(
        cls,
        extracted_name: str,
        tally_ledgers: List[Dict[str, Any]],
        limit: int = 5,
        threshold: float = 0.55
    ) -> List[Dict[str, Any]]:
        """
        Returns ranked list of candidate ledgers matching the extracted name.
        """
        if not extracted_name or not tally_ledgers:
            return []

        scored = []
        for l in tally_ledgers:
            name = l.get("name", "")
            score = cls.calculate_similarity(extracted_name, name)
            if score >= threshold:
                scored.append({
                    "name": name,
                    "parent": l.get("parent"),
                    "score": score,
                    "is_exact": score >= 0.98
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    @classmethod
    def match_party(
        cls,
        extracted_name: str,
        tally_ledgers: List[Dict[str, str]],
        threshold_reliable: float = 0.85,
        threshold_candidate: float = 0.55
    ) -> Dict[str, Any]:
        """
        Matches extracted party name against Tally ledgers.
        Returns:
            - status: "EXACT_MATCH" | "RELIABLE_MATCH" | "MULTIPLE_CANDIDATES" | "NO_MATCH"
            - matched_name: str or None
            - candidates: List[Tuple[str, float]]
        """
        if not extracted_name or not tally_ledgers:
            return {"status": "NO_MATCH", "matched_name": None, "candidates": []}

        scored = []
        for ledger in tally_ledgers:
            name = ledger["name"]
            score = cls.calculate_similarity(extracted_name, name)
            if score >= threshold_candidate:
                scored.append((name, round(score, 2)))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return {"status": "NO_MATCH", "matched_name": None, "candidates": []}

        best_match, best_score = scored[0]

        if best_score >= 0.98:
            return {"status": "EXACT_MATCH", "matched_name": best_match, "candidates": scored[:3]}
        elif best_score >= threshold_reliable:
            if len(scored) > 1 and (best_score - scored[1][1] < 0.05):
                return {"status": "MULTIPLE_CANDIDATES", "matched_name": None, "candidates": scored[:3]}
            return {"status": "RELIABLE_MATCH", "matched_name": best_match, "candidates": scored[:3]}
        else:
            return {"status": "MULTIPLE_CANDIDATES", "matched_name": None, "candidates": scored[:3]}

    MARATHI_HINDI_COMMODITY_MAP = {
        # Rice / Tandul
        "तांदुळ": "RICE", "तांदूळ": "RICE", "तांदुल": "RICE", "तांदूल": "RICE",
        "चावल": "RICE", "भात": "RICE", "धान": "RICE", "पॅडी": "RICE", "कणी": "KANI",
        "tandul": "RICE", "tandool": "RICE", "chawal": "RICE", "bhat": "RICE", "rice": "RICE",

        # Chana & Chana Dall
        "चनादाल": "CHANA DALL", "चनादाळ": "CHANA DALL", "चना दाळ": "CHANA DALL", "चना दाल": "CHANA DALL",
        "हरभरा दाळ": "CHANA DALL", "हरभरा डाळ": "CHANA DALL", "चना डाळ": "CHANA DALL", "चनाडाळ": "CHANA DALL",
        "चना": "CHANA", "हरभरा": "CHANA", "छोले": "CHANA",
        "chana dal": "CHANA DALL", "chana dall": "CHANA DALL", "chana daal": "CHANA DALL",
        "harbhara dal": "CHANA DALL", "chana": "CHANA",

        # Moong & Moong Dall
        "मुंगदाल": "MOONG DALL", "मुंग दाल": "MOONG DALL", "मूंग दाल": "MOONG DALL", "मूग दाळ": "MOONG DALL",
        "मुग दाळ": "MOONG DALL", "मुंगदाळ": "MOONG DALL", "मूगडाळ": "MOONG DALL", "मुगडाळ": "MOONG DALL",
        "मुंग डाळ": "MOONG DALL", "मूंग डाळ": "MOONG DALL", "मोगर": "MOGAR",
        "मुंग": "MOONG", "मूंग": "MOONG", "मूग": "MOONG", "मुग": "MOONG",
        "mung dal": "MOONG DALL", "moong dal": "MOONG DALL", "moong dall": "MOONG DALL", "moong": "MOONG", "mogar": "MOGAR",

        # Rava / Sooji
        "रवा": "RAVA", "सूजी": "RAVA", "सुजी": "RAVA", "सवा": "RAVA",
        "rava": "RAVA", "rawa": "RAVA", "sooji": "RAVA", "suji": "RAVA",

        # Wheat & Wheat Products
        "गहू": "GAHU", "गहु": "GAHU", "गेहूं": "GAHU", "गेहू": "GAHU",
        "आटा": "AATA", "कणीक": "AATA", "गव्हाचे पीठ": "AATA", "आटा गोणी": "AATA GONI",
        "मैदा": "MAIDA",
        "gahu": "GAHU", "gehu": "GAHU", "gehun": "GAHU", "atta": "AATA", "aata": "AATA", "maida": "MAIDA",

        # Toor / Tur Dall
        "तूरदाळ": "TURDALL", "तूर दाळ": "TURDALL", "तूर दाल": "TURDALL", "तुर दाळ": "TURDALL", "अरहर दाल": "TURDALL", "तुरी": "TURDALL", "तूर": "TURDALL",
        "tur dal": "TURDALL", "turdall": "TURDALL", "toor dal": "TURDALL", "arhar dal": "TURDALL",

        # Urad / Udid Dall
        "उडीद दाळ": "UDID DALL", "उडीद दाल": "UDID DALL", "उडद दाल": "UDID DALL", "उडीदडाळ": "UDID DALL", "उडद": "UDID DALL", "उडीद": "UDID DALL",
        "udid dal": "UDID DALL", "udid dall": "UDID DALL", "urad dal": "UDID DALL",

        # Masoor / Masur Dall
        "मसूर दाळ": "MASUR DALL", "मसूर दाल": "MASUR DALL", "मसूरडाळ": "MASUR DALL", "मसूर": "MASUR",
        "masur dal": "MASUR DALL", "masoor dal": "MASUR DALL", "masur": "MASUR",

        # Math & Math Dall
        "मठ दाळ": "MATH DALL", "मठ दाल": "MATH DALL", "मठडाळ": "MATH DALL", "मठ": "MATH", "मटकी": "MATH",
        "math dal": "MATH DALL", "math": "MATH",

        # Bajra / Bajari
        "बाजरी": "BAJARI", "बाजरा": "BAJARI", "bajari": "BAJARI", "bajra": "BAJARI",

        # Jowar / Jawari
        "ज्वारी": "JAWARI", "ज्वार": "JAWARI", "jawari": "JAWARI", "jowar": "JAWARI",

        # Corn / Makai
        "मका": "Makai", "मकई": "Makai", "कॉर्न": "Makai", "पॉपकॉर्न": "POPCORN", "makai": "Makai", "popcorn": "POPCORN",

        # Poha
        "पोहा": "POHA", "पोहे": "POHA", "poha": "POHA",

        # Vatana / Peas
        "वाटाणा": "VATANA", "वटाणा": "VATANA", "मटार": "VATANA", "vatana": "VATANA", "matar": "VATANA",

        # Chavali
        "चवळी": "CHAVALI", "लोबिया": "CHAVALI", "chavali": "CHAVALI",

        # Rajma
        "राजमा": "RAJMA", "राजमा दाना": "RAJMA", "rajma": "RAJMA",

        # Nagali
        "नागली": "NAGALI", "नाचणी": "NAGALI", "रागी": "NAGALI", "nagali": "NAGALI",

        # Bhagar / Varai
        "भगर": "BHAGAR", "वरई भगर": "VARAI BHAGAR", "वरई": "VARAI BHAGAR", "bhagar": "BHAGAR",

        # Kulid
        "कुळीथ": "KULID", "कुलथी": "KULID", "kulid": "KULID",

        # Generic Dall
        "दाळ": "DALL", "दाल": "DALL", "dal": "DALL", "dall": "DALL"
    }

    @classmethod
    def match_stock_item(
        cls,
        extracted_name: str,
        tally_stock_items: List[Dict[str, Any]],
        threshold_reliable: float = 0.85,
        threshold_candidate: float = 0.55
    ) -> Dict[str, Any]:
        """
        Matches extracted item name against existing Tally stock items.
        Handles:
        1. Multilingual Marathi / Hindi / Devanagari translation (e.g. 'तांदुळ' -> 'RICE', 'चनादाल' -> 'CHANA DALL').
        2. Base Commodity Extraction (stripping brand names, packaging, varieties).
        3. Fuzzy string matching fallback.
        """
        if not extracted_name or not tally_stock_items:
            return {"status": "NO_MATCH", "matched_name": None, "unit": "NOS", "candidates": []}

        items_by_name = {item["name"]: item for item in tally_stock_items}

        # 1. Multilingual Marathi / Hindi / Indic Translation to Recorded Tally Masters
        clean_ext_lower = extracted_name.strip().lower()
        norm_ext = clean_ext_lower.replace("ळ", "ल").replace("ू", "ु").replace("ी", "ि")
        
        sorted_dict_keys = sorted(cls.MARATHI_HINDI_COMMODITY_MAP.keys(), key=lambda x: len(x), reverse=True)
        for key in sorted_dict_keys:
            key_lower = key.lower()
            key_norm = key_lower.replace("ळ", "ल").replace("ू", "ु").replace("ी", "ि")
            if key_lower in clean_ext_lower or key_norm in norm_ext:
                target_commodity = cls.MARATHI_HINDI_COMMODITY_MAP[key]
                # Check exact match in user's Tally masters
                for m_item in tally_stock_items:
                    m_name = m_item["name"]
                    if m_name.strip().lower() == target_commodity.strip().lower():
                        return {
                            "status": "EXACT_MATCH",
                            "matched_name": m_name,
                            "unit": m_item.get("unit") or "KG",
                            "candidates": [(m_name, 1.0)]
                        }
                # Check partial match in user's Tally masters
                for m_item in tally_stock_items:
                    m_name = m_item["name"]
                    if target_commodity.lower() in m_name.lower():
                        return {
                            "status": "RELIABLE_MATCH",
                            "matched_name": m_name,
                            "unit": m_item.get("unit") or "KG",
                            "candidates": [(m_name, 0.95)]
                        }

        # 2. Base Commodity Extraction (English whole words):
        # Check if any Tally stock item exists as distinct word(s) in the raw bill text
        clean_raw = re.sub(r'[,.\-_/()[\]0-9]', ' ', extracted_name).lower()
        raw_words = set(clean_raw.split())

        # Sort Tally masters by word count and length descending (so 'CHANA DALL' matches before 'CHANA')
        sorted_masters = sorted(tally_stock_items, key=lambda x: (len(x["name"].split()), len(x["name"])), reverse=True)
        for item in sorted_masters:
            name = item["name"]
            clean_m = re.sub(r'[,.\-_/()[\]0-9]', ' ', name).lower()
            m_words = clean_m.split()
            if m_words and all(w in raw_words for w in m_words):
                item_unit = item.get("unit") or "KG"
                return {
                    "status": "EXACT_MATCH",
                    "matched_name": name,
                    "unit": item_unit,
                    "candidates": [(name, 1.0)]
                }

        # 2. Fuzzy similarity matching fallback
        scored = []
        for item in tally_stock_items:
            name = item["name"]
            score = cls.calculate_similarity(extracted_name, name)
            if score >= threshold_candidate:
                scored.append((name, round(score, 2)))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return {"status": "NO_MATCH", "matched_name": None, "unit": "NOS", "candidates": []}

        best_match, best_score = scored[0]
        best_item_unit = items_by_name.get(best_match, {}).get("unit", "NOS")

        if best_score >= 0.98:
            return {
                "status": "EXACT_MATCH",
                "matched_name": best_match,
                "unit": best_item_unit,
                "candidates": scored[:3]
            }
        elif best_score >= threshold_reliable:
            if len(scored) > 1 and (best_score - scored[1][1] < 0.05):
                return {
                    "status": "MULTIPLE_CANDIDATES",
                    "matched_name": None,
                    "unit": "NOS",
                    "candidates": scored[:3]
                }
            return {
                "status": "RELIABLE_MATCH",
                "matched_name": best_match,
                "unit": best_item_unit,
                "candidates": scored[:3]
            }
        else:
            return {
                "status": "MULTIPLE_CANDIDATES",
                "matched_name": None,
                "unit": "NOS",
                "candidates": scored[:3]
            }

    @classmethod
    def find_best_stock_match(
        cls,
        extracted_name: str,
        tally_stock_items: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Convenience method returning best stock item match dict."""
        res = cls.match_stock_item(extracted_name, tally_stock_items)
        if res.get("matched_name"):
            return {"name": res["matched_name"], "unit": res.get("unit", "NOS")}
        return None

class UnitConverter:
    """
    Standard unit conversion engine for Indian trade & mandi commerce.
    Handles Quintal (QTL) to Kilogram (KG), Ton to KG, Gram to KG, and vice-versa,
    ensuring Quantity and Rate are scaled proportionally while preserving total amount.
    """
    QTL_ALIASES = {"QTL", "QUINTAL", "QUINTALS", "Q", "KTL", "QNT", "QTL."}
    KG_ALIASES = {"KG", "KGS", "KILOGRAM", "KILOGRAMS", "KILO", "KILOS"}
    TON_ALIASES = {"TON", "TONS", "MT", "METRIC TON", "TONNE", "TONNES"}
    GM_ALIASES = {"GM", "GMS", "GRAM", "GRAMS"}

    @classmethod
    def convert(
        cls,
        quantity: float,
        rate: float,
        from_unit: Optional[str],
        to_unit: Optional[str]
    ) -> Tuple[float, float, str, bool, Optional[str]]:
        """
        Converts quantity and rate from bill unit to target Tally stock item unit.
        Returns:
            (converted_quantity, converted_rate, effective_unit, was_converted, explanation)
        """
        if not from_unit or not to_unit:
            return quantity, rate, to_unit or from_unit or "NOS", False, None

        fu = from_unit.strip().upper().replace(".", "")
        tu = to_unit.strip().upper().replace(".", "")

        if fu == tu or (fu in cls.KG_ALIASES and tu in cls.KG_ALIASES) or (fu in cls.QTL_ALIASES and tu in cls.QTL_ALIASES):
            return quantity, rate, tu, False, None

        # 1. QTL to KG: 1 QTL = 100 KG
        if fu in cls.QTL_ALIASES and tu in cls.KG_ALIASES:
            conv_qty = round(quantity * 100.0, 3)
            conv_rate = round(rate / 100.0, 4)
            return conv_qty, conv_rate, "KG", True, f"Converted from {quantity:.2f} {from_unit} @ ₹{rate:.2f}/{from_unit} to {conv_qty:.1f} KG @ ₹{conv_rate:.2f}/KG"

        # 2. KG to QTL: 100 KG = 1 QTL
        if fu in cls.KG_ALIASES and tu in cls.QTL_ALIASES:
            conv_qty = round(quantity / 100.0, 4)
            conv_rate = round(rate * 100.0, 2)
            return conv_qty, conv_rate, "QTL", True, f"Converted from {quantity:.2f} {from_unit} @ ₹{rate:.2f}/{from_unit} to {conv_qty:.2f} QTL @ ₹{conv_rate:.2f}/QTL"

        # 3. TON to KG: 1 TON = 1000 KG
        if fu in cls.TON_ALIASES and tu in cls.KG_ALIASES:
            conv_qty = round(quantity * 1000.0, 3)
            conv_rate = round(rate / 1000.0, 4)
            return conv_qty, conv_rate, "KG", True, f"Converted from {quantity:.2f} {from_unit} @ ₹{rate:.2f}/{from_unit} to {conv_qty:.1f} KG @ ₹{conv_rate:.2f}/KG"

        # 4. TON to QTL: 1 TON = 10 QTL
        if fu in cls.TON_ALIASES and tu in cls.QTL_ALIASES:
            conv_qty = round(quantity * 10.0, 3)
            conv_rate = round(rate / 10.0, 2)
            return conv_qty, conv_rate, "QTL", True, f"Converted from {quantity:.2f} {from_unit} @ ₹{rate:.2f}/{from_unit} to {conv_qty:.2f} QTL @ ₹{conv_rate:.2f}/QTL"

        # 5. GM to KG: 1000 GM = 1 KG
        if fu in cls.GM_ALIASES and tu in cls.KG_ALIASES:
            conv_qty = round(quantity / 1000.0, 4)
            conv_rate = round(rate * 100.0, 2)
            return conv_qty, conv_rate, "KG", True, f"Converted from {quantity:.2f} {from_unit} to {conv_qty:.2f} KG"

        return quantity, rate, to_unit, False, None

master_matcher = MasterMatcher()
unit_converter = UnitConverter()
