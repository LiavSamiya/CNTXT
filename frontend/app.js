const state = { bootstrap: null, requests: 0, entities: 0 };

const $ = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));

function updateMetrics() {
  $('metricRequests').textContent = state.requests;
  $('metricEntities').textContent = state.entities;
}

function renderLogs(logs) {
  const body = $('logsBody');
  if (!logs.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty-row">No events yet.</td></tr>';
    return;
  }
  body.innerHTML = logs.map((log) => `
    <tr>
      <td>${escapeHtml((log.timestamp || '').slice(11, 19))}</td>
      <td>${escapeHtml(log.user || '—')}<br><small>${escapeHtml(log.role || '')}</small></td>
      <td>${escapeHtml((log.tool || '').replace('shieldai_', ''))}</td>
      <td><span class="log-decision ${escapeHtml(log.decision)}">${escapeHtml(log.decision)}</span></td>
      <td>${escapeHtml(log.entities_hidden ?? 0)}</td>
      <td>${escapeHtml(log.latency_ms ?? '—')} ms</td>
    </tr>`).join('');
}

function renderTimeline(decision, reason) {
  const list = [...document.querySelectorAll('#timeline li')];
  list.forEach((item) => item.classList.remove('done', 'blocked'));
  const finished = decision === 'BLOCK' ? 2 : 4;
  list.slice(0, finished).forEach((item) => item.classList.add('done'));
  if (decision === 'BLOCK') list[1].classList.add('blocked');
  const pill = $('decisionPill');
  pill.textContent = decision;
  pill.className = `decision ${decision.toLowerCase()}`;
  $('decisionReason').textContent = reason;
}

function renderMapping(mapping) {
  const output = $('mappingOutput');
  const rows = Object.entries(mapping || {});
  output.innerHTML = rows.length
    ? rows.map(([placeholder, value]) => `<div class="map-row"><code>${escapeHtml(placeholder)}</code><span title="Stored locally">${escapeHtml(value)}</span></div>`).join('')
    : '<span class="empty">No protected entities were found.</span>';
}

function currentChannel() {
  const tool = $('toolSelect').value;
  return tool === 'shieldai_get_channel_history' ? 'engineering' : 'engineering';
}

async function loadBootstrap() {
  const response = await fetch('/api/bootstrap');
  state.bootstrap = await response.json();
  $('userSelect').innerHTML = state.bootstrap.users.map((user) => `<option value="${user.id}">${escapeHtml(user.name)} · ${escapeHtml(user.role)}</option>`).join('');
  $('policySelect').innerHTML = state.bootstrap.policies.map((policy) => `<option value="${policy.id}">${escapeHtml(policy.name)}</option>`).join('');
  $('metricConnectors').textContent = state.bootstrap.connectors.length;
  renderLogs(state.bootstrap.logs);
  updateMetrics();
}

async function refreshLogs() {
  const response = await fetch('/api/logs');
  renderLogs(await response.json());
}

async function runDemo() {
  const button = $('runButton');
  button.disabled = true;
  button.innerHTML = '<span>◌</span> Enforcing policy…';
  try {
    const payload = {
      user_id: $('userSelect').value,
      policy_id: $('policySelect').value,
      tool: $('toolSelect').value,
      query: $('queryInput').value,
      channel: currentChannel(),
    };
    const response = await fetch('/api/demo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Gateway request failed');
    state.requests += 1;
    state.entities += data.entities?.length || 0;
    updateMetrics();
    renderTimeline(data.decision, data.reason);
    $('latency').textContent = `${data.audit.latency_ms} ms · ${data.entities.length} entities transformed`;
    $('originalOutput').textContent = data.raw_context || 'Policy blocked the request before connector data was retrieved.';
    $('safeOutput').textContent = data.safe_context || 'No safe context returned because policy blocked the request.';
    $('responseOutput').textContent = data.decision === 'BLOCK'
      ? `Request blocked: ${data.reason}`
      : data.rehydrated_response || 'No rehydration was required.';
    renderMapping(data.mapping || {});
    await refreshLogs();
  } catch (error) {
    renderTimeline('BLOCK', error.message);
    $('safeOutput').textContent = `ShieldAI error: ${error.message}`;
  } finally {
    button.disabled = false;
    button.innerHTML = '<span>▶</span> Run through ShieldAI Gateway';
  }
}

$('runButton').addEventListener('click', runDemo);
$('refreshLogs').addEventListener('click', refreshLogs);
$('toolSelect').addEventListener('change', () => {
  const isHistory = $('toolSelect').value === 'shieldai_get_channel_history';
  $('queryInput').disabled = isHistory;
  $('queryInput').value = isHistory ? 'Channel history uses the protected source.' : 'latest Falcon discussion';
});

loadBootstrap().catch((error) => { $('decisionReason').textContent = `Dashboard initialization failed: ${error.message}`; });
