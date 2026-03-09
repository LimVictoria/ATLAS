# ATLAS — Advanced Transport & Logistics Analytics System

> AI-powered EDA and BI platform for logistics data

## Stack

| Layer | Technology |
|---|---|
| Frontend | React + Plotly.js |
| Backend | FastAPI + Python |
| Agent | LangGraph |
| LLM | Groq · Llama 3.1 70B (free) |
| Query engine | DuckDB (in-process) |
| Database | Supabase (PostgreSQL) |
| Observability | LangSmith |
| Frontend deploy | Vercel |
| Backend deploy | Render |

---

## Project Structure

```
atlas/
├── backend/
│   ├── main.py              ← FastAPI entry point
│   ├── agent/
│   │   ├── eda_graph.py     ← LangGraph EDA agent graph
│   │   ├── nodes.py         ← LangGraph node functions
│   │   └── tools.py         ← DuckDB + Pandas + Plotly tools
│   ├── api/
│   │   ├── upload.py        ← File upload endpoints
│   │   └── chat.py          ← Chat + chart endpoints
│   ├── db/
│   │   ├── supabase.py      ← Supabase client
│   │   └── duckdb_session.py← Per-session DuckDB instances
│   ├── requirements.txt
│   └── render.yaml          ← Render deploy config
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.jsx
│   │   │   ├── SchemaCards.jsx
│   │   │   ├── ChatPanel.jsx
│   │   │   └── ChartPanel.jsx
│   │   ├── pages/
│   │   │   └── EDA.jsx
│   │   ├── utils/
│   │   │   └── api.js
│   │   ├── App.jsx
│   │   ├── index.js
│   │   └── styles.css
│   ├── public/index.html
│   ├── package.json
│   └── vercel.json
└── .github/workflows/ci.yml
```

---

## Local Development

### 1. Clone repo

```bash
git clone https://github.com/YOUR_USERNAME/atlas.git
cd atlas
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in your API keys in .env
```

Start backend:
```bash
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 3. Frontend setup

```bash
cd frontend
npm install

cp .env.example .env
# Set REACT_APP_API_URL=http://localhost:8000
```

Start frontend:
```bash
npm start
```

App available at: http://localhost:3000

---

## API Keys Required

| Service | Where to get | Cost |
|---|---|---|
| Groq | console.groq.com | Free |
| LangSmith | smith.langchain.com | Free tier |
| Supabase | supabase.com | Free tier |

---

## Deployment

### Frontend → Vercel

1. Go to vercel.com → New Project → Import from GitHub
2. Select the `atlas` repo
3. Set **Root Directory** to `frontend`
4. Add environment variable: `REACT_APP_API_URL` = your Render backend URL
5. Deploy

### Backend → Render

1. Go to render.com → New Web Service → Connect GitHub
2. Select the `atlas` repo
3. Set **Root Directory** to `backend`
4. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add all environment variables from `.env.example`
6. Deploy

Every `git push` to `main` triggers automatic redeployment on both platforms.

---

## EDA Agent Capabilities

| Prompt | What the agent does |
|---|---|
| Profile all tables | Schema + nulls + duplicates + outliers for every table |
| Find anomalies | Statistical outlier detection (3σ), impossible values, date gaps |
| Detect relationships | Foreign key discovery across tables, orphaned record count |
| Suggest metrics | Analyses schema and suggests BI KPIs with ready SQL |
| Compare tables | Row counts, column diff, value range comparison for reconciliation |
| Any chart request | Generates interactive Plotly chart via LLM-written Python |
| Any SQL question | LLM writes DuckDB SQL, self-corrects up to 3 times on error |

---

## EDA Agent Architecture (LangGraph)

```
User Prompt
     ↓
Schema Loader (reads all uploaded tables)
     ↓
Intent Planner (LLM decides what analysis to run)
     ↓
┌────────────────────────────────────────────┐
│  Routes to one of:                         │
│  profile / anomaly / relationship /        │
│  chart / sql / compare / suggest_metrics   │
└────────────────────────────────────────────┘
     ↓
Synthesiser (LLM combines all findings)
     ↓
Output: narrative + charts + data table + SQL
```

SQL node includes self-correction loop — retries up to 3x on failure.

---

## Supported File Formats

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)
- Parquet (`.parquet`)
- JSON (`.json`)

Single file or multiple files supported. Relationships auto-detected across files.
