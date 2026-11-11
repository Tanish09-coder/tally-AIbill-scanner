# Master Architecture Blueprint & Inspection Report

## 1. Project Inspection Report (Baseline Status)

An initial audit of the workspace was performed:

| Component | Status | Details / Findings |
| :--- | :--- | :--- |
| **Frontend Framework** | `Not Present` | Clean directory. React + TypeScript + Vite + Tailwind CSS scaffold planned. |
| **Backend Framework** | `Initialized` | Python 3.14 + FastAPI + Pydantic Settings initialized. |
| **Database** | `Not Present` | SQLite with SQLAlchemy + aiosqlite configured in architecture; PostgreSQL-ready design. |
| **Bill Scanning / OCR** | `Not Present` | Vision-based multilingual pipeline (Hindi, Marathi, English) planned with Gemini Vision. |
| **AI Integration** | `Configured` | Secure configuration layer in `backend/app/core/config.py` for Google Gemini. |
| **TallyPrime Integration**| `Configured` | XML-over-HTTP client targeting `TALLY_HOST:TALLY_PORT` (default: `http://localhost:9000`). |
| **Voice Functionality** | `Configured` | Architecture ready for Sarvam AI (Hinglish STT/TTS). |
| **Missing Components** | `12 Modules` | Identified across Uploads, Vision OCR, Master Retrieval, Clarification, Voice, Voucher Engine. |

---

## 2. Directory Structure

The structural folders have been established:

```
TALLY/
├── .env.example                     # Root environment template
├── .gitignore                       # Ensures .env, db, & uploads are never committed
├── docs/                            # Architectural specifications & Tally XML schemas
├── backend/
│   ├── .env.example                 # Backend environment variable template
│   ├── .env                         # Local environment configuration (untracked)
│   ├── requirements.txt             # Backend dependencies
│   ├── main.py                      # FastAPI application entrypoint with startup validator
│   ├── verify_apis.py               # Connectivity & credentials diagnostic runner
│   ├── app/
│   │   ├── core/                    # Settings, config, security
│   │   │   ├── config.py            # Pydantic Settings & key validation
│   │   │   └── security.py          # Session and payload validation
│   │   ├── models/                  # SQLAlchemy ORM models (Bills, Items, Mappings, Audit)
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── api/
│   │   │   └── v1/
│   │   │       └── endpoints/       # Endpoints: bills, tally, voice, clarification, vouchers
│   │   ├── services/
│   │   │   ├── ai/                  # Gemini Vision OCR & multilingual handwriting extraction
│   │   │   ├── voice/               # Sarvam AI Hinglish STT/TTS & audio handling
│   │   │   ├── tally/               # Real Tally XML-over-HTTP client & master parser
│   │   │   ├── clarification/       # Question-and-answer context engine
│   │   │   └── accounting/          # Non-GST voucher builder & math validator
│   │   └── utils/                   # Image orientation, cropping, formatting
│   ├── uploads/
│   │   ├── raw/                     # Original uploaded invoice files (.jpg, .png, .pdf)
│   │   └── processed/               # Pre-processed/cropped images for AI vision
│   └── tests/                       # Automated pytest test suites
└── frontend/
    ├── public/
    └── src/
        ├── assets/
        ├── components/
        │   ├── dashboard/           # Analytics, counters, recent activity
        │   ├── upload/              # Mobile camera capture & desktop drag-and-drop
        │   ├── bills/               # Bill list, inspection modal, original image view
        │   ├── clarification/       # Interactive conversational Q&A step
        │   ├── voice/               # Hinglish mic button, wave visualizer, audio player
        │   ├── voucher/             # Non-GST voucher preview & approval controls
        │   ├── tally/               # Live Tally connection status & company selector
        │   └── common/              # Layout, buttons, alerts, navigation
        ├── pages/                   # Full-page routes
        ├── services/                # Axios / fetch API clients to backend
        ├── context/                 # Voice & Tally state providers
        ├── types/                   # TypeScript interfaces
        └── hooks/                   # Custom React hooks (e.g. useVoiceAssistant)
```

---

## 3. Environment & Security Architecture

1. **Security Isolation**: API keys (`GEMINI_API_KEY`, `SARVAM_API_KEY`) reside exclusively on the backend. No secrets are passed to the frontend bundle.
2. **Version Control Safety**: `.gitignore` explicitly ignores `.env`, `*.sqlite3`, `backend/app.db`, and uploaded invoices.
3. **Startup Validation**: If required keys are empty or set to placeholder values, `Settings.validate_api_keys()` flags specific missing keys with clear instructions.
4. **Diagnostic Verification Tool**: `backend/verify_apis.py` tests Gemini API, Sarvam AI, and TallyPrime without exposing raw credentials.

---

## 4. Master 12-Phase Implementation Roadmap

- [x] **Phase 1: Project Inspection & Structural Setup**
  - Created directory structure
  - Built `.env.example`, `.gitignore`, and `config.py`
  - Validated API configuration loader & test runner
- [x] **Phase 2: Database Models & Core Backend API**
  - SQLAlchemy models for Bills, Items, Clarifications, Masters, Vouchers, Audit Logs
  - Initialized SQLite database (`backend/app.db`)
  - REST endpoints for Dashboard, Bills, Clarifications, Vouchers, Tally, and Voice
  - Automated tests passing (7/7 unit & API tests)
- [x] **Phase 3: Responsive Frontend Dashboard & Multi-Device Upload**
  - Scaffolded React 18 + TypeScript + Vite + Tailwind CSS
  - Built desktop drag-and-drop & native mobile camera capture
  - Integrated persistent Hinglish voice assistant bar (Sarvam AI STT & TTS)
  - Built Clarification Modal & Non-GST Voucher Preview with TallyPrime approval gate
  - Production bundle verified with `tsc && vite build`
- [x] **Phase 4: Multilingual AI Bill Recognition Engine**
  - Integrated Gemini Vision service (`gemini-2.5-flash`) for Hindi, Marathi, and English handwriting & printed bills
  - Accounting math validation and automatic Non-GST compliance detection
- [x] **Phase 5: TallyPrime XML-over-HTTP Connector**
  - Real XML-over-HTTP client for Tally (port 9000) for company status, ledgers, stock items, and voucher creation
- [x] **Phase 6 & 7: Clarification System & Party/Item Matching**
  - Dynamic Hinglish questions generated for missing/unclear fields
  - Spoken/typed answer resolution updating line items and bill records
- [x] **Phase 8: Hinglish AI Voice Assistant (Sarvam AI)**
  - Natural Indian Hinglish STT (`saarika:v2`) & TTS (`bulbul:v3`, speaker: `priya`)
- [x] **Phase 9 & 10: Non-GST Voucher Preparation, Preview & Tally Posting**
  - Strict Non-GST rules, Qty × Rate arithmetic validation, user confirmation gate, and real Tally XML posting with response verification
- [ ] **Phase 11: Security, Audit Logging & Offline Resilience**
- [ ] **Phase 12: Comprehensive End-to-End Testing & Live Deployment**

