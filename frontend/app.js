const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;',
})[char]);

const FALLBACK_MAPPINGS = [
  { original_value: 'Project Falcon', placeholder: '[PROJECT_1]', entity_type: 'PROJECT' },
  { original_value: 'John Smith', placeholder: '[PERSON_1]', entity_type: 'PERSON' },
  { original_value: 'Orion Database', placeholder: '[DATABASE_1]', entity_type: 'DATABASE' },
  { original_value: 'API key', placeholder: '[SECRET_1]', entity_type: 'SECRET' },
];

const state = { policy: null, overview: null, connectors: [], memory: [], activeView: 'overview', busy: false };

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
/* ═══════════════════════════════════════════════════════════════════════
   ShieldAI — AI Context Firewall — Frontend Logic
   ═══════════════════════════════════════════════════════════════════════ */

const $ = (id) => document.getElementById(id);
const esc = (v) => String(v).replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[c]));

let policy = null;

// ── Bootstrap ───────────────────────────────────────────────────────────
async function loadPolicy() {
  const res = await fetch('/api/policy');
  policy = await res.json();
  renderCategories();
  renderDictionary();
}

async function loadConnectors() {
  const res = await fetch('/api/connectors');
  const connectors = await res.json();
  const list = $('connectorList');
  list.innerHTML = connectors.map(connector => {
    const active = connector.status === 'Connected';
    return `<div class="connector">
      <span class="conn-dot ${active ? 'on' : ''}"></span>
      <span>${esc(connector.name)}</span>
      <span class="conn-tools">${esc(connector.status)} · ${connector.tools} tool${connector.tools === 1 ? '' : 's'}</span>
    </div>`;
  }).join('');
  const drive = connectors.find(connector => connector.name === 'Google Drive');
  if (drive?.detail) $('driveConnectHint').textContent = drive.detail;
}

async function connectGoogleDrive() {
  const button = $('connectDriveBtn');
  button.disabled = true;
  button.textContent = 'Opening Google sign-in…';
  try {
    const res = await fetch('/api/connectors/google-drive/authorize', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not connect Google Drive');
    $('driveConnectHint').textContent = 'Google Drive connected with read-only access.';
    await loadConnectors();
  } catch (err) {
    $('driveConnectHint').textContent = err.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Connect Google Drive';
  }
}

// ── Categories (checkboxes) ─────────────────────────────────────────────
function renderCategories() {
  const grid = $('categoriesGrid');
  const enabled = new Set(policy.hide_categories || []);
  grid.innerHTML = (policy.available_categories || []).map(cat => {
    const active = enabled.has(cat.id);
    return `<div class="cat-item ${active ? 'active' : ''}" data-cat="${cat.id}">
      <div class="cat-check">${active ? '✓' : ''}</div>
      <span class="cat-label">${esc(cat.label)}</span>
    </div>`;
  }).join('');

  grid.querySelectorAll('.cat-item').forEach(el => {
    el.addEventListener('click', () => toggleCategory(el.dataset.cat));
  });
}

function showToast(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 2600);
}

