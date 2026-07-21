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

async function toggleCategory(catId) {
  const cats = new Set(policy.hide_categories || []);
  if (cats.has(catId)) cats.delete(catId); else cats.add(catId);
  policy.hide_categories = [...cats];
  renderCategories();
  await savePolicy();
}

// ── Dictionary ──────────────────────────────────────────────────────────
function renderDictionary() {
  const list = $('dictionaryList');
  const entries = Object.entries(policy.custom_dictionary || {});
  if (!entries.length) {
    list.innerHTML = '<span class="empty">No custom terms defined.</span>';
    return;
  }
  list.innerHTML = entries.map(([term, type]) =>
    `<div class="dict-item">
      <span class="dict-term">${esc(term)}</span>
      <span class="dict-type">${esc(type)}</span>
      <button class="dict-remove" data-term="${esc(term)}" title="Remove">×</button>
    </div>`
  ).join('');

  list.querySelectorAll('.dict-remove').forEach(btn => {
    btn.addEventListener('click', () => removeTerm(btn.dataset.term));
  });
}

async function addTerm() {
  const input = $('newTermInput');
  const type = $('newTermType').value;
  const term = input.value.trim();
  if (!term) return;
  if (!policy.custom_dictionary) policy.custom_dictionary = {};
  policy.custom_dictionary[term] = type;
  input.value = '';
  renderDictionary();
  await savePolicy();
}

async function removeTerm(term) {
  if (policy.custom_dictionary) {
    delete policy.custom_dictionary[term];
    renderDictionary();
    await savePolicy();
  }
}

async function savePolicy() {
  await fetch('/api/policy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      hide_categories: policy.hide_categories,
      custom_dictionary: policy.custom_dictionary,
    }),
  });
}

// ── Steps Animation ─────────────────────────────────────────────────────
function resetSteps() {
  document.querySelectorAll('.step').forEach(s => {
    s.classList.remove('done', 'active');
  });
}

function animateStep(n) {
  return new Promise(resolve => {
    const step = document.querySelector(`.step[data-step="${n}"]`);
    if (!step) { resolve(); return; }
    step.classList.add('active');
    setTimeout(() => {
      step.classList.remove('active');
      step.classList.add('done');
      resolve();
    }, 350);
  });
}

// ── Run Protection ──────────────────────────────────────────────────────
async function runProtect() {
  const btn = $('runBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="run-icon">◌</span> Processing…';
  resetSteps();

  try {
    // Animate steps
    await animateStep(1);
    await animateStep(2);

    const payload = {
      tool: $('sourceSelect').value,
      query: $('queryInput').value,
      channel: 'engineering',
    };

    const res = await fetch('/api/protect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');

    await animateStep(3);
    await animateStep(4);

    // Render results
    $('originalOutput').textContent = data.raw_context || 'No data returned.';
    $('safeOutput').textContent = data.safe_context || 'No transformation needed.';

    // Mapping
    const mapEntries = Object.entries(data.mapping || {});
    $('mappingOutput').innerHTML = mapEntries.length
      ? mapEntries.map(([ph, val]) =>
          `<div class="map-row"><code>${esc(ph)}</code><span class="arrow">←</span><span>${esc(val)}</span></div>`
        ).join('')
      : '<span class="empty">No entities detected.</span>';

    // LLM response + rehydration
    $('llmOutput').textContent = data.demo_llm_response || '—';
    $('rehydratedOutput').textContent = data.rehydrated_response || '—';

    // Stats
    const entities = data.entities || [];
    const types = [...new Set(entities.map(e => e.entity_type))];
    $('statEntities').textContent = `🛡️ ${entities.length} entities hidden`;
    $('statLatency').textContent = `⚡ ${data.audit?.latency_ms ?? '—'} ms`;
    $('statMemory').textContent = `🧠 ${data.project_memory_entries ?? 0} memory entries`;

  } catch (err) {
    $('safeOutput').textContent = `Error: ${err.message}`;
    $('originalOutput').textContent = '—';
    $('mappingOutput').innerHTML = '<span class="empty">—</span>';
    $('llmOutput').textContent = '—';
    $('rehydratedOutput').textContent = '—';
    $('statEntities').textContent = '❌ Error';
    $('statLatency').textContent = '';
    $('statMemory').textContent = '';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span class="run-icon">▶</span> Retrieve & Protect Context';
  }
}

// ── Event Listeners ─────────────────────────────────────────────────────
$('runBtn').addEventListener('click', runProtect);
$('addTermBtn').addEventListener('click', addTerm);
$('newTermInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') addTerm();
});

$('sourceSelect').addEventListener('change', () => {
  const isHistory = $('sourceSelect').value === 'shieldai_get_channel_history';
  $('queryInput').disabled = isHistory;
  $('queryInput').value = isHistory ? '' : 'latest Falcon discussion';
});

// ── Init ────────────────────────────────────────────────────────────────
loadPolicy().catch(err => {
  console.error('Failed to load policy:', err);
});
