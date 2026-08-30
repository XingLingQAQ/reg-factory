const $ = (selector) => document.querySelector(selector);
const state = {emails: [], tasks: []};

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function showMessage(text, ok = false) {
  $('#config-message').textContent = text || '';
  $('#config-message').className = `message ${ok ? 'ok' : 'bad'}`;
}

function renderEmails() {
  $('#email-count').textContent = state.emails.length;
  $('#emails').innerHTML = state.emails.map(item => `<div class="list-row"><span>${item.email}</span><b class="${item.status}">${item.status}</b></div>`).join('') || '<p class="muted">暂无邮箱</p>';
}

function renderTasks() {
  $('#tasks').innerHTML = state.tasks.map(task => {
    const logs = (task.logs || []).slice(-3).map(line => `<div>${line.replaceAll('&', '&amp;').replaceAll('<', '&lt;')}</div>`).join('');
    return `<article class="task"><div class="task-head"><strong>${task.email}</strong><span class="${task.status}">${task.status}</span>${task.status === 'running' ? `<button data-cancel="${task.id}" class="link">取消</button>` : ''}</div><div class="logs">${logs}</div></article>`;
  }).join('') || '<p class="muted">暂无任务</p>';
}

async function loadConfig() {
  const data = await api('/api/config');
  const config = data.config || {};
  $('#workspace-ids').value = (config.workspace_ids || []).join('\n');
  $('#workspace-route').value = config.workspace_route || 'request';
  $('#run-workspace').checked = config.run_workspace_join !== false;
  $('#concurrency').value = config.concurrency || 1;
  $('#sms-provider').value = config.sms_provider || 'auto';
  $('#node').value = config.node || 'auto';
  $('#group').value = config.group || 'k12';
}

async function saveConfig() {
  try {
    await api('/api/config', {method: 'PATCH', body: JSON.stringify({
      workspace_ids: $('#workspace-ids').value,
      workspace_route: $('#workspace-route').value,
      run_workspace_join: $('#run-workspace').checked,
      concurrency: Number($('#concurrency').value || 1),
      sms_provider: $('#sms-provider').value,
      node: $('#node').value.trim() || 'auto',
      group: $('#group').value.trim() || 'k12',
    })});
    showMessage('配置已保存', true);
  } catch (error) { showMessage(error.message); }
}

async function loadEmails() { state.emails = (await api('/api/emails')).items || []; renderEmails(); }
async function importEmails() {
  const text = $('#email-input').value.trim();
  if (!text) return showMessage('请填写邮箱记录');
  try { const data = await api('/api/emails/import', {method: 'POST', body: JSON.stringify({text})}); $('#email-input').value = ''; showMessage(`导入完成：新增 ${data.added}`, true); await loadEmails(); } catch (error) { showMessage(error.message); }
}
async function loadTasks() { state.tasks = (await api('/api/tasks')).items || []; renderTasks(); }
async function startTasks() {
  try { await saveConfig(); await api('/api/tasks', {method: 'POST', body: JSON.stringify({count: Number($('#task-count').value || 1)})}); await loadTasks(); } catch (error) { showMessage(error.message); }
}
async function refresh() { try { await Promise.all([loadConfig(), loadEmails(), loadTasks()]); $('#health-dot').className = 'online'; $('#health').textContent = '服务在线'; } catch (error) { $('#health').textContent = error.message; } }

$('#save-config').onclick = saveConfig;
$('#import-emails').onclick = importEmails;
$('#refresh-emails').onclick = loadEmails;
$('#refresh-tasks').onclick = loadTasks;
$('#start-tasks').onclick = startTasks;
$('#tasks').onclick = async (event) => { const id = event.target.dataset.cancel; if (id) { await api(`/api/tasks/${id}/cancel`, {method: 'POST', body: '{}'}); await loadTasks(); } };
setInterval(loadTasks, 2500);
refresh();
