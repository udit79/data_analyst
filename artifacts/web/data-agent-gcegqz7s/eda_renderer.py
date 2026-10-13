"""Render the sandbox EDA dashboard and downloadable chart artifacts."""

from __future__ import annotations

import csv
import html
import json
import math
from collections import defaultdict
from pathlib import Path, PurePosixPath
from statistics import mean, stdev
from typing import Any, cast

ROOT = PurePosixPath("/workspace")
ARTIFACTS = ROOT / "artifacts"
DATA_PATH = ARTIFACTS / "cleaned_data.csv"
PROFILE_PATH = ARTIFACTS / "analysis_profile.json"
LOG_PATH = ARTIFACTS / "transformation_log.json"
REQUESTS_PATH = ARTIFACTS / "chart_requests.json"
MANIFEST_PATH = ARTIFACTS / "chart_manifest.json"
REPORT_PATH = ARTIFACTS / "analysis_report.md"
DASHBOARD_PATH = ARTIFACTS / "analysis_dashboard.html"


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _number(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _finite_pairs(
    rows: list[dict[str, str]], x_column: str, y_column: str | None = None
) -> list[tuple[int, float, float | None]]:
    pairs = []
    for index, row in enumerate(rows):
        x_value = _number(row.get(x_column))
        y_value = _number(row.get(y_column)) if y_column is not None else None
        if x_value is not None and (y_column is None or y_value is not None):
            pairs.append((index, x_value, y_value))
    return pairs


def _correlation(columns: list[str], rows: list[dict[str, str]]) -> list[list[float | None]]:
    matrix = []
    for first in columns:
        line = []
        for second in columns:
            pairs = _finite_pairs(rows, first, second)
            if len(pairs) < 2:
                line.append(None)
                continue
            x_values = [pair[1] for pair in pairs]
            y_values = [cast(float, pair[2]) for pair in pairs]
            x_sd, y_sd = stdev(x_values), stdev(y_values)
            if x_sd == 0 or y_sd == 0:
                line.append(None)
                continue
            covariance = sum(
                (x - mean(x_values)) * (y - mean(y_values))
                for x, y in zip(x_values, y_values, strict=True)
            ) / (len(pairs) - 1)
            line.append(covariance / (x_sd * y_sd))
        matrix.append(line)
    return matrix


def _figure(request: dict[str, Any], rows: list[dict[str, str]], title: str):
    import plotly.graph_objects as go

    chart_type = request["chart_type"]
    columns = request["columns"]
    figure = go.Figure()
    if chart_type == "histogram":
        column = columns[0]
        pairs = _finite_pairs(rows, column)
        if not pairs:
            raise ValueError(f"'{column}' has no usable numeric values")
        values = [pair[1] for pair in pairs]
        minimum, maximum = min(values), max(values)
        bins = min(20, max(1, int(math.sqrt(len(values)))))
        width = (maximum - minimum) / bins if maximum > minimum else 1.0
        row_groups: list[list[int]] = [[] for _ in range(bins)]
        for index, value, _ in pairs:
            bin_index = min(bins - 1, int((value - minimum) / width)) if maximum > minimum else 0
            row_groups[bin_index].append(index)
        centers = [minimum + (index + 0.5) * width for index in range(bins)]
        figure.add_bar(
            x=centers,
            y=[len(group) for group in row_groups],
            customdata=row_groups,
            marker_color="#3977b8",
            hovertemplate=f"{column}: %{{x:.4g}}<br>Rows: %{{y}}<extra></extra>",
        )
        figure.update_layout(xaxis_title=column, yaxis_title="Row count")
    elif chart_type == "box":
        column = columns[0]
        pairs = _finite_pairs(rows, column)
        if not pairs:
            raise ValueError(f"'{column}' has no usable numeric values")
        figure.add_box(
            y=[pair[1] for pair in pairs],
            x=[column] * len(pairs),
            customdata=[pair[0] for pair in pairs],
            boxpoints="all",
            jitter=0.35,
            pointpos=-1.5,
            marker_color="#3977b8",
            hovertemplate=f"{column}: %{{y:.4g}}<extra></extra>",
        )
        figure.update_layout(xaxis_title="", yaxis_title=column)
    elif chart_type == "scatter":
        x_column, y_column = columns
        pairs = _finite_pairs(rows, x_column, y_column)
        if not pairs:
            raise ValueError("No rows contain numeric values for both scatter columns")
        figure.add_scatter(
            x=[pair[1] for pair in pairs],
            y=[pair[2] for pair in pairs],
            customdata=[pair[0] for pair in pairs],
            mode="markers",
            marker={"color": "#3977b8", "opacity": 0.75},
            hovertemplate=f"{x_column}: %{{x:.4g}}<br>{y_column}: %{{y:.4g}}<extra></extra>",
        )
        figure.update_layout(xaxis_title=x_column, yaxis_title=y_column)
    elif chart_type == "bar":
        column = columns[0]
        grouped: dict[str, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            grouped[row.get(column) or "(missing)"].append(index)
        items = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))[:15]
        if not items:
            raise ValueError(f"'{column}' has no values to chart")
        figure.add_bar(
            x=[len(indices) for _, indices in items],
            y=[label for label, _ in items],
            customdata=[indices for _, indices in items],
            orientation="h",
            marker_color="#3977b8",
            hovertemplate=f"{column}: %{{y}}<br>Rows: %{{x}}<extra></extra>",
        )
        figure.update_layout(xaxis_title="Row count", yaxis_title=column, yaxis={"autorange": "reversed"})
    elif chart_type == "correlation":
        if len(columns) > 10:
            raise ValueError("Correlation charts are limited to 10 columns")
        values = _correlation(columns, rows)
        if not any(value is not None for line in values for value in line):
            raise ValueError("Correlation chart has no usable numeric pairs")
        figure.add_heatmap(
            z=values,
            x=columns,
            y=columns,
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            text=[["n/a" if value is None else f"{value:.2f}" for value in line] for line in values],
            texttemplate="%{text}",
            hovertemplate="%{y} × %{x}: %{z:.3f}<extra></extra>",
        )
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")

    figure.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        colorway=["#3977b8", "#e07b39", "#4a9c75", "#c95454", "#8c6bb1"],
        font={"family": "Arial, sans-serif", "size": 12},
        margin={"l": 55, "r": 25, "t": 65, "b": 55},
        clickmode="event+select",
    )
    figure.update_xaxes(automargin=True, showgrid=False)
    figure.update_yaxes(automargin=True, gridcolor="#e8edf2")
    return figure