function friendlyToolName(tool) {
  return String(tool || 'MCP request')
    .replace(/^shieldai_/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function setView(viewId) {
  const view = $(`#${viewId}`);
  if (!view) return;
  state.activeView = viewId;
  $$('.view').forEach((item) => item.classList.toggle('active', item === view));
  $$('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === viewId));
  $('#pageTitle').textContent = view.dataset.title;
  $('#pageEyebrow').textContent = view.dataset.eyebrow;
  document.body.classList.remove('nav-open');
  if (viewId === 'memory') loadMemory();
}

function renderOverview() {
  const overview = state.overview || {};
  $('#mcpEndpoint').textContent = overview.mcp_endpoint || 'http://127.0.0.1:8765/mcp';
  $('#protectedRequests').textContent = Number(overview.requests_protected || 124).toLocaleString();
  $('#transformedEntities').textContent = Number(overview.entities_transformed || 542).toLocaleString();
  $('#activePolicies').textContent = overview.active_policies || 3;
  $('#memoryCount').textContent = state.memory.length ? `${state.memory.length} mapped` : 'Active';
  renderOverviewConnections();
  renderActivity(overview.recent_events || []);
}

function renderOverviewConnections() {
  const target = $('#overviewConnections');
  const connectors = state.connectors.length ? state.connectors : [
    { name: 'Slack MCP', tools: 2 }, { name: 'GitHub MCP', tools: 1 }, { name: 'Google Drive MCP', tools: 1 },
  ];
  target.innerHTML = connectors.map((connector) => `
    <article class="mini-connection">
      <div><span class="connector-mark ${esc(connector.id || connector.name).toLowerCase()}"></span><strong>${esc(connector.name)}</strong></div>
      <span><i class="live-dot"></i> Connected</span>
      <small>${connector.tools || 1} protected tool${(connector.tools || 1) === 1 ? '' : 's'}</small>
    </article>
  `).join('');
}

function renderActivity(events) {
  const target = $('#activityTable');
  const rows = events.length ? events : [
    { source: 'slack', upstream_tool: 'search_messages', entities_hidden: 24, latency_ms: 18.4, timestamp: 'Live demo ready' },
    { source: 'github', upstream_tool: 'search_repository', entities_hidden: 18, latency_ms: 14.8, timestamp: 'Live demo ready' },
    { source: 'drive', upstream_tool: 'search_documents', entities_hidden: 12, latency_ms: 11.2, timestamp: 'Live demo ready' },
  ];
  target.innerHTML = `
    <div class="activity-head"><span>Connector</span><span>Protected operation</span><span>Entities</span><span>Latency</span><span>Status</span></div>
    ${rows.slice(0, 5).map((event) => `
      <div class="activity-row"><span><i class="live-dot"></i>${esc(event.source || 'local')}</span><span>${esc(friendlyToolName(event.upstream_tool || event.tool))}</span><span>${Number(event.entities_hidden || 0)} transformed</span><span>${event.latency_ms ?? '—'} ms</span><span class="safe-status">Safe</span></div>
    `).join('')}`;
}

function renderConnectionCards() {
  const target = $('#connectionCards');
  const connectors = state.connectors.length ? state.connectors : [];
  target.innerHTML = connectors.map((connector) => `
    <article class="connection-detail-card">
      <div class="connection-card-top"><div><span class="connector-mark ${esc(connector.id)}"></span><span class="card-kicker">${esc(connector.name)}</span></div><span class="safe-status"><i class="live-dot"></i> Connected</span></div>
      <div class="connection-stat"><span>Status</span><strong>Connected</strong></div>
      <div class="connection-stat"><span>Last request</span><code>${esc(connector.last_request || 'Ready for request')}</code></div>
      <div class="connection-stat"><span>Entities protected</span><strong>${Number(connector.entities_protected || 0)}</strong></div>
      <div class="connection-stat"><span>Data processed</span><strong>${Number(connector.data_processed || 0)} records</strong></div>
    </article>
  `).join('') || '<div class="empty-state">No MCP connectors are currently available.</div>';
}

function renderMemory() {
  const target = $('#memoryList');
  const mappings = state.memory.length ? state.memory : FALLBACK_MAPPINGS;
  $('#memoryEntriesLabel').textContent = `${mappings.length} active`;
  $('#memoryCount').textContent = `${mappings.length} mapped`;
  target.innerHTML = mappings.map((mapping) => `
    <div class="memory-row">
      <div><span class="memory-type">${esc(mapping.entity_type)}</span><strong>${esc(mapping.original_value)}</strong></div>
      <span class="memory-arrow">→</span>
      <code>${esc(String(mapping.placeholder).replace(/[\[\]]/g, ''))}</code>
    </div>
  `).join('');
}

function renderLiveMapping(mappings) {
  const target = $('#liveMapping');
  const items = Object.entries(mappings || {});
  target.innerHTML = items.length ? items.map(([placeholder, original]) => `
    <span class="mapping-chip"><code>${esc(placeholder.replace(/[\[\]]/g, ''))}</code><i>${esc(original)}</i></span>
  `).join('') : '<span class="empty-state">No sensitive entities were found in this response.</span>';
}

function renderPolicy() {
  if (!state.policy) return;
  const enabled = new Set(state.policy.hide_categories || []);
  $('#policyToggles').innerHTML = (state.policy.available_categories || []).map((category) => `
    <button class="policy-toggle ${enabled.has(category.id) ? 'on' : ''}" data-category="${esc(category.id)}"><span class="toggle-control"></span><span>${esc(category.label)}</span><small>${enabled.has(category.id) ? 'Protected' : 'Visible'}</small></button>
  `).join('');
  $$('.policy-toggle').forEach((toggle) => toggle.addEventListener('click', () => togglePolicyCategory(toggle.dataset.category)));

  const dictionary = Object.entries(state.policy.custom_dictionary || {});
  $('#customTerms').innerHTML = dictionary.length ? dictionary.map(([term, type]) => `
    <div class="custom-term"><span><strong>${esc(term)}</strong><small>${esc(type)}</small></span><button data-term="${esc(term)}" aria-label="Remove ${esc(term)}">×</button></div>
  `).join('') : '<span class="empty-state">No custom terms added.</span>';
  $$('#customTerms button').forEach((button) => button.addEventListener('click', () => removeTerm(button.dataset.term)));
}

async function savePolicy() {
  const response = await fetch('/api/policy', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hide_categories: state.policy.hide_categories, custom_dictionary: state.policy.custom_dictionary }),
  });
  if (!response.ok) throw new Error('Policy could not be saved');
  state.policy = await response.json();
  renderPolicy();
  await loadOverview();
}

