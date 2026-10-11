# Centsible 🪙
### Personal AI Financial Advisor on iMessage

**Centsible** is an intelligent, privacy-first personal financial advisor that communicates directly via **iMessage (blue bubbles)**. Powered by **Google Gemini** and the **50/30/20 budgeting rule**, Centsible gives you instant, concise spending feedback, reads receipt photos, finds real-time internet deals on demand, suggests smart alternatives for expensive items, and safeguards your private credentials with on-device redaction.

---

## 🚀 Key Features

* **50/30/20 Budgeting:** Instant, concise spending analysis (50% Needs, 30% Wants, 20% Savings) in 2–4 sentences tailored for iMessage.
* **On-Demand Live Internet Deals:** Connects directly to the internet in real time to find clearance deals, sales, and discounts at retailers (Target, Amazon, Best Buy, etc.) when asked.
* **Smart Cheaper Alternatives:** Proactively recommends high-value, budget-friendly alternatives (certified refurbished, prior-gen models, budget brands) when you consider expensive purchases.
* **Multimodal Receipt & Document Vision:** Send a photo of any receipt or bank statement to get itemized breakdowns and category analysis.
* **Privacy-First & Local Redaction:** Uses Microsoft Presidio and pattern recognition to scrub Social Security Numbers, credit cards, bank accounts, and passwords locally before data reaches the LLM.
* **Security & Chat Deletion Advice:** Assures users that data is encrypted and suggests deleting bank statements from the chat thread for device safety.
* **Persistent Name Memory:** Automatically asks for and remembers user names across conversations using SQLite.
* **Outbound "Text-First" Engine:** Capable of initiating new iMessage conversations with users before they text in.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.12+, FastAPI, Uvicorn
* **AI Model:** Google Gemini (`gemini-flash-lite-latest`, `gemini-3.5-flash`)
* **iMessage Bridge:** TypeScript, Spectrum SDK (`spectrum-ts`), Photon
* **Privacy & Anonymization:** Microsoft Presidio (`presidio-analyzer`, `presidio-anonymizer`)
* **Live Search:** `ddgs` (DuckDuckGo search engine)
* **Database:** SQLite (`memory.db`)

---

## 📋 Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/centsible.git
cd centsible
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your credentials:
```env
GEMINI_API_KEY=your_gemini_api_key_here
PHOTON_PROJECT_ID=your_photon_project_id_here
PHOTON_PROJECT_SECRET=your_photon_project_secret_here
```

### 3. Install Python Dependencies
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

### 4. Install Node Dependencies
```bash
npm install
```

---

## 🏃 Running the Application

Open two terminal windows:

### Terminal 1: Start Photon iMessage Bridge
```bash
npx tsx photon_proxy.ts
```

### Terminal 2: Start FastAPI Python Backend
```bash
# Windows
.\venv\Scripts\python.exe main.py
# Mac/Linux
python main.py
```

---

## 📲 Outbound "Text-First" CLI

To have Centsible initiate an iMessage with a new user:
```bash
python text_first.py +1XXXXXXXXXX "User Name"
```
Or via HTTP:
```text
http://127.0.0.1:8000/text-first?phone=+1XXXXXXXXXX&name=Leo
```

---

## 🔒 Security & Privacy Notice
* Sensitive identifiers (SSNs, cards, credentials) are sanitized locally before processing.
* Never commit `.env` or `memory.db` to version control.