def render_chart(request: dict[str, Any], rows: list[dict[str, str]], title: str) -> bytes:
    """Export one validated chart as a static SVG using Kaleido."""
    return _figure(request, rows, title).to_image(format="svg", width=1000, height=620)


def _dashboard_script(
    rows: list[dict[str, str]], charts: list[dict[str, Any]], columns: list[str]
) -> str:
    chart_rows = [
        {"row_id": index, **{column: row.get(column, "") for column in columns}}
        for index, row in enumerate(rows)
    ]
    rows_json = json.dumps(chart_rows, ensure_ascii=False).replace("</", "<\\/")
    charts_json = json.dumps(charts, ensure_ascii=False).replace("</", "<\\/")
    return f"""
const allRows = {rows_json};
const chartSpecs = {charts_json};
let activeRows = null;
const numeric = (value) => {{ const n = Number(value); return value !== "" && Number.isFinite(n) ? n : null; }};
const currentRows = () => activeRows === null ? allRows : allRows.filter(row => activeRows.has(row.row_id));
function makeTraces(spec, rows) {{
  const column = spec.columns[0];
  if (spec.chart_type === "histogram") {{
    const items = rows.map(r => ({{id:r.row_id, value:numeric(r[column])}})).filter(x => x.value !== null);
    if (!items.length) return [{{x:[], y:[], type:"bar"}}];
    const min = Math.min(...items.map(x => x.value)), max = Math.max(...items.map(x => x.value));
    const bins = Math.min(20, Math.max(1, Math.floor(Math.sqrt(items.length))));
    const width = max > min ? (max-min)/bins : 1;
    const groups = Array.from({{length:bins}}, () => []);
    for (const item of items) groups[max > min ? Math.min(bins-1, Math.floor((item.value-min)/width)) : 0].push(item.id);
    return [{{type:"bar", x:groups.map((_,i)=>min+(i+.5)*width), y:groups.map(g=>g.length), customdata:groups, marker:{{color:"#3977b8"}}}}];
  }}
  if (spec.chart_type === "box") {{
    const items = rows.map(r => ({{id:r.row_id, value:numeric(r[column])}})).filter(x => x.value !== null);
    return [{{type:"box", x:items.map(()=>column), y:items.map(x=>x.value), customdata:items.map(x=>x.id), boxpoints:"all", jitter:.35, pointpos:-1.5, marker:{{color:"#3977b8"}}}}];
  }}
  if (spec.chart_type === "scatter") {{
    const [xcol,ycol] = spec.columns;
    const items = rows.map(r => ({{id:r.row_id, x:numeric(r[xcol]), y:numeric(r[ycol])}})).filter(x => x.x !== null && x.y !== null);
    return [{{type:"scatter", mode:"markers", x:items.map(x=>x.x), y:items.map(x=>x.y), customdata:items.map(x=>x.id), marker:{{color:"#3977b8",opacity:.75}}}}];
  }}
  if (spec.chart_type === "bar") {{
    const groups = new Map();
    for (const row of rows) {{ const label = row[column] || "(missing)"; if (!groups.has(label)) groups.set(label, []); groups.get(label).push(row.row_id); }}
    const items = [...groups.entries()].sort((a,b)=>b[1].length-a[1].length || a[0].localeCompare(b[0])).slice(0,15);
    return [{{type:"bar", orientation:"h", x:items.map(x=>x[1].length), y:items.map(x=>x[0]), customdata:items.map(x=>x[1]), marker:{{color:"#3977b8"}}}}];
  }}
  if (spec.chart_type === "correlation") {{
    const cols = spec.columns, z = cols.map(a => cols.map(b => {{
      const pairs = rows.map(r => [numeric(r[a]),numeric(r[b])]).filter(p=>p[0]!==null&&p[1]!==null);
      if (pairs.length < 2) return null;
      const mx=pairs.reduce((s,p)=>s+p[0],0)/pairs.length, my=pairs.reduce((s,p)=>s+p[1],0)/pairs.length;
      const xx=pairs.reduce((s,p)=>s+(p[0]-mx)**2,0), yy=pairs.reduce((s,p)=>s+(p[1]-my)**2,0);
      return xx===0||yy===0 ? null : pairs.reduce((s,p)=>s+(p[0]-mx)*(p[1]-my),0)/Math.sqrt(xx*yy);
    }}));
    return [{{type:"heatmap",x:cols,y:cols,z,zmin:-1,zmax:1,colorscale:"RdBu",reversescale:true}}];
  }}
  return [];
}}
function layoutFor(spec) {{
  const labels = {{histogram:[spec.columns[0],"Row count"],box:["",spec.columns[0]],scatter:spec.columns,bar:["Row count",spec.columns[0]]}};
  const [xaxis_title,yaxis_title] = labels[spec.chart_type] || ["",""];
  return {{title:{{text:spec.question,x:.02,xanchor:"left"}},template:"plotly_white",colorway:["#3977b8","#e07b39","#4a9c75","#c95454","#8c6bb1"],font:{{family:"Arial, sans-serif",size:12}},margin:{{l:55,r:25,t:65,b:55}},xaxis:{{title:xaxis_title,automargin:true,showgrid:false}},yaxis:{{title:yaxis_title,automargin:true,gridcolor:"#e8edf2",autorange:spec.chart_type==="bar"?"reversed":undefined}},clickmode:"event+select"}};
}}
async function updateDashboard() {{
  const rows = currentRows();
  await Promise.all(chartSpecs.map(spec => Plotly.react("chart-"+spec.id,makeTraces(spec,rows),layoutFor(spec),{{responsive:true,displaylogo:false}})));
  document.getElementById("filter-status").textContent = activeRows === null ? "Showing all rows" : `Filtered to ${{rows.length}} rows`;
}}
(async () => {{
  await updateDashboard();
  for (const spec of chartSpecs) {{
    const el = document.getElementById("chart-"+spec.id);
    el.on("plotly_click", event => {{
      const value = event.points?.[0]?.customdata;
      if (value === undefined || value === null) return;
      const ids = new Set(Array.isArray(value) ? value.flat(Infinity).filter(Number.isInteger) : [value]);
      if (!ids.size) return;
      const same = activeRows && activeRows.size === ids.size && [...ids].every(id => activeRows.has(id));
      activeRows = same ? null : ids;
      updateDashboard();
    }});
  }}
  document.getElementById("reset-filters").addEventListener("click",()=>{{activeRows=null;updateDashboard();}});
}})();
"""


