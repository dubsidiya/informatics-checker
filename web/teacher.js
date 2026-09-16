const loginPanel = document.getElementById("login-panel");
const board = document.getElementById("board");
const stats = document.getElementById("stats");
const grid = document.getElementById("grid");
const attemptBox = document.getElementById("attempt");
const logout = document.getElementById("logout");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const pin = document.getElementById("pin");
const boardSearch = document.getElementById("board-search");
const boardTopic = document.getElementById("board-topic");
const boardCols = document.getElementById("board-cols");
const boardRefresh = document.getElementById("board-refresh");

let problems = [];
let summary = { students: [], total_attempts: 0, total_students: 0 };
let topicFilter = "все";
let colMode = "attempted";
let query = "";
let openCell = null;

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
  try {
    problems = await api("/api/problems");
  } catch {
    loginError.textContent = "Не удалось загрузить список задач.";
    loginError.classList.remove("hidden");
    showLogin();
    return;
  }
  fillTopicFilter();
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

function fillTopicFilter() {
  const topics = ["все", ...[...new Set(problems.map((item) => item.topic))]];
  boardTopic.innerHTML = topics.map((topic) => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`).join("");
  boardTopic.value = topicFilter;
}

function showLogin() {
  loginPanel.classList.remove("hidden");
  board.classList.add("hidden");
  logout.classList.add("hidden");
}

async function showBoard() {
  loginPanel.classList.add("hidden");
  board.classList.remove("hidden");
  logout.classList.remove("hidden");
  await loadSummary();
}

async function loadSummary() {
  summary = await api("/api/teacher/summary");
  renderStats();
  renderGrid();
}

function renderStats() {
  const attempted = new Set();
  for (const student of summary.students) {
    for (const id of Object.keys(student.problems || {})) attempted.add(id);
  }
  stats.innerHTML = `
    <article class="stat"><b>${summary.total_students}</b><span>учеников</span></article>
    <article class="stat"><b>${summary.total_attempts}</b><span>попыток</span></article>
    <article class="stat"><b>${attempted.size} / ${problems.length}</b><span>задач трогали</span></article>
  `;
}

function visibleProblems() {
  const attempted = new Set();
  for (const student of summary.students) {
    for (const id of Object.keys(student.problems || {})) attempted.add(id);
  }
  const q = query.trim().toLowerCase();
  const nameHits = q ? summary.students.filter((item) => item.name.toLowerCase().includes(q)) : [];
  return problems.filter((problem) => {
    if (topicFilter !== "все" && problem.topic !== topicFilter) return false;
    if (colMode === "attempted" && !attempted.has(problem.id)) return false;
    if (!q) return true;
    const titleHit = problem.title.toLowerCase().includes(q) || problem.id.toLowerCase().includes(q);
    if (titleHit) return true;
    if (nameHits.length) return true;
    return false;
  });
}

function visibleStudents() {
  const q = query.trim().toLowerCase();
  if (!q) return summary.students;
  const nameHits = summary.students.filter((item) => item.name.toLowerCase().includes(q));
  if (nameHits.length) return nameHits;
  return summary.students;
}

function renderGrid() {
  if (!summary.students.length) {
    grid.innerHTML = `<p class="muted">Пока никто не отправлял решения. Пусть ученики укажут имя и нажмут «Проверить».</p>`;
    return;
  }
  const cols = visibleProblems();
  const rowsData = visibleStudents();
  if (!cols.length) {
    grid.innerHTML = `<p class="muted">Нет задач в этом фильтре. Переключи «Все задачи» или сбрось поиск.</p>`;
    return;
  }
  const head = cols.map((problem) => `<th title="${escapeHtml(problem.title)}">${escapeHtml(problem.title)}</th>`).join("");
  const rows = rowsData.map((student) => {
    const cells = cols.map((problem) => {
      const cell = student.problems[problem.id];
      if (!cell) {
        return `<td class="cell empty">—</td>`;
      }
      const klass = cell.best_status === "ok" ? "ok" : cell.best_status === "syntax" ? "warn" : "bad";
      const label = cell.best_status === "ok" ? "сдано" : `${cell.passed}/${cell.total}`;
      const attemptId = cell.best_attempt_id || cell.attempt_id;
      return `<td class="cell ${klass}" data-student="${escapeHtml(student.name)}" data-problem="${problem.id}" data-id="${attemptId}">${label}<small>${cell.attempts} попыток</small></td>`;
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
  openCell = { student, problemId, attemptId };
  attemptBox.classList.remove("hidden");
  attemptBox.innerHTML = `<p class="muted">Загружаю попытку…</p>`;
  try {
    const [item, history] = await Promise.all([
      attemptId
        ? api(`/api/teacher/attempts/${attemptId}`)
        : api(`/api/teacher/latest?student=${encodeURIComponent(student)}&problem_id=${encodeURIComponent(problemId)}`),
      api(`/api/teacher/attempts?student=${encodeURIComponent(student)}&problem_id=${encodeURIComponent(problemId)}`),
    ]);
    const problem = problems.find((entry) => entry.id === item.problem_id);
    const currentId = String(item.id);
    const historyHtml = (history || []).map((entry) => {
      const klass = entry.status === "ok" ? "ok" : entry.status === "syntax" ? "warn" : "bad";
      const active = String(entry.id) === currentId ? " active" : "";
      return `<button type="button" class="history-item ${klass}${active}" data-id="${entry.id}" data-student="${escapeHtml(entry.student)}" data-problem="${entry.problem_id}">${when(entry.ts)} · ${entry.status === "ok" ? "сдано" : `${entry.passed}/${entry.total}`}</button>`;
    }).join("");
    attemptBox.innerHTML = `
      <div class="banner ${item.status === "ok" ? "ok" : item.status === "syntax" ? "warn" : "bad"}">
        ${escapeHtml(item.student)} · ${escapeHtml(problem ? problem.title : item.problem_id)} · ${escapeHtml(item.message)}
      </div>
      <p class="muted">${when(item.ts)} · тесты ${item.passed} / ${item.total}</p>
      <h3>История попыток</h3>
      <div class="history-list">${historyHtml || "<p class='muted'>Других попыток нет.</p>"}</div>
      <h3>Код</h3>
      <pre class="snippet">${escapeHtml(item.code || "")}</pre>
    `;
    attemptBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
  const button = event.target.closest("button.history-item[data-id]");
  if (!button) return;
  openAttempt(button.dataset.student, button.dataset.problem, button.dataset.id);
});

boardSearch.addEventListener("input", () => {
  query = boardSearch.value || "";
  renderGrid();
});

boardTopic.addEventListener("change", () => {
  topicFilter = boardTopic.value || "все";
  renderGrid();
});

boardCols.addEventListener("change", () => {
  colMode = boardCols.value || "attempted";
  renderGrid();
});

boardRefresh.addEventListener("click", async () => {
  boardRefresh.disabled = true;
  try {
    await loadSummary();
    if (openCell) {
      await openAttempt(openCell.student, openCell.problemId, openCell.attemptId);
    }
  } catch (error) {
    grid.innerHTML = `<div class="banner bad">${escapeHtml(error.message)}</div>`;
  } finally {
    boardRefresh.disabled = false;
  }
});

boot();
