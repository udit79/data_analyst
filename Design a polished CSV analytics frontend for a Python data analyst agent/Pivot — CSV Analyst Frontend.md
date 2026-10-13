# Pivot — CSV Analyst Frontend

A responsive, dependency-free frontend for a CSV-powered data analyst. It includes a dashboard UI, CSV upload, a staged analysis progress tracker, a Plotly-result display slot, follow-up questions, light/dark themes, and a demo mode when no API is configured.

## Run locally

```bash
python3 -m http.server 4173 --bind 0.0.0.0
```

Open `http://localhost:4173`.

## Connect the Python backend

Set `window.PIVOT_API_BASE` in `config.js` to the backend origin (for example, `http://localhost:8000`). The frontend then sends the CSV to `POST /api/analyses`, polls `GET /api/analyses/{analysis_id}` for status/progress, embeds the returned Plotly dashboard, and sends questions to `POST /api/analyses/{analysis_id}/questions`. The complete request and response contract is in [BACKEND-CONTRACT.md](BACKEND-CONTRACT.md).

The backend should enable CORS for the frontend origin when these services are cross-origin. The HTML dashboard response should be produced by your Python/Plotly service; no Python processing or Plotly chart generation is included here.

## Demo mode

With `window.PIVOT_API_BASE` empty, the UI labels its upload progress as a local demo, parses the CSV in-browser for a preview, and uses illustrative sample analyst answers. It does not pretend to have run a Python/Plotly backend.

CSV parsing in the demo recognizes likely fields from column names such as `revenue`, `sales`, `amount`, `price`, `category`, `quantity`, `units`, and `date`. Theme preference is saved in local storage.