def _summary(profile: dict[str, Any], log: dict[str, Any]) -> str:
    after = profile["after"]
    missing = sum(column["missing_count"] for column in after["columns"].values())
    cards = [
        ("Rows", f"{after['row_count']:,}"),
        ("Columns", f"{after['column_count']:,}"),
        ("Missing cells", f"{missing:,}"),
        ("Duplicate rows removed", f"{log['duplicate_rows_removed']:,}"),
    ]
    cards_html = "".join(
        f'<div class="metric"><span>{_escape(label)}</span><strong>{_escape(value)}</strong></div>'
        for label, value in cards
    )
    findings = "".join(f"<li>{_escape(item)}</li>" for item in log["findings"])
    if not findings:
        findings = "<li>No dataset findings were supplied.</li>"
    profile_rows = []
    for name, item in after["columns"].items():
        summary = (
            f"mean {_display(item['mean'])}; median {_display(item['median'])}; "
            f"IQR outliers {item['iqr_outlier_count']}"
            if item["inferred_type"] == "numeric"
            else f"mode {_display(item['mode'])} ({item['mode_frequency']} rows)"
        )
        profile_rows.append(
            "<tr>"
            f"<td>{_escape(name)}</td><td>{_escape(item['inferred_type'])}</td>"
            f"<td>{item['missing_count']:,} ({item['missing_percent']:.1f}%)</td>"
            f"<td>{item['unique_count']:,}</td><td>{_escape(summary)}</td>"
            f"<td>{'Yes' if item['likely_identifier'] else 'No'}</td></tr>"
        )
    return (
        f"<section class=\"metrics\">{cards_html}</section>"
        f"<section class=\"panel\"><h2>Key findings</h2><ul>{findings}</ul></section>"
        "<section class=\"panel\"><h2>Column profile</h2><div class=\"table-wrap\"><table>"
        "<thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Unique</th>"
        "<th>Summary</th><th>Likely ID</th></tr></thead><tbody>"
        + "".join(profile_rows)
        + "</tbody></table></div></section>"
    )


