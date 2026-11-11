import httpx
import xml.etree.ElementTree as ET

xml1 = """<ENVELOPE>
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
</STATICVARIABLES>
</REQUESTDESC>
</EXPORTDATA>
</BODY>
</ENVELOPE>"""

xml2 = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>AllLedgers</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="AllLedgers">
<TYPE>Ledger</TYPE>
<FETCH>Name, Parent</FETCH>
</COLLECTION>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""

xml3 = """<ENVELOPE>
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

def main():
    with httpx.Client(timeout=15.0) as client:
        for name, payload in [("Companies", xml3), ("List of Accounts", xml1), ("Collection TDL", xml2)]:
            try:
                print(f"--- Sending: {name} ---")
                r = client.post("http://localhost:9000", content=payload.encode("utf-8"))
                print(f"Status: {r.status_code}, Length: {len(r.text)}")
                print("Preview:", r.text[:200].replace("\n", " "))
            except Exception as e:
                print(f"Error for {name}: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()

