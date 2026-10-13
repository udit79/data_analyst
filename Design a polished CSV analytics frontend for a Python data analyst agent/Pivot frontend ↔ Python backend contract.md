# Pivot frontend ↔ Python backend contract

The frontend is backend-ready but does not implement Python analytics or Plotly chart generation. Configure the service origin in `config.js` as `window.PIVOT_API_BASE = "http://localhost:8000"` (omit a trailing slash).

## 1. Start an analysis

`POST {base}/api/analyses`

- Content type: `multipart/form-data`
- Form field: `file` (the uploaded CSV)
- Expected response: HTTP `202 Accepted` (or `200` for a fast completed run), JSON:

```json
{
  "analysis_id": "an_123",
  "status": "queued",
  "progress": 5,
  "message": "Upload received"
}
```

## 2. Report processing progress and result

The frontend polls `GET {base}/api/analyses/{analysis_id}` approximately every 1.1 seconds. Return JSON using these fields:

```json
{
  "analysis_id": "an_123",
  "status": "running",
  "progress": 54,
  "message": "Building charts and comparing segments"
}
```

`progress` is a number from 0–100; `message` is the human-readable current step. Progress states are displayed across upload, data profiling, Plotly dashboard building, and insight generation.

Complete with `status: "completed"` (also accepted: `complete` or `succeeded`) and a `result` object:

```json
{
  "analysis_id": "an_123",
  "status": "completed",
  "progress": 100,
  "message": "Dashboard ready",
  "result": {
    "row_count": 2481,
    "metrics": { "revenue": 284590 },
    "dashboard_url": "http://localhost:8000/dashboards/an_123"
  }
}
```

Provide either `result.dashboard_url` (also accepted: `plotly_url`) or `result.plotly_html` (also accepted: `dashboard_html`). The URL is loaded in an iframe. Inline HTML is loaded in a sandboxed iframe with scripts enabled and same-origin access disabled. For an error, return `status: "failed"` and a `message`; non-2xx API responses may return `{ "message": "..." }` or `{ "detail": "..." }`.

Optional `result.metrics.revenue` updates the revenue summary, and `result.row_count` updates the record count. The frontend uses the backend-provided dashboard as the primary visualization and hides its illustrative demo charts after the backend dashboard is ready.

## 3. Answer follow-up questions

`POST {base}/api/analyses/{analysis_id}/questions`

```json
{ "question": "What changed most this quarter?" }
```

Return JSON such as `{ "answer": "..." }`. The frontend shows the answer in the analyst conversation.

## Cross-origin deployment

If the frontend and API use different origins, enable CORS for the exact frontend origin and allow `GET`, `POST`, and the `Content-Type` header. If using `dashboard_url`, configure the dashboard host to allow embedding from the frontend origin.