def _display(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{value:.4g}"
    return str(value)


def build_report(profile: dict[str, Any], log: dict[str, Any], manifest: dict[str, Any]) -> str:
    before, after = profile["before"], profile["after"]
    lines = [
        "# Exploratory Data Analysis",
        "",
        f"- Rows: {before['row_count']} before, {after['row_count']} after transformations.",
        f"- Columns: {after['column_count']}.",
        f"- Exact duplicate rows removed: {log['duplicate_rows_removed']}.",
        "",
        "## Dashboard",
        "",
        "Open [the interactive dashboard](analysis_dashboard.html) for summary cards, the full column profile, and cross-filtering charts.",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in log["findings"] or ["No dataset findings were supplied."])
    lines.extend(["", "## Transformations applied", ""])
    if log["column_transformations"]:
        for operation in log["column_transformations"]:
            lines.append(
                f"- **{operation['column']}** — {operation['reason']} "
                f"(conversion: {operation['conversion'] or 'none'}; "
                f"missing values: {operation['missing_values']}; outliers: {operation['outliers']}; "
                f"rows removed: {operation['rows_removed']})."
            )
    else:
        lines.append("- No per-column transformations were requested.")
    lines.extend([f"- Duplicate handling: {log['duplicate_reason']}", "", "## Chart downloads", ""])
    for chart in manifest["charts"]:
        if chart["status"] == "generated":
            relative = PurePosixPath(chart["path"]).relative_to(ARTIFACTS).as_posix()
            lines.append(f"- [{chart['question']} (SVG)]({relative}) — {chart['reason']}")
        else:
            lines.append(f"- Skipped **{chart['question']}**: {chart['error']}")
    if not manifest["charts"]:
        lines.append("- No chart was requested.")
    lines.extend(["", "No model was trained and no train/test split was created.", ""])
    return "\n".join(lines)


def render_artifacts(
    rows: list[dict[str, str]],
    profile: dict[str, Any],
    log: dict[str, Any],
    requests: list[dict[str, Any]],
) -> dict[str, bytes]:
    """Render standalone Plotly dashboard and static SVG chart downloads."""
    from plotly.offline import get_plotlyjs

    manifest: dict[str, Any] = {"charts": []}
    files: dict[str, bytes] = {}
    charts: list[dict[str, Any]] = []
    chart_columns: set[str] = set()

    for index, request in enumerate(requests, start=1):
        filename = f"chart_{index:02d}_{request['chart_type']}.svg"
        path = ARTIFACTS / "charts" / filename
        title = f"{request['question']} — {', '.join(request['columns'])}"
        try:
            figure = _figure(request, rows, title)
            svg = figure.to_image(format="svg", width=1000, height=620)
            if not svg.strip():
                raise ValueError("Plotly produced an empty SVG")
            files[str(path)] = svg
            chart = {
                "id": index,
                "chart_type": request["chart_type"],
                "columns": request["columns"],
                "question": request["question"],
                "reason": request["reason"],
                "path": str(path),
            }
            charts.append(chart)
            chart_columns.update(request["columns"])
            manifest["charts"].append(
                {"status": "generated", **{key: chart[key] for key in ("path", "question", "reason")}}
            )
        except (ValueError, KeyError) as error:
            manifest["charts"].append(
                {
                    "status": "skipped",
                    "path": str(path),
                    "question": request["question"],
                    "reason": request["reason"],
                    "error": str(error),
                }
            )

    dashboard_sections = "".join(
        f'<section class="chart panel"><div id="chart-{chart["id"]}" '
        f'aria-label="{_escape(chart["question"])}"></div>'
        f'<p>{_escape(chart["reason"])} · '
        f'<a href="charts/{_escape(PurePosixPath(chart["path"]).name)}" download>Download SVG</a></p></section>'
        for chart in charts
    )
    if not charts:
        dashboard_sections = '<section class="panel"><p>No valid charts were requested.</p></section>'
    profile_html = _summary(profile, log)
    plotly_script = get_plotlyjs()
    dashboard_js = _dashboard_script(rows, charts, sorted(chart_columns)) if charts else ""
    dashboard = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDA Dashboard</title><style>
:root{{--ink:#17212b;--muted:#64748b;--line:#dbe3eb;--panel:#fff;--bg:#f3f6fa;--blue:#174a7e}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px Arial,sans-serif}}
header{{background:var(--blue);color:#fff;padding:24px max(20px,calc((100% - 1400px)/2))}}
header h1{{margin:0 0 6px;font-size:25px}}header p{{margin:0;color:#dceafa}}
main{{max-width:1440px;margin:22px auto;padding:0 20px 36px}}h2{{font-size:18px;margin:0 0 14px}}
.toolbar{{display:flex;align-items:center;gap:12px;margin-bottom:16px;color:var(--muted)}}
button{{border:1px solid var(--line);background:#fff;padding:8px 12px;border-radius:6px;cursor:pointer;color:var(--ink)}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:14px;margin-bottom:16px}}
.metric,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:9px;box-shadow:0 1px 3px #0f172a0d}}
.metric{{padding:16px}}.metric span{{display:block;color:var(--muted);font-size:13px}}.metric strong{{display:block;font-size:27px;margin-top:9px}}
.panel{{padding:18px;margin-bottom:16px}}ul{{margin:0;padding-left:20px}}li+li{{margin-top:7px}}
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:16px}}
.chart{{margin:0;min-width:0}}.chart p{{color:var(--muted);font-size:13px;margin:8px 4px 0}}
.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line)}}th{{background:#f7f9fc;position:sticky;top:0}}
footer{{color:var(--muted);font-size:12px;padding:8px 2px}}@media(max-width:600px){{main{{padding:0 10px}}header{{padding:18px 14px}}.panel{{padding:12px}}}}
</style></head><body><header><h1>Exploratory Data Analysis</h1><p>Full-dataset profile with interactive, cross-filtering visuals</p></header>
<main><div class="toolbar"><button id="reset-filters" type="button">Clear chart filters</button><span id="filter-status">Showing all rows</span></div>
{profile_html}<h2>Charts</h2><div class="charts">{dashboard_sections}</div>
<footer>Click a data point or bar to filter compatible charts. Click the same selection again or use Clear chart filters to reset. Correlation matrices do not filter other charts.</footer></main>
<script>{plotly_script}</script><script>{dashboard_js}</script></body></html>"""

    files[str(DASHBOARD_PATH)] = dashboard.encode("utf-8")
    files[str(MANIFEST_PATH)] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    files[str(REPORT_PATH)] = build_report(profile, log, manifest).encode("utf-8")
    return files


def main() -> None:
    Path(str(ARTIFACTS)).mkdir(parents=True, exist_ok=True)
    with Path(str(DATA_PATH)).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    profile = json.loads(Path(str(PROFILE_PATH)).read_text(encoding="utf-8"))
    log = json.loads(Path(str(LOG_PATH)).read_text(encoding="utf-8"))
    requests = json.loads(Path(str(REQUESTS_PATH)).read_text(encoding="utf-8"))
    files = render_artifacts(rows, profile, log, requests)
    for path, content in files.items():
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    manifest = json.loads(files[str(MANIFEST_PATH)])
    print(
        json.dumps(
            {
                "generated": sum(chart["status"] == "generated" for chart in manifest["charts"]),
                "skipped": sum(chart["status"] == "skipped" for chart in manifest["charts"]),
                "dashboard": str(DASHBOARD_PATH),
            }
        )
    )


if __name__ == "__main__":
    main()
