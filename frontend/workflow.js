(() => {
  const apiBase = () => String(window.PIVOT_API_BASE || '').replace(/\/$/, '');
  const progress = $('#analysis-progress');
  const stages = ['Receiving your CSV', 'Profiling the dataset', 'Planning EDA and charts', 'Building dashboard', 'Ready to explore'];
  let activeAnalysisId = null;

  function showProgress(filename) {
    progress.hidden = false;
    progress.classList.remove('progress-error');
    progress.innerHTML = `<div class="progress-heading"><div><div class="panel-kicker">LIVE ANALYSIS</div><h3>Turning your CSV into a dashboard</h3><p>${escapeHtml(filename)}</p></div><span class="progress-percent" id="progress-percent">0%</span></div><div class="progress-track" role="progressbar" aria-label="Analysis progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span id="progress-fill"></span></div><div class="progress-steps" id="progress-steps"></div><div class="progress-note" id="progress-note"></div>`;
    $('#progress-steps').innerHTML = stages.slice(0, 4).map((label, index) => `<div class="progress-step" data-step="${index}"><span class="step-marker">${String(index + 1).padStart(2, '0')}</span><span>${label}</span></div>`).join('');
  }

  function setProgress(percent, message, status = 'running') {
    const value = Math.max(0, Math.min(100, Number(percent) || 0));
    const fill = $('#progress-fill');
    if (!fill) return;
    $('#progress-percent').textContent = `${Math.round(value)}%`;
    fill.style.width = `${value}%`;
    $('.progress-track', progress).setAttribute('aria-valuenow', String(Math.round(value)));
    $('#progress-note').textContent = message || '';
    const current = value < 18 ? 0 : value < 40 ? 1 : value < 72 ? 2 : 3;
    $$('.progress-step', progress).forEach((step, index) => {
      step.classList.toggle('done', index < current || status === 'completed');
      step.classList.toggle('current', index === current && status !== 'completed' && status !== 'failed');
      step.classList.toggle('failed', status === 'failed' && index === current);
    });
    if (status === 'completed') {
      $('#progress-percent').textContent = '100%';
      fill.style.width = '100%';
    }
    if (status === 'failed') progress.classList.add('progress-error');
  }

  async function readResponse(response) {
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload.message || payload.detail || `Request failed (${response.status}).`);
    return payload;
  }

  function renderMetrics(result) {
    const profile = result.profile?.after || {};
    const columns = profile.columns || {};
    const missing = Object.values(columns).reduce((total, column) => total + Number(column.missing_count || 0), 0);
    $('#metric-rows').textContent = Number(result.row_count || 0).toLocaleString();
    $('#metric-columns').textContent = Number(result.column_count || Object.keys(columns).length).toLocaleString();
    $('#metric-missing').textContent = Number(result.missing_value_count ?? missing).toLocaleString();
    $('#metric-duplicates').textContent = Number(result.duplicate_row_count ?? profile.duplicate_row_count ?? 0).toLocaleString();
  }

  function renderArtifacts(result) {
    const container = $('#artifact-links');
    container.replaceChildren();
    const artifacts = result.artifacts || [];
    for (const artifact of artifacts) {
      const anchor = document.createElement('a');
      const artifactUrl = new URL(artifact.url, apiBase());
      artifactUrl.searchParams.set('download', '1');
      anchor.href = artifactUrl.href;
      anchor.download = artifact.name;
      anchor.textContent = artifact.name.replaceAll('_', ' ');
      anchor.className = 'artifact-link';
      container.append(anchor);
    }
    $('#artifact-empty').hidden = artifacts.length > 0;
  }

  async function runBackend(file, rows, classification) {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('classification', classification);
    setProgress(8, 'Sending the approved CSV to your local analysis service.');
    const created = await readResponse(await fetch(`${apiBase()}/api/analyses`, { method: 'POST', body: form }));
    activeAnalysisId = created.analysis_id;
    if (!activeAnalysisId) throw new Error('The analysis service did not return an analysis ID.');
    let state = created;
    const deadline = Date.now() + 30 * 60 * 1000;
    while (!['completed', 'complete', 'succeeded', 'failed', 'error'].includes(String(state.status || '').toLowerCase())) {
      if (Date.now() > deadline) throw new Error('The analysis is taking longer than expected. Check the Python service and try again.');
      setProgress(state.progress ?? 12, state.message || 'Your analyst is working through the next step.');
      await new Promise(resolve => setTimeout(resolve, 1100));
      state = await readResponse(await fetch(`${apiBase()}/api/analyses/${encodeURIComponent(activeAnalysisId)}`));
    }
    if (['failed', 'error'].includes(String(state.status).toLowerCase())) throw new Error(state.message || 'The analysis failed.');
    const result = state.result || {};
    renderCSV(rows, file.name);
    renderMetrics(result);
    renderArtifacts(result);
    const frame = $('#plotly-frame');
    frame.src = new URL(result.dashboard_url, apiBase()).href;
    $('#plotly-dashboard-panel').hidden = false;
    $('#ask-btn').disabled = false;
    $('.status-pill').innerHTML = '<i></i> ANALYZED';
    $('#dataset-updated').textContent = 'Just now';
    setProgress(100, 'Your interactive dashboard and downloadable analysis files are ready.', 'completed');
  }

  window.loadFile = async function(file) {
    if (!/\.csv$/i.test(file.name) && file.type !== 'text/csv') { toast('Please choose a .csv file.'); return; }
    if (file.size > 25 * 1024 * 1024) { toast('That file is over the 25 MB upload limit.'); return; }
    if (!apiBase()) { toast('Set PIVOT_API_BASE in config.js and start the Python API.'); return; }
    const classification = $('#data-classification').value;
    if (!classification) { toast('Choose a data classification before upload.'); return; }
    if (classification === 'private') { toast('Private data is blocked from analysis.'); return; }
    activeAnalysisId = null;
    $('#ask-btn').disabled = true;
    $('#plotly-dashboard-panel').hidden = true;
    $('#artifact-links').replaceChildren();
    $('#artifact-empty').hidden = false;
    showProgress(file.name);
    try {
      const text = await file.text();
      const rows = parseCSV(text);
      if (rows.length < 2 || rows[0].length < 1) throw new Error('Your file needs a header and at least one data row.');
      await runBackend(file, rows, classification);
      toast('Your full-dataset dashboard is ready.');
    } catch (error) {
      setProgress(0, error.message || 'Something went wrong while analyzing this file.', 'failed');
      toast(error.message || 'Could not analyze that CSV.');
    }
  };

  $('#sample-btn').addEventListener('click', async () => {
    $('#data-classification').value = 'sample';
    try {
      const response = await fetch(`${apiBase()}/sample.csv`);
      if (!response.ok) throw new Error('Could not load the included sample CSV.');
      const blob = await response.blob();
      await window.loadFile(new File([blob], 'sample_data.csv', { type: 'text/csv' }));
    } catch (error) { toast(error.message || 'Could not load the sample.'); }
  });

  window.sendMessage = async function(question) {
    if (!question?.trim()) return;
    if (!activeAnalysisId) { toast('Upload a sample or public CSV before asking a question.'); return; }
    const body = $('#chat-body');
    const user = document.createElement('div');
    user.className = 'user-message';
    user.innerHTML = `<span>${escapeHtml(question)}</span>`;
    body.append(user);
    $('#chat-input').value = '';
    const reply = document.createElement('div');
    reply.className = 'reply-message reply-loading';
    reply.textContent = 'Checking your data…';
    body.append(reply);
    body.scrollTop = body.scrollHeight;
    try {
      const response = await fetch(`${apiBase()}/api/analyses/${encodeURIComponent(activeAnalysisId)}/questions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }),
      });
      const answer = await readResponse(response);
      reply.textContent = answer.answer || 'The analyst did not return an answer.';
    } catch (error) { reply.textContent = `I couldn't reach the analyst: ${error.message}`; }
    reply.classList.remove('reply-loading');
    body.scrollTop = body.scrollHeight;
  };

  $('#chat-form').addEventListener('submit', event => {
    event.preventDefault();
    window.sendMessage($('#chat-input').value);
  });
  $$('.insight-link').forEach(button => button.addEventListener('click', () => window.openPivotChat(button.dataset.prompt)));
  $$('.suggestions button').forEach(button => button.addEventListener('click', () => window.sendMessage(button.dataset.question)));
  $('#download-report').addEventListener('click', () => {
    const report = [...$$('.artifact-link')].find(link => link.textContent.trim() === 'analysis report.md');
    if (report) report.click();
    else toast('Run an analysis first to download its report.');
  });
})();
