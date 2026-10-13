# Pivot — Data Agent

Pivot analyzes approved CSV data: a Groq-backed agent plans exploratory analysis and justified transformations, while a local isolated renderer creates a dashboard and downloadable artifacts.

## Demo

[Demo recording](<Recording 2026-10-13 200235.mp4>)

No live demo URL or slide link was supplied in the task context.

## Problem and solution

The contest name, problem ID, and official problem statement were not provided. This project addresses a practical task for analysts: understanding a CSV’s quality and structure before relying on it for further analysis.

Pivot profiles columns, missing values, duplicates, and numeric distributions; asks an agent to propose allowed transformations and useful charts; then saves a dashboard, report, transformed CSV, profile, and transformation log. It does not train a model.

## Key features

- Local browser interface for CSV uploads up to 25 MB.
- Blocks private and unknown data classifications before analysis; accepts sample or explicitly public CSVs.
- Gives the model an aggregate profile and a reproducible preview of up to 10 rows. Full CSV data is passed in run context for the analysis tool.
- Applies a validated plan for missing values, selected type conversions, IQR outlier capping, and exact duplicate removal. The original data is preserved.
- Builds a standalone interactive Plotly dashboard with full-dataset metrics, column profiles, and up to four requested charts. Compatible charts support cross-filtering.
- Saves SVG chart downloads, an analysis report, profile, transformed CSV, and transformation log locally.
- Runs chart rendering in a local Docker container with networking disabled and a read-only root filesystem; its temporary workspace and `/tmp` are writable.
- Includes a separate Managed Deep Agent CLI path for the bundled CSV, PostgreSQL query results, and API JSON data. Database and API credentials stay on the host; uploads to the hosted path require a sample or public classification.

## Architecture

```mermaid
flowchart LR
    Browser[Analyst browser] --> Frontend[Pivot static frontend<br/>port 4173]
    Frontend --> API[FastAPI service<br/>port 8000]
    API --> Guard{Sample or public?}
    Guard -->|yes| Context[Run context holds CSV]
    Guard -->|yes| Prompt[Aggregate profile and up to 10 sample rows]
    Guard -->|no| Reject[Reject before analysis]
    Context --> Tool[Validated apply_dataset_plan tool]
    Prompt --> Agent[LangChain agent with TodoListMiddleware]
    Agent -->|Groq API from host| Model[Groq model]
    Model --> Agent
    Agent -->|Plan tool call| Tool
    Tool --> Renderer[Docker EDA renderer<br/>network disabled]
    Renderer --> Files[Dashboard, report, profile,<br/>transformed CSV, log, SVGs]
    Files --> API
    API --> Frontend
    Agent -. optional tracing .-> LangSmith[LangSmith project]
    CLI[main.py CLI] --> Sources[Host-side CSV, database,<br/>or API ingestion]
    Sources --> HostedGuard{Sample or public?}
    HostedGuard -->|yes| Managed[LangSmith Managed Deep Agent]
    Managed --> ManagedSandbox[Managed sandbox]
    ManagedSandbox --> CLI
```

For the web flow, the API checks the data classification before starting an analysis. It computes an aggregate profile and reproducible preview for the model prompt, while the full CSV is kept in run context for the analysis tool. The agent proposes one validated plan; host-side code applies the allowed transformations to a copy and sends the data and chart requests to the local Docker renderer. The API saves and serves the dashboard and other generated files. A separate CLI uses host-side ingestion and the LangSmith Managed Deep Agent runtime.

## Tech stack

| Technology | Role |
| --- | --- |
| Python 3.11–3.12 | API, agent tools, ingestion, and renderer |
| FastAPI and Uvicorn | Local upload, analysis status, questions, and artifact endpoints |
| LangChain Agents and TodoListMiddleware | Local agent orchestration and task tracking |
| Groq via LangChain Groq | Model calls from the host process |
| LangSmith Managed Deep Agents and LangGraph SDK | Separate hosted CLI execution path |
| Pandas and Pydantic | Data profiling, transformation, and plan validation |
| Plotly and Kaleido | Interactive dashboard and SVG rendering |
| Docker and Chromium | Isolated local chart rendering |
| HTML, CSS, and JavaScript | Pivot browser interface |

## Quick Start

### Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop running
- A Groq API key for analysis
- LangSmith credentials only if using tracing or the separate hosted CLI

Run these five commands from the repository root. Run commands 4 and 5 in separate PowerShell terminals.

```powershell
uv sync
```

```powershell
Copy-Item .env.example .env
```

Add your Groq key to `.env` as `GROQ_API_KEY`, then build the renderer image:

```powershell
docker build -f sandbox/Dockerfile -t data-agent-eda:checkpoint .
```

```powershell
uv run uvicorn scripts.web_app:app --host 127.0.0.1 --port 8000
```

```powershell
python -m http.server 4173 --bind 127.0.0.1 --directory "Design a polished CSV analytics frontend for a Python data analyst agent"
```

