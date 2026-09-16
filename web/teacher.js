const loginPanel = document.getElementById("login-panel");
const board = document.getElementById("board");
const stats = document.getElementById("stats");
const grid = document.getElementById("grid");
const attemptBox = document.getElementById("attempt");
const logout = document.getElementById("logout");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const pin = document.getElementById("pin");
const topicFilter = document.getElementById("topic-filter");
const studentSearch = document.getElementById("student-search");
const onlyAttempted = document.getElementById("only-attempted");
const autoRefresh = document.getElementById("auto-refresh");
const refreshBtn = document.getElementById("refresh");
const updated = document.getElementById("updated");

let problems = [];
let summary = { students: [], total_attempts: 0, total_students: 0 };
let refreshTimer = 0;
let selected = { student: "", problemId: "", attemptId: "" };

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function when(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}

function shortTitle(title) {
  const cut = String(title || "").split(" — ")[0];
  return cut.length > 18 ? `${cut.slice(0, 16)}…` : cut;
}

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || "Ошибка запроса");
    error.status = response.status;
    throw error;
  }
  return data;
}

async function boot() {
  problems = await api("/api/problems");
  fillTopics();
  try {
    const me = await api("/api/teacher/me");
    if (me.ok) {
      await showBoard();
      return;
    }
  } catch {
    showLogin();
    return;
  }
  showLogin();
}