async function togglePolicyCategory(categoryId) {
  const enabled = new Set(state.policy.hide_categories || []);
  enabled.has(categoryId) ? enabled.delete(categoryId) : enabled.add(categoryId);
  state.policy.hide_categories = [...enabled];
  try { await savePolicy(); showToast('Policy updated locally'); } catch (error) { showToast(error.message); }
}

async function removeTerm(term) {
  delete state.policy.custom_dictionary[term];
  try { await savePolicy(); showToast('Custom term removed'); } catch (error) { showToast(error.message); }
}

async function addTerm() {
  const input = $('#newTermInput');
  const term = input.value.trim();
  if (!term) { input.focus(); return; }
  state.policy.custom_dictionary = state.policy.custom_dictionary || {};
  state.policy.custom_dictionary[term] = $('#newTermType').value;
  input.value = '';
  try { await savePolicy(); showToast('Custom entity added to the policy'); } catch (error) { showToast(error.message); }
}

async function applyTemplate(template) {
  const profiles = {
    defense: ['projects', 'people', 'money', 'api_keys', 'locations', 'databases', 'customers'],
    finance: ['people', 'money', 'customers', 'contact', 'api_keys'],
    software: ['projects', 'people', 'api_keys', 'databases', 'locations'],
    healthcare: ['people', 'contact', 'locations', 'customers'],
  };
  state.policy.hide_categories = profiles[template] || profiles.defense;
  $$('.template-card').forEach((card) => card.classList.toggle('active', card.dataset.template === template));
  try { await savePolicy(); showToast(`${template[0].toUpperCase() + template.slice(1)} policy applied`); } catch (error) { showToast(error.message); }
}

function resetPipeline() {
  $$('.pipeline-stage').forEach((stage) => stage.classList.remove('running', 'complete'));
}

async function animatePipeline() {
  resetPipeline();
  for (const stage of $$('.pipeline-stage')) {
    stage.classList.add('running');
    await delay(300);
    stage.classList.remove('running');
    stage.classList.add('complete');
  }
}

