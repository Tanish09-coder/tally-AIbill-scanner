# 🌾 Tally AI Bill Scanner & Voice Automation

An intelligent, non-GST invoice scanner, handwriting recognition engine, and TallyPrime voucher automation system designed specifically for Indian grain, grocery, and mandi agricultural trade.

---

## 🚀 Key Features

* **Multilingual AI Vision OCR**:
  - Reads computer-printed invoices and messy Hindi / Marathi / English handwritten bills (Devanagari script like `तांदुळ`, `चनादाल`, `रवा`, `मुंगदाल`, `गहू`).
  - Automatically translates and maps regional commodity names to your English Tally master inventory list (`RICE`, `CHANA DALL`, `RAVA`, `MOONG DALL`, `GAHU`).
  - Strips brand names, varieties, and packaging clutter (`RICE SONPARI INDRAYANI - 30 KG` $\rightarrow$ `RICE`) while preserving the raw OCR text for audit.

* **Automatic Mandi Unit Conversion (QTL $\leftrightarrow$ KG)**:
  - Automatically converts wholesale Quintal (`QTL`) quantities and rates to standard retail/stock Kilograms (`KG`) ($\text{Qty} \times 100$, $\text{Rate} \div 100$), preserving the exact financial invoice total.

* **TallyPrime HTTP XML Automation**:
  - Direct integration with TallyPrime running on port `9000`.
  - Automatic double-entry balancing (sum of debits == sum of credits) preventing `<EXCEPTIONS>1</EXCEPTIONS>`.
  - Proper Tally internal sign conventions (Debits negative, Credits positive for purchases).
  - Handles Mandi Hamali expenses, round-offs, and discounts.

* **Smart Party & Ledger Matching**:
  - Token-subset and location-aware fuzzy matching (`HARSH INDUSTRIES` $\rightarrow$ `Harsh Industries , Ghoti` with 95%+ confidence).
  - One-click party suggestion and auto-learning persistent party mappings.

* **Conversational Hinglish Voice Assistant**:
  - Speaks and understands Hindi-English voice clarification for handwritten notes, rate alterations, and missing details.

* **One-Click Cleanup & Management**:
  - Per-bill delete option and 1-click failed bill cleanup.
  - Multi-device local network access (Mobile camera capture & desktop workflow).

---

## 🛠️ Architecture & Tech Stack

* **Backend**: Python 3.11+, FastAPI, SQLAlchemy (Async), Uvicorn, httpx.
* **AI Vision Engine**: Google Gemini Multimodal Vision API (`gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`).
* **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons.
* **Accounting Engine**: Tally XML / TDL Server (`http://localhost:9000`).

---

## ⚡ Quickstart

### 1. Prerequisites
* Python 3.11 or newer
* Node.js 18 or newer
* TallyPrime running with HTTP Server enabled on port 9000

### 2. Configure Environment
Create `backend/.env` (refer to `backend/.env.example`):
```env
GEMINI_API_KEY=your_gemini_api_key_here
TALLY_ENDPOINT=http://localhost:9000
DATABASE_URL=sqlite+aiosqlite:///app.db
UPLOAD_DIR=uploads
```

### 3. Launch System
Simply double-click:
```cmd
start_all.bat
```
Or start manually:
```cmd
# Terminal 1: Backend
start_backend.bat

# Terminal 2: Frontend
start_frontend.bat
```

### 4. Access UI
* **Desktop / Laptop**: `http://localhost:5173`
* **Mobile (Same Wi-Fi)**: `http://<your-local-ip>:5173`
