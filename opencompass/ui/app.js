// OpenCompass Dev — UI Application
(function() {
  'use strict';

  const API = '';  // 同源，不需要前缀
  let refreshInterval = null;

  // ---- Navigation ----
  function initNav() {
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', () => {
        const page = item.dataset.page;
        showPage(page);
      });
    });
  }

  function showPage(name) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const el = document.getElementById('page-' + name);
    if (el) el.classList.add('active');
    const nav = document.querySelector(`.nav-item[data-page="${name}"]`);
    if (nav) nav.classList.add('active');
    document.getElementById('pageTitle').textContent = nav ? nav.textContent.trim() : name;

    // Load data for the page
    if (name === 'dashboard' || name === 'tasks') loadDashboard();
    if (name === 'bugs') loadBugReport();
  }

  // ---- Mobile menu ----
  document.getElementById('menuToggle')?.addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });

  // ---- API helpers ----
  async function api(url, options = {}) {
    try {
      const resp = await fetch(API + url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      return await resp.json();
    } catch (e) {
      console.error('API error:', e);
      toast('API 请求失败: ' + e.message, 'error');
      return null;
    }
  }

  // ---- Toast ----
  function toast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  // ---- Badge helper ----
  function statusBadge(status) {
    const map = {
      pending: '等待中', running: '运行中', completed: '已完成',
      failed: '失败', paused: '已暂停', cancelled: '已取消',
      retrying: '重试中', cancelling: '取消中',
    };
    const label = map[status] || status;
    return `<span class="badge badge-${status}">${label}</span>`;
  }

  // ---- Dashboard ----
  async function loadDashboard() {
    const status = await api('/api/v1/health');
    if (!status) return;

    // Fetch recent tasks from all tasks endpoint (we'll use a simple list approach)
    const tasks = await listTasks('');
    if (!tasks) return;

    const total = tasks.length;
    const completed = tasks.filter(t => t.status === 'completed').length;
    const running = tasks.filter(t => t.status === 'running' || t.status === 'retrying').length;
    const failed = tasks.filter(t => t.status === 'failed').length;
    const paused = tasks.filter(t => t.status === 'paused').length;

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statCompleted').textContent = completed;
    document.getElementById('statRunning').textContent = running;
    document.getElementById('statFailed').textContent = failed;
    document.getElementById('statPaused').textContent = paused;
    document.getElementById('statSuccessRate').textContent = total > 0 ? Math.round(completed / total * 100) + '%' : '-';

    // Recent tasks (last 10)
    const recent = tasks.slice(-10).reverse();
    const tbody = document.querySelector('#recentTasks tbody');
    tbody.innerHTML = recent.map(t => `
      <tr>
        <td><code>${t.id}</code></td>
        <td>${t.type || '-'}</td>
        <td>${statusBadge(t.status)}</td>
        <td>${t.created_at ? new Date(t.created_at * 1000).toLocaleTimeString() : '-'}</td>
        <td>
          <button class="btn-xs" onclick="showTaskDetail('${t.id}')">详情</button>
        </td>
      </tr>
    `).join('') || '<tr><td colspan="5" class="empty-state">暂无任务</td></tr>';

    // All tasks
    const allTbody = document.querySelector('#allTasks tbody');
    allTbody.innerHTML = tasks.map(t => {
      const result = t.result || {};
      const passed = result.passed_tests || '-';
      const totalTests = result.total_tests || '-';
      const elapsed = result.execution_time ? result.execution_time.toFixed(1) + 's' : '-';
      return `
        <tr>
          <td><code>${t.id}</code></td>
          <td>${t.type || '-'}</td>
          <td>${statusBadge(t.status)}</td>
          <td>${passed}/${totalTests}</td>
          <td>${elapsed}</td>
          <td>
            ${t.status === 'running' ? `<button class="btn-xs" onclick="pauseTask('${t.id}')">⏸ 暂停</button>` : ''}
            ${t.status === 'paused' ? `<button class="btn-xs" onclick="resumeTask('${t.id}')">▶ 继续</button>` : ''}
            ${t.status === 'failed' ? `<button class="btn-xs" onclick="retryTask('${t.id}')">🔄 重试</button>` : ''}
            <button class="btn-xs" onclick="showTaskDetail('${t.id}')">详情</button>
          </td>
        </tr>
      `;
    }).join('') || '<tr><td colspan="6" class="empty-state">暂无任务</td></tr>';
  }

  async function listTasks(filter) {
    const url = filter ? `/api/v1/tasks?status=${filter}` : '/api/v1/tasks';
    // Note: the API doesn't have a list endpoint for all tasks
    // This will need to be adapted to the actual API
    return await api('/api/v1/tasks');
  }

  // ---- Task Actions ----
  window.pauseTask = async function(id) {
    const r = await api('/api/v1/tasks/' + id + '/pause', { method: 'POST' });
    if (r) toast('任务已暂停: ' + id, 'success');
    loadDashboard();
  };

  window.resumeTask = async function(id) {
    const r = await api('/api/v1/tasks/' + id + '/resume', { method: 'POST' });
    if (r) toast('任务已继续: ' + id, 'success');
    loadDashboard();
  };

  window.retryTask = async function(id) {
    const r = await api('/api/v1/tasks/' + id + '/retry', { method: 'POST' });
    if (r) toast('重试任务已创建: ' + (r.task_id || id), 'success');
    loadDashboard();
  };

  window.showTaskDetail = async function(id) {
    const detail = document.getElementById('taskDetail');
    const content = document.getElementById('taskDetailContent');
    detail.style.display = 'block';

    const t = await api('/api/v1/tasks/' + id);
    if (!t) { content.innerHTML = '<p>加载失败</p>'; return; }

    const result = t.result || {};
    content.innerHTML = `
      <div class="detail-row"><div class="detail-label">ID</div><div class="detail-value"><code>${t.id}</code></div></div>
      <div class="detail-row"><div class="detail-label">类型</div><div class="detail-value">${t.type || '-'}</div></div>
      <div class="detail-row"><div class="detail-label">状态</div><div class="detail-value">${statusBadge(t.status)}</div></div>
      <div class="detail-row"><div class="detail-label">通过/总数</div><div class="detail-value">${result.passed_tests || 0} / ${result.total_tests || 0}</div></div>
      <div class="detail-row"><div class="detail-label">耗时</div><div class="detail-value">${result.execution_time ? result.execution_time.toFixed(2) + 's' : '-'}</div></div>
      <div class="detail-row"><div class="detail-label">错误</div><div class="detail-value">${t.error || result.error || '无'}</div></div>
      ${result.generated_code ? `<div class="detail-row"><div class="detail-label">生成代码</div><div class="detail-value"><div class="code-block">${escapeHtml(result.generated_code)}</div></div></div>` : ''}
      <div style="margin-top:16px">
        ${t.status === 'running' ? `<button class="btn btn-sm btn-outline" onclick="pauseTask('${t.id}')">⏸ 暂停</button>` : ''}
        ${t.status === 'paused' ? `<button class="btn btn-sm btn-primary" onclick="resumeTask('${t.id}')">▶ 继续</button>` : ''}
        ${t.status === 'failed' ? `<button class="btn btn-sm btn-outline" onclick="retryTask('${t.id}')">🔄 重试</button>` : ''}
        <button class="btn btn-sm btn-outline" onclick="loadBugDetail('${t.id}')">🐛 Bug 报告</button>
      </div>
    `;
  };

  window.loadBugDetail = async function(id) {
    const report = await api('/api/v1/tasks/' + id + '/bugs');
    if (report && report.bugs) {
      renderBugReport(report);
      showPage('bugs');
    }
  };

  // ---- Submit Form ----
  function initSubmitForm() {
    const form = document.getElementById('submitForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      let testCases = [];
      try {
        testCases = JSON.parse(fd.get('test_cases') || '[]');
      } catch (err) {
        toast('测试用例 JSON 格式错误', 'error');
        return;
      }

      const body = {
        agent_type: fd.get('agent_type'),
        model: fd.get('model'),
        api_key: fd.get('api_key'),
        base_url: fd.get('base_url') || undefined,
        task: {
          description: fd.get('description'),
          language: fd.get('language'),
          test_cases: testCases,
          difficulty: fd.get('difficulty'),
        },
      };

      const r = await api('/api/v1/agent/evaluate', {
        method: 'POST',
        body: JSON.stringify(body),
      });

      if (r && r.task_id) {
        toast('任务已提交: ' + r.task_id, 'success');
        form.reset();
        showPage('tasks');
      }
    });
  }

  // ---- Sandbox ----
  function initSandbox() {
    const runBtn = document.getElementById('sandboxRun');
    if (!runBtn) return;

    runBtn.addEventListener('click', async () => {
      const code = document.getElementById('sandboxCode').value;
      const lang = document.getElementById('sandboxLang').value;
      const timeout = parseInt(document.getElementById('sandboxTimeout').value) || 10;

      if (!code.trim()) { toast('请输入代码', 'error'); return; }

      runBtn.disabled = true;
      runBtn.textContent = '⏳ 执行中...';

      const r = await api('/api/v1/sandbox/execute', {
        method: 'POST',
        body: JSON.stringify({ code, language: lang, timeout }),
      });

      document.getElementById('sandboxStdout').textContent = r?.stdout || '';
      document.getElementById('sandboxStderr').textContent = r?.stderr || '';
      document.getElementById('sandboxStatus').textContent = r?.exit_code === 0 ? '✓ 成功' : '✗ 失败';
      document.getElementById('sandboxStatus').className = 'badge badge-' + (r?.exit_code === 0 ? 'completed' : 'failed');
      document.getElementById('sandboxMeta').textContent = [
        `Exit: ${r?.exit_code}`,
        r?.timed_out ? '⏱ 超时' : '',
        r?.memory_exceeded ? '💾 内存超限' : '',
        `${r?.execution_time?.toFixed(2) || 0}s`,
      ].filter(Boolean).join(' | ');

      runBtn.disabled = false;
      runBtn.textContent = '▶ 执行';
    });
  }

  // ---- Bug Detection ----
  function initBugAnalysis() {
    const btn = document.getElementById('bugAnalyze');
    if (!btn) return;

    btn.addEventListener('click', () => {
      const id = document.getElementById('bugTaskId').value.trim();
      if (id) loadBugReportForTask(id);
    });
  }

  async function loadBugReport() {
    // Auto-load from URL param or last selected
    const id = new URLSearchParams(location.search).get('task');
    if (id) loadBugReportForTask(id);
  }

  async function loadBugReportForTask(id) {
    const report = await api('/api/v1/tasks/' + id + '/bugs');
    if (report) renderBugReport(report);
    else toast('无法获取 Bug 报告', 'error');
  }

  function renderBugReport(report) {
    const container = document.getElementById('bugReport');
    if (!container) return;

    const summary = report.summary || {};
    container.innerHTML = `
      <div class="bug-summary">
        <div class="stat-card">
          <div class="stat-value">${summary.total_bugs || 0}</div>
          <div class="stat-label">Bug 总数</div>
        </div>
        <div class="stat-card accent-red">
          <div class="stat-value">${summary.high_severity || 0}</div>
          <div class="stat-label">高危</div>
        </div>
        <div class="stat-card accent-yellow">
          <div class="stat-value">${summary.medium_severity || 0}</div>
          <div class="stat-label">中危</div>
        </div>
        <div class="stat-card accent-blue">
          <div class="stat-value">${summary.low_severity || 0}</div>
          <div class="stat-label">低危</div>
        </div>
      </div>
      <div style="margin-bottom:12px;font-size:13px;color:var(--text-muted)">
        常见模式: <strong>${summary.common_pattern || 'none'}</strong>
      </div>
      ${(report.bugs || []).map(b => `
        <div class="bug-item">
          <div class="bug-item-header">
            <span class="bug-type">${escapeHtml(b.error_type)}</span>
            <span class="bug-severity ${b.severity}">${b.severity}</span>
            <span class="bug-confidence">置信度 ${(b.confidence * 100).toFixed(0)}%</span>
          </div>
          <div class="bug-desc">Test #${b.test_index}: ${escapeHtml(b.description)}</div>
          ${b.suggested_fix ? `<div class="bug-fix">💡 ${escapeHtml(b.suggested_fix)}</div>` : ''}
        </div>
      `).join('') || '<div class="empty-state">未检测到 Bug</div>'}
    `;
  }

  // ---- Utilities ----
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  // ---- Refresh ----
  document.getElementById('refreshBtn')?.addEventListener('click', () => {
    loadDashboard();
    toast('已刷新', 'info');
  });

  // ---- Init ----
  function init() {
    initNav();
    initSubmitForm();
    initSandbox();
    initBugAnalysis();
    showPage('dashboard');

    // Auto-refresh every 5s
    refreshInterval = setInterval(loadDashboard, 5000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