Confirm the API reports `"agent_configured": true` at [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health), then open [http://127.0.0.1:4173](http://127.0.0.1:4173).

### Environment variables

Examples below are placeholders, not credentials. The local web app needs `GROQ_API_KEY`; other web variables are optional unless you enable tracing. Managed CLI variables apply only to that separate path.

| Variable | Purpose | Example |
| --- | --- | --- |
| `GROQ_API_KEY` | Required API key for local analysis | `your-groq-api-key` |
| `GROQ_MODEL` | Local model override; default is `openai/gpt-oss-120b` | `openai/gpt-oss-120b` |
| `SANDBOX_DOCKER_IMAGE` | Local renderer image override; default is `data-agent-eda:checkpoint` | `data-agent-eda:checkpoint` |
| `LANGSMITH_TRACING` | Enables optional local trace export | `true` |
| `LANGSMITH_ENDPOINT` | LangSmith API endpoint | `https://api.smith.langchain.com` |
| `LANGSMITH_API_KEY` | LangSmith tracing key; also used by the hosted CLI | `your-langsmith-api-key` |
| `LANGSMITH_PROJECT` | Local trace project; defaults to `Pivot` | `Pivot` |
| `MANAGED_DEEP_AGENT_ID` | Deployed Managed Deep Agent ID for the hosted CLI | `your-agent-id` |
| `LANGSMITH_MANAGED_AGENTS_URL` | Optional hosted-agent API base URL | `https://api.smith.langchain.com/v1/deepagents` |
| `DATABASE_URL` | Optional SQLAlchemy database URL for the CLI | `postgresql+psycopg2://postgres:your-password@localhost:5432/data_cleaning` |
| `DB_Password` | Host-side PostgreSQL password when `DATABASE_URL` is unset | `your-local-password` |
| `API_HEADERS` | JSON object of host-side API request headers | `{}` |

Do not commit real keys or passwords. PostgreSQL defaults for host, port, database, and user are set in `scripts/db_cn.py`.

## Usage

### Browser walkthrough (2–4 minutes)

1. Open the local app and choose **Try the included sample**, or upload a CSV after selecting **Sample or synthetic data** or **Explicitly public data**.
2. Review the dataset metrics, column profile, findings, and interactive charts in the dashboard.
3. Click a chart category or point to cross-filter compatible charts; clear the selection to reset the view. The dashboard summarizes the full dataset and does not show a raw-record table.
4. Download the report, dashboard, profile, transformed CSV, transformation log, and available SVG charts. Use **Ask your data** for a follow-up question about the analysis.

### Hosted CLI walkthrough

The root `main.py` invokes the Managed Deep Agent CLI. It requires a deployed `MANAGED_DEEP_AGENT_ID` and `LANGSMITH_API_KEY`. Its default source is the bundled CSV:

```powershell
uv run python main.py --source sample-csv --output-dir artifacts
```

The CLI also accepts `--source database --query "..."` or `--source api --api-url ...`. Database and API data default to private and are blocked until the caller explicitly classifies permitted data as `sample` or `public`. API query parameters use `--api-params`; host-side headers are read from the JSON environment variable named by `--api-headers-env` (default `API_HEADERS`). The database URL can be supplied with `--database-url-env` (default `DATABASE_URL`), or the project uses the local settings in `scripts/db_cn.py`.

## Project structure

```text
.
├── README.md                       Project guide
├── main.py                         Managed-agent CLI entry point
├── agent.py                        Managed Deep Agent declaration
├── instructions.md                 Agent analysis instructions
├── pyproject.toml                  Package metadata and Python dependencies
├── requirements.txt                Runtime dependency list
├── uv.lock                         Locked uv dependency versions
├── scripts/
│   ├── web_app.py                  Local FastAPI application
│   ├── local_agent.py              Local Groq-backed agent
│   ├── analysis_plan.py            Validated transformations and chart plan
│   ├── data_tools.py               Profiling and plan execution tools
│   ├── data_policy.py              Sample/public/private classification guard
│   ├── data_ingestion.py           CSV, database, and API readers
│   ├── data_cleaning.py            DataFrame cleaning strategies
│   ├── docker_sandbox.py           Restricted local renderer backend
│   ├── eda_renderer.py             Dashboard, report, and SVG generation
│   ├── artifacts.py                Managed sandbox artifact download tool
│   └── main.py                     CLI ingestion and hosted-agent workflow
├── sandbox/
│   ├── Dockerfile                  Local renderer image
│   ├── requirements.txt            Renderer dependencies
│   ├── setup.sh                    Managed sandbox setup script
│   └── __init__.py                 Managed sandbox declaration
├── Design a polished CSV analytics frontend for a Python data analyst agent/
│   ├── index.html                  Pivot application page
│   ├── app.js and workflow.js      Browser interactions and API workflow
│   ├── styles.css                  Interface styles
│   └── config.js                   Local API address
├── data/
│   ├── sample_data.csv             Bundled CSV demo input
│   └── synthetic_eda_test.csv      Synthetic EDA test input
└── artifacts/                      Local analysis outputs and logs
```

## Status and limitations

- The local web app supports CSV uploads only. Its API limits uploads to 25 MB.
- The CLI includes sample CSV, database, and API ingestion paths; database and API paths require their source credentials and an available Managed Deep Agent deployment.
- Only sample or explicitly public data may be sent for hosted analysis. Private and unknown classifications are rejected.
- The agent proposes and applies EDA transformations; model training and train/test splitting are not implemented.
- Local analysis sessions are held in memory. Restarting the API clears follow-up sessions and the active analysis list.
- Dashboard chart requests are capped at four; excess requests are recorded as omitted by the plan executor.
- Test files exist in the working directory but `tests/` is excluded by `.gitignore`, so those files are not included in a Git checkout.

## Team, license, and acknowledgements

No team members, license, or formal acknowledgements are specified in the repository. No license file is present.
