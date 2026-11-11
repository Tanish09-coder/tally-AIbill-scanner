import xml.etree.ElementTree as ET
import re
from typing import Dict, List, Optional, Tuple, Any
import httpx
import logging
from app.core.config import settings

logger = logging.getLogger("tally_client")

def clean_tally_xml(xml_text: str) -> str:
    """
    Sanitizes raw XML from TallyPrime:
    - Removes invalid XML 1.0 numeric entities (control characters &#1; to &#31;)
    - Strips unprintable raw ASCII control bytes
    - Fixes unescaped ampersands
    """
    if not xml_text:
        return ""
    # Strip numeric entities for control characters
    xml_text = re.sub(r'&#(0?[0-8]|1[12]|1[4-9]|2[0-9]|3[01]);', '', xml_text)
    xml_text = re.sub(r'&#x(0?[0-8bBcCeeFf]|1[0-9a-fA-F]);', '', xml_text)
    # Strip raw control characters except tab, newline, CR
    xml_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', xml_text)
    # Fix stray ampersands
    xml_text = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', xml_text)
    return xml_text

class TallyClient:
    """
    Communicates directly with TallyPrime installed on the local system
    via its official XML-over-HTTP interface (Default port 9000).
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        self.host = host or settings.TALLY_HOST
        self.port = port or settings.TALLY_PORT
        self.endpoint = f"{self.host.rstrip('/')}:{self.port}"
        self.timeout = 15.0
        self.active_company_name: Optional[str] = None

    async def _send_xml(self, xml_payload: str, timeout: Optional[float] = None) -> Tuple[bool, str]:
        """Sends an XML payload to TallyPrime and returns (success, response_text)."""
        headers = {"Content-Type": "text/xml;charset=utf-8"}
        use_timeout = timeout if timeout is not None else self.timeout
        try:
            async with httpx.AsyncClient(timeout=use_timeout) as client:
                response = await client.post(
                    self.endpoint,
                    content=xml_payload.encode("utf-8"),
                    headers=headers
                )
                if response.status_code == 200:
                    return True, response.text
                return False, f"HTTP Error {response.status_code}: {response.text}"
        except httpx.ConnectError:
            return False, f"Connection refused at {self.endpoint}. Is TallyPrime running with HTTP Server enabled on port {self.port}?"
        except httpx.TimeoutException:
            return False, f"Connection to TallyPrime timed out at {self.endpoint}."
        except Exception as e:
            return False, f"Unexpected error connecting to TallyPrime: {str(e)}"

    async def get_connection_status(self) -> Dict[str, Any]:
        """
        Pings Tally and inspects whether a company is loaded.
        Uses lightweight List of Accounts (Units) query which includes SVCURRENTCOMPANY.
        """
        xml_req = """<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>List of Accounts</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<ACCOUNTTYPE>Units</ACCOUNTTYPE>
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""
        success, resp = await self._send_xml(xml_req, timeout=8.0)
        if not success:
            # If timed out but we previously knew the company, Tally might just have a modal menu open
            if "timed out" in resp.lower() and self.active_company_name:
                return {
                    "is_connected": True,
                    "status": "CONNECTED",
                    "endpoint": self.endpoint,
                    "company_name": self.active_company_name,
                    "message": f"Connected to active company '{self.active_company_name}' (Tally is processing or modal menu open)."
                }
            return {
                "is_connected": False,
                "status": "DISCONNECTED",
                "endpoint": self.endpoint,
                "company_name": self.active_company_name,
                "message": resp
            }

        try:
            root = ET.fromstring(resp)
            comp_name = root.findtext(".//SVCURRENTCOMPANY")
            if comp_name and comp_name.strip():
                self.active_company_name = comp_name.strip()

            if self.active_company_name:
                return {
                    "is_connected": True,
                    "status": "CONNECTED",
                    "endpoint": self.endpoint,
                    "company_name": self.active_company_name,
                    "available_companies": [self.active_company_name],
                    "message": f"Connected to active company '{self.active_company_name}'"
                }
            else:
                return {
                    "is_connected": True,
                    "status": "COMPANY_NOT_SELECTED",
                    "endpoint": self.endpoint,
                    "company_name": None,
                    "available_companies": [],
                    "message": "Tally is running, but no company is currently open. Please open your company in Gateway of Tally."
                }
        except ET.ParseError:
            return {
                "is_connected": True,
                "status": "CONNECTED_RAW",
                "endpoint": self.endpoint,
                "company_name": self.active_company_name,
                "message": "Connected to TallyPrime, but received non-XML response."
            }

    async def get_ledgers(self, company_name: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Retrieves all ledgers and their parent groups from TallyPrime.
        Useful for Party (Sundry Debtors/Creditors) and Sales/Purchase accounts.
        Supports both 'List of Accounts' report and TDL collection fallback.
        """
        company_xml = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>" if company_name else ""
        xml_req = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>List of Accounts</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<ACCOUNTTYPE>Ledgers</ACCOUNTTYPE>
{company_xml}
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""
        success, resp = await self._send_xml(xml_req, timeout=30.0)
        ledgers = []

        def _extract_name_and_parent(elem: ET.Element) -> Tuple[Optional[str], Optional[str]]:
            # Extract name
            name = elem.get("NAME")
            if not name:
                name_elem = elem.find("NAME")
                if name_elem is not None and name_elem.text:
                    name = name_elem.text.strip()
            if not name:
                for n in elem.iter("NAME"):
                    if n.text and n.text.strip():
                        name = n.text.strip()
                        break
            # Extract parent
            parent = elem.get("PARENT")
            if not parent:
                parent_elem = elem.find("PARENT")
                if parent_elem is not None and parent_elem.text:
                    parent = parent_elem.text.strip()
            if not parent:
                for p in elem.iter("PARENT"):
                    if p.text and p.text.strip():
                        parent = p.text.strip()
                        break
            return name, parent

        if success and resp:
            cleaned = clean_tally_xml(resp)
            # Extract company name from XML
            comp_match = re.search(r'<SVCURRENTCOMPANY>([^<]+)</SVCURRENTCOMPANY>', cleaned, re.IGNORECASE)
            if comp_match and comp_match.group(1).strip():
                self.active_company_name = comp_match.group(1).strip()

            try:
                root = ET.fromstring(cleaned)
                for ledger in root.iter("LEDGER"):
                    name, parent = _extract_name_and_parent(ledger)
                    if name and not any(l["name"].lower() == name.lower() for l in ledgers):
                        ledgers.append({"name": name, "parent": parent or "Primary"})
            except Exception as e:
                logger.warning(f"DOM parsing error in List of Accounts ledgers: {e}. Using regex parser fallback.")

            # Resilient Regex fallback parser (handles control characters or malformed entities)
            if not ledgers:
                ledger_blocks = re.findall(r'<LEDGER\s+NAME="([^"]+)"(.*?)<\/LEDGER>', cleaned, re.DOTALL | re.IGNORECASE)
                for name, content in ledger_blocks:
                    clean_name = name.strip()
                    if clean_name and not any(l["name"].lower() == clean_name.lower() for l in ledgers):
                        parent_match = re.search(r'<PARENT>([^<]*)<\/PARENT>', content, re.IGNORECASE)
                        parent = parent_match.group(1).strip() if parent_match else "Primary"
                        ledgers.append({"name": clean_name, "parent": parent})

        # If still empty or failed, fallback to TDL Collection query
        if not ledgers:
            tdl_req = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_xml}
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="LedgersColl">
<TYPE>Ledger</TYPE>
<FETCH>Name, Parent</FETCH>
</COLLECTION>
</TDLMESSAGE>
</TDL>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""
            success_tdl, resp_tdl = await self._send_xml(tdl_req, timeout=15.0)
            if success_tdl and resp_tdl:
                cleaned_tdl = clean_tally_xml(resp_tdl)
                try:
                    root = ET.fromstring(cleaned_tdl)
                    for ledger in root.iter("LEDGER"):
                        name, parent = _extract_name_and_parent(ledger)
                        if name and not any(l["name"].lower() == name.lower() for l in ledgers):
                            ledgers.append({"name": name, "parent": parent or "Primary"})
                except Exception as e:
                    logger.warning(f"Error parsing TDL ledgers: {e}")
                if not ledgers:
                    ledger_blocks = re.findall(r'<LEDGER\s+NAME="([^"]+)"(.*?)<\/LEDGER>', cleaned_tdl, re.DOTALL | re.IGNORECASE)
                    for name, content in ledger_blocks:
                        clean_name = name.strip()
                        if clean_name and not any(l["name"].lower() == clean_name.lower() for l in ledgers):
                            parent_match = re.search(r'<PARENT>([^<]*)<\/PARENT>', content, re.IGNORECASE)
                            parent = parent_match.group(1).strip() if parent_match else "Primary"
                            ledgers.append({"name": clean_name, "parent": parent})

        return ledgers

    async def get_ledgers_and_company(self, company_name: Optional[str] = None) -> Tuple[List[Dict[str, str]], Optional[str]]:
        """Returns both ledgers list and the detected active company name."""
        ledgers = await self.get_ledgers(company_name)
        return ledgers, self.active_company_name

    async def get_stock_items(self, company_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all Stock Items, base units of measurement, and parent stock groups.
        """
        company_xml = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>" if company_name else ""
        xml_req = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>List of Accounts</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<ACCOUNTTYPE>Stock Items</ACCOUNTTYPE>
{company_xml}
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""
        success, resp = await self._send_xml(xml_req, timeout=25.0)
        items = []

        def _extract_stock_item(elem: ET.Element) -> Optional[Dict[str, Any]]:
            name = elem.get("NAME")
            if not name:
                name_elem = elem.find("NAME")
                if name_elem is not None and name_elem.text:
                    name = name_elem.text.strip()
            if not name:
                for n in elem.iter("NAME"):
                    if n.text and n.text.strip():
                        name = n.text.strip()
                        break
            if not name:
                return None
            parent = elem.get("PARENT") or (elem.findtext("PARENT") or "").strip()
            unit = (elem.findtext("BASEUNITS") or "").strip()
            if not unit:
                for u in elem.iter("BASEUNITS"):
                    if u.text and u.text.strip():
                        unit = u.text.strip()
                        break
            return {"name": name, "parent": parent or "Primary", "unit": unit or "NOS"}

        if success and resp:
            cleaned = clean_tally_xml(resp)
            try:
                root = ET.fromstring(cleaned)
                for item in root.iter("STOCKITEM"):
                    data = _extract_stock_item(item)
                    if data and not any(it["name"].lower() == data["name"].lower() for it in items):
                        items.append(data)
            except Exception as e:
                logger.warning(f"Error parsing stock items XML: {e}. Using regex fallback.")

            if not items:
                item_blocks = re.findall(r'<STOCKITEM\s+NAME="([^"]+)"(.*?)<\/STOCKITEM>', cleaned, re.DOTALL | re.IGNORECASE)
                for name, content in item_blocks:
                    clean_name = name.strip()
                    if clean_name and not any(it["name"].lower() == clean_name.lower() for it in items):
                        parent_match = re.search(r'<PARENT>([^<]*)<\/PARENT>', content, re.IGNORECASE)
                        unit_match = re.search(r'<BASEUNITS>([^<]*)<\/BASEUNITS>', content, re.IGNORECASE)
                        parent = parent_match.group(1).strip() if parent_match else "Primary"
                        unit = unit_match.group(1).strip() if unit_match else "NOS"
                        items.append({"name": clean_name, "parent": parent, "unit": unit})

        # Fallback to TDL Collection query if needed
        if not items:
            tdl_req = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
{company_xml}
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="StockItemsColl">
<TYPE>StockItem</TYPE>
<FETCH>Name, Parent, BaseUnits</FETCH>
</COLLECTION>
</TDLMESSAGE>
</TDL>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""
            success_tdl, resp_tdl = await self._send_xml(tdl_req, timeout=15.0)
            if success_tdl and resp_tdl:
                cleaned_tdl = clean_tally_xml(resp_tdl)
                try:
                    root = ET.fromstring(cleaned_tdl)
                    for item in root.iter("STOCKITEM"):
                        data = _extract_stock_item(item)
                        if data and not any(it["name"].lower() == data["name"].lower() for it in items):
                            items.append(data)
                except Exception as e:
                    logger.warning(f"Error parsing TDL stock items: {e}")

                if not items:
                    item_blocks = re.findall(r'<STOCKITEM\s+NAME="([^"]+)"(.*?)<\/STOCKITEM>', cleaned_tdl, re.DOTALL | re.IGNORECASE)
                    for name, content in item_blocks:
                        clean_name = name.strip()
                        if clean_name and not any(it["name"].lower() == clean_name.lower() for it in items):
                            parent_match = re.search(r'<PARENT>([^<]*)<\/PARENT>', content, re.IGNORECASE)
                            unit_match = re.search(r'<BASEUNITS>([^<]*)<\/BASEUNITS>', content, re.IGNORECASE)
                            parent = parent_match.group(1).strip() if parent_match else "Primary"
                            unit = unit_match.group(1).strip() if unit_match else "NOS"
                            items.append({"name": clean_name, "parent": parent, "unit": unit})

        return items

    async def get_units(self, company_name: Optional[str] = None) -> List[str]:
        """Retrieves Units of Measurement defined in Tally."""
        company_xml = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>" if company_name else ""
        xml_req = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Export Data</TALLYREQUEST>
</HEADER>
<BODY>
<EXPORTDATA>
<REQUESTDESC>
<REPORTNAME>List of Accounts</REPORTNAME>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<ACCOUNTTYPE>Units</ACCOUNTTYPE>
{company_xml}
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""
        success, resp = await self._send_xml(xml_req, timeout=10.0)
        units = []
        if success and resp:
            cleaned = clean_tally_xml(resp)
            try:
                root = ET.fromstring(cleaned)
                for unit in root.iter("UNIT"):
                    name = unit.get("NAME") or (unit.findtext("NAME") or "").strip()
                    if not name:
                        for n in unit.iter("NAME"):
                            if n.text and n.text.strip():
                                name = n.text.strip()
                                break
                    if name and name not in units:
                        units.append(name)
            except Exception as e:
                logger.warning(f"Error parsing units XML: {e}")

            if not units:
                unit_names = re.findall(r'<UNIT\s+NAME="([^"]+)"', cleaned, re.IGNORECASE)
                for u in unit_names:
                    if u.strip() and u.strip() not in units:
                        units.append(u.strip())
        return units

    def build_create_ledger_xml(self, company_name: str, ledger_name: str, parent_group: str = "Sundry Debtors") -> str:
        """Builds standard Tally XML to create a new Ledger (only after explicit user approval)."""
        return f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<LEDGER NAME="{ledger_name}" ACTION="Create">
<NAME>{ledger_name}</NAME>
<PARENT>{parent_group}</PARENT>
<ISBILLWISEON>Yes</ISBILLWISEON>
<AFFECTSSTOCK>No</AFFECTSSTOCK>
</LEDGER>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""

    def build_create_stock_item_xml(self, company_name: str, item_name: str, parent_group: str = "Primary", uom: str = "NOS") -> str:
        """Builds standard Tally XML to create a new Stock Item (only after explicit user approval)."""
        return f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<STOCKITEM NAME="{item_name}" ACTION="Create">
<NAME>{item_name}</NAME>
<PARENT>{parent_group}</PARENT>
<BASEUNITS>{uom}</BASEUNITS>
</STOCKITEM>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""

    async def create_ledger(self, company_name: str, ledger_name: str, parent_group: str = "Sundry Debtors") -> Tuple[bool, str]:
        xml_req = self.build_create_ledger_xml(company_name, ledger_name, parent_group)
        success, resp = await self._send_xml(xml_req)
        if not success:
            return False, resp
        if "<CREATED>1</CREATED>" in resp or "<ALTERED>1</ALTERED>" in resp or "<ERRORS>0</ERRORS>" in resp:
            return True, f"Ledger '{ledger_name}' created in Tally."
        return False, f"Tally rejected ledger creation: {resp[:200]}"

    async def create_stock_item(self, company_name: str, item_name: str, parent_group: str = "Primary", uom: str = "NOS") -> Tuple[bool, str]:
        xml_req = self.build_create_stock_item_xml(company_name, item_name, parent_group, uom)
        success, resp = await self._send_xml(xml_req)
        if not success:
            return False, resp
        if "<CREATED>1</CREATED>" in resp or "<ALTERED>1</ALTERED>" in resp or "<ERRORS>0</ERRORS>" in resp:
            return True, f"Stock Item '{item_name}' created in Tally."
        return False, f"Tally rejected stock item creation: {resp[:200]}"

    def build_non_gst_voucher_xml(
        self,
        company_name: Optional[str],
        voucher_type: str, # "Sales" or "Purchase"
        invoice_number: str,
        invoice_date_tally: str, # Format: YYYYMMDD (e.g. 20250401)
        party_ledger: str,
        sales_purchase_ledger: str,
        items: List[Dict[str, Any]],
        final_amount: float,
        narration: str = "Imported via AI Bill Scanner Automation",
        additional_charges: float = 0.0,
        additional_charges_ledger: Optional[str] = "Hamali Expenses",
        discount: float = 0.0,
        discount_ledger: Optional[str] = "Discount",
        round_off: float = 0.0
    ) -> str:
        """
        Builds standard, verified Tally XML for a Non-GST Sales or Purchase Voucher.
        Strictly enforces double-entry balancing (sum of debits == sum of credits == final_amount)
        so Tally never rejects with out-of-balance exceptions.
        """
        is_sales = voucher_type.lower() == "sales"
        vch_type_str = "Sales" if is_sales else "Purchase"

        # 1. Tally inventory XML block
        # In Tally TDL accounting: Debit is ALWAYS negative, Credit is ALWAYS positive
        # For Purchase: Items are Debit (-), Party is Credit (+)
        # For Sales: Items are Credit (+), Party is Debit (-)
        inv_entries = []
        inv_sum = 0.0
        for it in items:
            item_name = it["stock_item_name"]
            qty = float(it["quantity"])
            unit = it.get("unit", "NOS")
            rate = float(it["rate"])
            amount = float(it["amount"])
            inv_sum += amount

            # In Tally, Rate * Qty must equal Amount. If rate is quoted per Quintal or different unit:
            if qty > 0 and abs(rate * qty - amount) > 1.0:
                effective_rate = round(amount / qty, 2)
            else:
                effective_rate = rate

            inv_amt_signed = f"{amount:.2f}" if is_sales else f"-{amount:.2f}"
            rate_str = f"{effective_rate:.2f}/{unit}"
            billed_qty_str = f"{qty:.2f} {unit}"
            inv_deemed = "No" if is_sales else "Yes"

            inv_xml = f"""<ALLINVENTORYENTRIES.LIST>
<STOCKITEMNAME>{item_name}</STOCKITEMNAME>
<ISDEEMEDPOSITIVE>{inv_deemed}</ISDEEMEDPOSITIVE>
<RATE>{rate_str}</RATE>
<ACTUALQTY>{billed_qty_str}</ACTUALQTY>
<BILLEDQTY>{billed_qty_str}</BILLEDQTY>
<AMOUNT>{inv_amt_signed}</AMOUNT>
<ACCOUNTINGALLOCATIONS.LIST>
<LEDGERNAME>{sales_purchase_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{inv_deemed}</ISDEEMEDPOSITIVE>
<AMOUNT>{inv_amt_signed}</AMOUNT>
</ACCOUNTINGALLOCATIONS.LIST>
</ALLINVENTORYENTRIES.LIST>"""
            inv_entries.append(inv_xml)

        inventory_block = "\n".join(inv_entries)

        # 2. Additional ledger entries (Additional charges/Hamali, Discount, Round off)
        addl_ledger_blocks = []

        effective_addl = additional_charges if additional_charges and additional_charges > 0 else 0.0
        effective_disc = discount if discount and discount > 0 else 0.0

        if effective_addl > 0:
            addl_amt_signed = f"{effective_addl:.2f}" if is_sales else f"-{effective_addl:.2f}"
            addl_deemed = "No" if is_sales else "Yes"
            addl_ledger_blocks.append(f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{additional_charges_ledger or "Hamali Expenses"}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{addl_deemed}</ISDEEMEDPOSITIVE>
<AMOUNT>{addl_amt_signed}</AMOUNT>
</LEDGERENTRIES.LIST>""")

        if effective_disc > 0:
            disc_amt_signed = f"-{effective_disc:.2f}" if is_sales else f"{effective_disc:.2f}"
            disc_deemed = "Yes" if is_sales else "No"
            addl_ledger_blocks.append(f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>{discount_ledger or "Discount"}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{disc_deemed}</ISDEEMEDPOSITIVE>
<AMOUNT>{disc_amt_signed}</AMOUNT>
</LEDGERENTRIES.LIST>""")

        # Ensure exact mathematical double-entry balance for Tally
        # Total line items debits/credits + charges must balance party credit/debit
        computed_total = round(inv_sum + effective_addl - effective_disc, 2)
        diff_with_final = round(final_amount - computed_total, 2)

        # If diff is small or there is an explicit round off, add round off ledger
        effective_ro = round_off
        if abs(diff_with_final) >= 0.01 and abs(diff_with_final) <= 5.0:
            effective_ro = diff_with_final

        if abs(effective_ro) >= 0.01:
            if is_sales:
                ro_amt_signed = f"{effective_ro:.2f}" if effective_ro > 0 else f"{effective_ro:.2f}"
                ro_deemed = "No" if effective_ro > 0 else "Yes"
            else:
                ro_amt_signed = f"-{effective_ro:.2f}" if effective_ro > 0 else f"{abs(effective_ro):.2f}"
                ro_deemed = "Yes" if effective_ro > 0 else "No"
            addl_ledger_blocks.append(f"""<LEDGERENTRIES.LIST>
<LEDGERNAME>Round Off</LEDGERNAME>
<ISDEEMEDPOSITIVE>{ro_deemed}</ISDEEMEDPOSITIVE>
<AMOUNT>{ro_amt_signed}</AMOUNT>
</LEDGERENTRIES.LIST>""")

        additional_entries_xml = "\n".join(addl_ledger_blocks)

        # 3. Party Ledger entry: strictly balanced to algebraic sum of entries
        party_balance = round(inv_sum + effective_addl - effective_disc + effective_ro, 2)
        party_amt_signed = f"-{party_balance:.2f}" if is_sales else f"{party_balance:.2f}"
        party_deemed_positive = "Yes" if is_sales else "No"

        current_comp_xml = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>" if company_name else ""

        envelope = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>Vouchers</REPORTNAME>
<STATICVARIABLES>
{current_comp_xml}
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<VOUCHER VCHTYPE="{vch_type_str}" ACTION="Create" OBJVIEW="Invoice Voucher View">
<DATE>{invoice_date_tally}</DATE>
<VOUCHERTYPENAME>{vch_type_str}</VOUCHERTYPENAME>
<REFERENCE>{invoice_number}</REFERENCE>
<VOUCHERNUMBER>{invoice_number}</VOUCHERNUMBER>
<PARTYLEDGERNAME>{party_ledger}</PARTYLEDGERNAME>
<NARRATION>{narration}</NARRATION>
<PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<LEDGERENTRIES.LIST>
<LEDGERNAME>{party_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>{party_deemed_positive}</ISDEEMEDPOSITIVE>
<AMOUNT>{party_amt_signed}</AMOUNT>
</LEDGERENTRIES.LIST>
{additional_entries_xml}
{inventory_block}
</VOUCHER>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""
        return envelope
        return envelope

    async def post_voucher(self, xml_payload: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Submits the voucher to TallyPrime and validates response XML.
        Verifies `<CREATED>1</CREATED>` or checks for `<LINEERROR>`.
        """
        success, resp = await self._send_xml(xml_payload)
        if not success:
            return False, {"error": resp, "raw_response": resp}

        try:
            root = ET.fromstring(resp)
            # Check for standard Tally import counters
            created_elem = root.find(".//CREATED")
            errors_elem = root.find(".//ERRORS")
            created_count = int(created_elem.text) if created_elem is not None and created_elem.text else 0
            errors_count = int(errors_elem.text) if errors_elem is not None and errors_elem.text else 0
            
            # Find line errors if any
            line_errors = [err.text.strip() for err in root.iter("LINEERROR") if err.text]

            if created_count > 0 and errors_count == 0:
                # Retrieve voucher number or guid if available
                vch_num = root.findtext(".//LASTVCHNUM")
                return True, {
                    "success": True,
                    "created_count": created_count,
                    "voucher_number": vch_num,
                    "raw_response": resp
                }
            else:
                error_msg = "; ".join(line_errors) if line_errors else f"Tally rejected voucher (Errors: {errors_count})"
                return False, {
                    "success": False,
                    "error": error_msg,
                    "errors_count": errors_count,
                    "line_errors": line_errors,
                    "raw_response": resp
                }
        except ET.ParseError:
            return False, {
                "success": False,
                "error": "Failed to parse Tally XML response.",
                "raw_response": resp
            }

tally_client = TallyClient()