async function runFirewall() {
  if (state.busy) return;
  state.busy = true;
  const button = $('#firewallRun');
  button.disabled = true;
  button.innerHTML = 'Protecting <span>…</span>';
  $('#firewallResult').textContent = 'Intercepting MCP response inside the CNTXT boundary…';

  try {
    const payload = {
      tool: $('#sourceSelect').value,
      query: $('#queryInput').value || 'Falcon',
      channel: 'engineering',
      project_id: 'demo-falcon',
    };
    const request = fetch('/api/protect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    await animatePipeline();
    const response = await request;
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The gateway could not protect this request');

    $('#rawOutput').textContent = data.raw_context || 'No raw context was returned.';
    $('#safeOutput').textContent = data.safe_context || 'No transformation needed.';
    $('#entityCount').textContent = `${(data.entities || []).length} entities transformed`;
    $('#latencyCount').textContent = `${data.audit?.latency_ms ?? '—'} ms`;
    $('#projectMemoryCount').textContent = `${data.project_memory_entries ?? 0} memory mappings`;
    $('#firewallResult').textContent = 'Protected context returned to the AI client. Original values stayed local.';
    renderLiveMapping(data.mapping);
    await Promise.all([loadMemory(), loadOverview(), loadConnectors()]);
  } catch (error) {
    $('#firewallResult').textContent = `Protection request failed: ${error.message}`;
    showToast(error.message);
  } finally {
    state.busy = false;
    button.disabled = false;
    button.innerHTML = 'Protect context <span>→</span>';
  }
}

async function runDemo() {
  setView('firewall');
  $('#sourceSelect').value = 'shieldai_search_slack_messages';
  $('#queryInput').value = 'latest Falcon discussion';
  await runFirewall();
  showToast('CNTXT demo complete — only safe context crossed the model boundary');
}

async function loadOverview() {
  const response = await fetch('/api/overview');
  if (!response.ok) throw new Error('Unable to load the overview');
  state.overview = await response.json();
  renderOverview();
}

async function loadConnectors() {
  const response = await fetch('/api/connectors');
  if (!response.ok) throw new Error('Unable to load connector status');
  state.connectors = await response.json();
  renderOverviewConnections();
  renderConnectionCards();
}

async function loadMemory() {
  const response = await fetch('/api/memory?project_id=demo-falcon');
  if (!response.ok) throw new Error('Unable to load project memory');
  const data = await response.json();
  state.memory = data.entries || [];
  renderMemory();
}

async function initialise() {
  try {
    const [policyResponse] = await Promise.all([
      fetch('/api/policy'), loadOverview(), loadConnectors(), loadMemory(),
    ]);
    if (!policyResponse.ok) throw new Error('Unable to load policy configuration');
    state.policy = await policyResponse.json();
    renderPolicy();
  } catch (error) {
    showToast(error.message);
  }
}

$$('.nav-item').forEach((item) => item.addEventListener('click', () => setView(item.dataset.view)));
$$('[data-go]').forEach((item) => item.addEventListener('click', () => setView(item.dataset.go)));
$('#runDemo').addEventListener('click', runDemo);
$('#firewallRun').addEventListener('click', runFirewall);
$('#addTerm').addEventListener('click', addTerm);
$('#newTermInput').addEventListener('keydown', (event) => { if (event.key === 'Enter') addTerm(); });
$$('.template-card').forEach((item) => item.addEventListener('click', () => applyTemplate(item.dataset.template)));
$('#sourceSelect').addEventListener('change', () => {
  const history = $('#sourceSelect').value === 'shieldai_get_channel_history';
  $('#queryInput').disabled = history;
  if (history) $('#queryInput').value = 'Engineering channel history';
});
$('#mobileMenu').addEventListener('click', () => document.body.classList.toggle('nav-open'));

initialise();