function fillTopics() {
  if (!topicFilter) return;
  const topics = ["все", ...[...new Set(problems.map((item) => item.topic))]];
  topicFilter.innerHTML = topics.map((topic) => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`).join("");
}

function showLogin() {
  loginPanel.classList.remove("hidden");
  board.classList.add("hidden");
  logout.classList.add("hidden");
  stopRefresh();
}

async function showBoard() {
  loginPanel.classList.add("hidden");
  board.classList.remove("hidden");
  logout.classList.remove("hidden");
  await renderBoard();
  scheduleRefresh();
}

function scheduleRefresh() {
  stopRefresh();
  if (!autoRefresh || !autoRefresh.checked) return;
  refreshTimer = window.setInterval(() => {
    if (board.classList.contains("hidden")) return;
    renderBoard().catch(() => {});
  }, 8000);
}

function stopRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = 0;
  }
}

async function renderBoard() {
  summary = await api("/api/teacher/summary");
  paintBoard();
}

function paintBoard() {
  const solvedAll = summary.students.reduce((sum, student) => sum + student.solved, 0);
  stats.innerHTML = `
    <article class="stat"><b>${summary.total_students}</b><span>учеников</span></article>
    <article class="stat"><b>${summary.total_attempts}</b><span>попыток</span></article>
    <article class="stat"><b>${solvedAll}</b><span>сдано задач</span></article>
  `;
  if (updated) {
    updated.textContent = `обновлено ${new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
  }
  if (!summary.students.length) {
    grid.innerHTML = `<p class="muted">Пока никто не отправлял решения. Пусть ученики укажут имя и нажмут «Проверить».</p>`;
    return;
  }

  const topic = topicFilter ? topicFilter.value : "все";
  const query = (studentSearch ? studentSearch.value : "").trim().toLowerCase();
  const attemptedIds = new Set();
  for (const student of summary.students) {
    for (const id of Object.keys(student.problems || {})) attemptedIds.add(id);
  }
  const columns = problems.filter((problem) => {
    const topicOk = topic === "все" || problem.topic === topic;
    const attemptedOk = !onlyAttempted || !onlyAttempted.checked || attemptedIds.has(problem.id);
    return topicOk && attemptedOk;
  });
  const students = summary.students.filter((student) => !query || student.name.toLowerCase().includes(query));

  if (!columns.length) {
    grid.innerHTML = `<p class="muted">Нет колонок в этом фильтре. Сними «только задачи с попытками» или выбери другую тему.</p>`;
    return;
  }
  if (!students.length) {
    grid.innerHTML = `<p class="muted">Нет учеников с таким именем.</p>`;
    return;
  }

  const head = columns.map((problem) => (
    `<th class="problem-head" title="${escapeHtml(problem.title)}">${escapeHtml(shortTitle(problem.title))}</th>`
  )).join("");
  const rows = students.map((student) => {
    const cells = columns.map((problem) => {
      const cell = student.problems[problem.id];
      if (!cell) {
        return `<td class="cell empty">—</td>`;
      }
      const klass = cell.best_status === "ok" ? "ok" : cell.best_status === "syntax" ? "warn" : "bad";
      const label = cell.best_status === "ok" ? "сдано" : `${cell.passed}/${cell.total}`;
      const active = selected.student === student.name && selected.problemId === problem.id ? " active" : "";
      return `<td class="cell ${klass}${active}" data-student="${escapeHtml(student.name)}" data-problem="${problem.id}" data-id="${cell.attempt_id}">${label}<small>${cell.attempts} попыток</small></td>`;
    }).join("");
    return `<tr>
      <th class="name-col">${escapeHtml(student.name)}<small>${student.solved} сдано · ${student.attempts} попыток · ${when(student.last_ts)}</small></th>
      ${cells}
    </tr>`;
  }).join("");
  grid.innerHTML = `
    <table class="board-table">
      <thead><tr><th>Ученик</th>${head}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function openAttempt(student, problemId, attemptId) {
  selected = { student, problemId, attemptId: String(attemptId || "") };
  attemptBox.classList.remove("hidden");
  attemptBox.innerHTML = `<p class="muted">Загружаю попытку…</p>`;
  try {
    const history = await api(`/api/teacher/attempts?student=${encodeURIComponent(student)}&problem_id=${encodeURIComponent(problemId)}`);
    const chosenId = attemptId || (history[0] && history[0].id);
    const item = chosenId
      ? await api(`/api/teacher/attempts/${chosenId}`)
      : await api(`/api/teacher/latest?student=${encodeURIComponent(student)}&problem_id=${encodeURIComponent(problemId)}`);
    selected.attemptId = String(item.id);
    const problem = problems.find((entry) => entry.id === item.problem_id);
    const historyHtml = history.map((entry) => {
      const klass = entry.status === "ok" ? "ok" : entry.status === "syntax" ? "warn" : "bad";
      const active = String(entry.id) === String(item.id) ? " active" : "";
      const label = entry.status === "ok" ? "сдано" : `${entry.passed}/${entry.total}`;
      return `<button type="button" class="${klass}${active}" data-student="${escapeHtml(student)}" data-problem="${escapeHtml(problemId)}" data-id="${entry.id}">
        <span class="pill ${entry.status === "ok" ? "OK" : "WA"}">${escapeHtml(label)}</span>
        ${escapeHtml(when(entry.ts))} · ${escapeHtml(entry.message)}
      </button>`;
    }).join("");
    attemptBox.innerHTML = `
      <div class="banner ${item.status === "ok" ? "ok" : item.status === "syntax" ? "warn" : "bad"}">
        ${escapeHtml(item.student)} · ${escapeHtml(problem ? problem.title : item.problem_id)} · ${escapeHtml(item.message)}
      </div>
      <p class="muted">${when(item.ts)} · тесты ${item.passed} / ${item.total}</p>
      <h3>Попытки</h3>
      <div class="attempt-history">${historyHtml || "<p class='muted'>Истории нет.</p>"}</div>
      <h3>Код</h3>
      <pre class="snippet">${escapeHtml(item.code || "")}</pre>
    `;
    attemptBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    paintBoard();
  } catch (error) {
    attemptBox.innerHTML = `<div class="banner bad">${escapeHtml(error.message)}</div>`;
  }
}

async function doLogin(event) {
  if (event) event.preventDefault();
  loginError.classList.add("hidden");
  try {
    await api("/api/teacher/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: pin.value }),
    });
    await showBoard();
  } catch (error) {
    loginError.textContent = error.message;
    loginError.classList.remove("hidden");
  }
}

loginForm.addEventListener("submit", doLogin);

logout.addEventListener("click", async () => {
  await api("/api/teacher/logout", { method: "POST" });
  showLogin();
});

grid.addEventListener("click", (event) => {
  const cell = event.target.closest("td.cell[data-student]");
  if (!cell) return;
  openAttempt(cell.dataset.student, cell.dataset.problem, cell.dataset.id);
});

attemptBox.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-student]");
  if (!button) return;
  openAttempt(button.dataset.student, button.dataset.problem, button.dataset.id);
});

if (topicFilter) topicFilter.addEventListener("change", paintBoard);
if (studentSearch) studentSearch.addEventListener("input", paintBoard);
if (onlyAttempted) onlyAttempted.addEventListener("change", paintBoard);
if (autoRefresh) {
  autoRefresh.addEventListener("change", () => {
    if (autoRefresh.checked) scheduleRefresh();
    else stopRefresh();
  });
}
if (refreshBtn) refreshBtn.addEventListener("click", () => renderBoard().catch(() => {}));

boot();
