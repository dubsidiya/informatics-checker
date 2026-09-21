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
const boardPeriod = document.getElementById("board-period");
const boardAuto = document.getElementById("board-auto");
const boardRefresh = document.getElementById("board-refresh");

let teacherCsrf = "";
let problems = [];
let summary = { students: [], total_attempts: 0, total_students: 0, stuck: [], topics: [], hard_tasks: [], inactive: [], exams: { live: [], recent: [] } };
let topicFilter = "все";
let colMode = "attempted";
let period = "all";
let query = "";
let openCell = null;
let refreshTimer = 0;

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

function inPeriod(ts) {
  if (period === "all") return true;
  if (!ts) return false;
  const now = Date.now() / 1000;
  if (period === "lesson") return now - ts <= 45 * 60;
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  return ts >= start.getTime() / 1000;
}

function readCookie(name) {
  const parts = document.cookie.split(";").map((item) => item.trim());
  for (const part of parts) {
    if (part.startsWith(`${name}=`)) return decodeURIComponent(part.slice(name.length + 1));
  }
  return "";
}

function csrfHeaders(extra) {
  const headers = Object.assign({ "Content-Type": "application/json" }, extra || {});
  const token = teacherCsrf || readCookie("teacher_csrf");
  if (token) headers["X-CSRF-Token"] = token;
  return headers;
}

function clearTeacherState() {
  teacherCsrf = "";
  summary = { students: [], total_attempts: 0, total_students: 0, stuck: [], topics: [], hard_tasks: [], inactive: [], exams: { live: [], recent: [] } };
  openCell = null;
  query = "";
  if (boardSearch) boardSearch.value = "";
  if (attemptBox) {
    attemptBox.classList.add("hidden");
    attemptBox.innerHTML = "";
  }
  if (grid) grid.innerHTML = "";
  if (stats) stats.innerHTML = "";
  const classroom = document.getElementById("classroom");
  if (classroom) classroom.innerHTML = "";
}

async function api(url, options) {
  const opts = options || {};
  if (opts.method && opts.method !== "GET") {
    opts.headers = csrfHeaders(opts.headers);
  }
  const response = await fetch(url, opts);
  if (response.status === 401) {
    stopAuto();
    clearTeacherState();
    showLogin();
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || "Ошибка запроса");
    error.status = response.status;
    throw error;
  }
  return data;
}

async function boot() {
  teacherCsrf = readCookie("teacher_csrf");
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
  stopAuto();
  loginPanel.classList.remove("hidden");
  board.classList.add("hidden");
  logout.classList.add("hidden");
}

async function showBoard() {
  loginPanel.classList.add("hidden");
  board.classList.remove("hidden");
  logout.classList.remove("hidden");
  await loadSummary();
  boardSearch.focus();
}

async function loadSummary() {
  summary = await api("/api/teacher/summary");
  renderStats();
  renderGrid();
}

function roster() {
  const q = query.trim().toLowerCase();
  let students = summary.students.filter((item) => inPeriod(item.last_ts));
  if (!q) return students;
  const nameHits = students.filter((item) => item.name.toLowerCase().includes(q));
  if (nameHits.length) return nameHits;
  return students;
}

function renderStats() {
  const students = roster();
  const attempted = new Set();
  let solved = 0;
  const topicIds = topicFilter === "все" ? [] : problems.filter((item) => item.topic === topicFilter).map((item) => item.id);
  let topicSolved = 0;
  for (const student of students) {
    solved += student.solved || 0;
    for (const id of Object.keys(student.problems || {})) attempted.add(id);
    if (topicIds.length) {
      topicSolved += topicIds.filter((id) => student.problems?.[id]?.best_status === "ok").length;
    }
  }
  const topicStat = topicIds.length
    ? `<article class="stat"><b>${topicSolved}</b><span>сдач по теме</span></article>`
    : `<article class="stat"><b>${attempted.size} / ${problems.length}</b><span>задач трогали</span></article>`;
  stats.innerHTML = `
    <article class="stat"><b>${students.length}</b><span>учеников в срезе</span></article>
    <article class="stat"><b>${solved}</b><span>сдач задач</span></article>
    ${topicStat}
    <article class="stat"><b>${summary.total_attempts}</b><span>попыток всего</span></article>
  `;
  renderAnalytics();
  renderClassroom();
}

function renderAnalytics() {
  const box = document.getElementById("analytics");
  if (!box) return;
  const topics = (summary.topics || []).filter((item) => item.attempts);
  const inactive = (summary.inactive || []).slice(0, 8);
  const hardTasks = (summary.hard_tasks || []).slice(0, 8);
  box.innerHTML = `
    <article class="classroom-card">
      <h3>Темы класса</h3>
      ${topics.length ? `<ul>${topics.slice(0, 8).map((item) => `<li><b>${escapeHtml(item.topic)}</b> · ${item.solved}/${item.attempted} сдано · ${item.success_rate}% успеха</li>`).join("")}</ul>` : `<p class="muted">Пока нет данных по темам.</p>`}
    </article>
    <article class="classroom-card">
      <h3>Самые сложные задачи</h3>
      ${hardTasks.length ? `<ul>${hardTasks.map((item) => `<li><button type="button" class="ghost-link" data-find-problem="${escapeHtml(item.problem_id)}">${escapeHtml(item.title)}</button> · ${item.success_rate}% успеха · ${item.fails} неудач</li>`).join("")}</ul>` : `<p class="muted">Пока недостаточно попыток.</p>`}
    </article>
    <article class="classroom-card">
      <h3>Нет активности 45+ минут</h3>
      ${inactive.length ? `<ul>${inactive.map((item) => `<li><button type="button" class="ghost-link" data-find="${escapeHtml(item.name)}">${escapeHtml(item.name)}</button></li>`).join("")}</ul>` : `<p class="muted">Все ученики активны.</p>`}
    </article>
  `;
}

function findStudentFrom(event) {
  const button = event.target.closest("[data-find]");
  if (!button) return;
  query = button.dataset.find || "";
  boardSearch.value = query;
  renderStats();
  renderGrid();
}

function findProblemFrom(event) {
  const button = event.target.closest("[data-find-problem]");
  if (!button) return;
  query = button.dataset.findProblem || "";
  boardSearch.value = query;
  boardCols.value = "all";
  colMode = "all";
  renderStats();
  renderGrid();
}

function visibleProblems() {
  const students = roster();
  const attempted = new Set();
  for (const student of students) {
    for (const id of Object.keys(student.problems || {})) attempted.add(id);
  }
  const q = query.trim().toLowerCase();
  const nameHits = q ? students.filter((item) => item.name.toLowerCase().includes(q)) : [];
  return problems.filter((problem) => {
    if (topicFilter !== "все" && problem.topic !== topicFilter) return false;
    if (colMode === "attempted" && !attempted.has(problem.id)) return false;
    if (colMode === "help" && !students.some((student) => {
      const cell = student.problems?.[problem.id];
      return cell && cell.best_status !== "ok";
    })) return false;
    if (!q) return true;
    const titleHit = problem.title.toLowerCase().includes(q) || problem.id.toLowerCase().includes(q);
    if (titleHit) return true;
    if (nameHits.length) return true;
    return false;
  });
}

function problemTitle(id) {
  return problems.find((item) => item.id === id)?.title || id;
}

function renderClassroom() {
  const box = document.getElementById("classroom");
  if (!box) return;
  const live = (summary.exams && summary.exams.live) || [];
  const recent = (summary.exams && summary.exams.recent) || [];
  const stuck = (summary.stuck || []).filter((item) => inPeriod(item.ts)).slice(0, 12);
  const liveHtml = live.length
    ? `<ul>${live.map((item) => `<li><button type="button" class="ghost-link" data-find="${escapeHtml(item.student)}">${escapeHtml(item.student)}</button> · ${escapeHtml(item.topic)} · ${item.solved}/${item.total}</li>`).join("")}</ul>`
    : `<p class="muted">Сейчас никто не пишет зачёт.</p>`;
  const stuckHtml = stuck.length
    ? `<ul>${stuck.map((item) => `<li><button type="button" class="ghost-link" data-find="${escapeHtml(item.student)}">${escapeHtml(item.student)}</button> · ${escapeHtml(problemTitle(item.problem_id))} · ${item.attempts} попыток, не сдано</li>`).join("")}</ul>`
    : `<p class="muted">Нет учеников с тремя и больше неудачами на одной задаче.</p>`;
  const recentHtml = recent.length
    ? `<p class="muted">${recent.slice(0, 6).map((item) => `${escapeHtml(item.student)}: ${item.solved}/${item.total} «${escapeHtml(item.topic)}»`).join(" · ")}</p>`
    : "";
  box.innerHTML = `
    <article class="classroom-card">
      <h3>Сейчас пишут зачёт</h3>
      ${liveHtml}
      ${recentHtml}
    </article>
    <article class="classroom-card">
      <h3>Кто застрял</h3>
      ${stuckHtml}
    </article>
  `;
}

function topicScore(student) {
  if (topicFilter === "все") return `${student.solved} сдано · ${student.attempts} попыток · ${when(student.last_ts)}`;
  const ids = problems.filter((item) => item.topic === topicFilter).map((item) => item.id);
  const done = ids.filter((id) => student.problems?.[id]?.best_status === "ok").length;
  return `${done}/${ids.length} по теме · ${student.attempts} попыток · ${when(student.last_ts)}`;
}

function renderGrid() {
  const rowsData = roster();
  if (!summary.students.length) {
    grid.innerHTML = `<p class="muted">Пока никто не отправлял решения. Пусть ученики укажут имя и нажмут «Проверить».</p>`;
    return;
  }
  if (!rowsData.length) {
    grid.innerHTML = `<p class="muted">В этом периоде никого нет. Переключи «Всё время», если журнал за сегодня пуст.</p>`;
    return;
  }
  const cols = visibleProblems();
  if (!cols.length) {
    grid.innerHTML = `<p class="muted">Нет задач в этом фильтре. Переключи «Все задачи» или сбрось поиск.</p>`;
    return;
  }
  const head = cols.map((problem) => `<th title="${escapeHtml(problem.title)}">${escapeHtml(problem.title)}</th>`).join("");
  const rows = rowsData.map((student) => {
    const cells = cols.map((problem) => {
      const cell = student.problems[problem.id];
      if (!cell || (colMode === "help" && cell.best_status === "ok")) {
        return `<td class="cell empty">—</td>`;
      }
      const klass = cell.best_status === "ok" ? "ok" : cell.best_status === "syntax" ? "warn" : "bad";
      const label = cell.best_status === "ok" ? "сдано" : `${cell.passed}/${cell.total}`;
      const attemptId = cell.best_attempt_id || cell.attempt_id;
      return `<td class="cell ${klass}" tabindex="0" role="button" data-student="${escapeHtml(student.name)}" data-problem="${problem.id}" data-id="${attemptId}">${label}<small>${cell.attempts} попыток</small></td>`;
    }).join("");
    return `<tr>
      <th class="name-col" tabindex="0" data-student="${escapeHtml(student.name)}" title="Нажми, чтобы найти этого ученика">${escapeHtml(student.name)}<small>${topicScore(student)}</small></th>
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
      <div class="editor-actions spacing">
        <button type="button" class="ghost-btn" data-copy-code="1">Копировать код</button>
      </div>
      <h3>Код</h3>
      <pre class="snippet" id="attempt-code">${escapeHtml(item.code || "")}</pre>
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
    const data = await api("/api/teacher/login", {
      method: "POST",
      body: JSON.stringify({ pin: pin.value }),
    });
    teacherCsrf = data.csrf || readCookie("teacher_csrf");
    pin.value = "";
    await showBoard();
  } catch (error) {
    loginError.textContent = error.message;
    loginError.classList.remove("hidden");
    pin.focus();
    pin.select();
  }
}

function stopAuto() {
  clearInterval(refreshTimer);
  refreshTimer = 0;
}

function startAuto() {
  stopAuto();
  refreshTimer = setInterval(() => {
    loadSummary().catch((error) => {
      if (importNote) {
        importNote.classList.remove("hidden");
        importNote.textContent = error.message || "Автообновление не удалось.";
      }
    });
  }, 12000);
}

loginForm.addEventListener("submit", doLogin);

logout.addEventListener("click", async () => {
  stopAuto();
  if (boardAuto) boardAuto.checked = false;
  try {
    await api("/api/teacher/logout", { method: "POST" });
  } catch {
    /* still leave */
  }
  clearTeacherState();
  showLogin();
});

grid.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const name = event.target.closest("th.name-col[data-student]");
  if (name) {
    event.preventDefault();
    query = name.dataset.student || "";
    boardSearch.value = query;
    renderStats();
    renderGrid();
    return;
  }
  const cell = event.target.closest("td.cell[data-student]");
  if (!cell) return;
  event.preventDefault();
  openAttempt(cell.dataset.student, cell.dataset.problem, cell.dataset.id);
});

grid.addEventListener("click", (event) => {
  const name = event.target.closest("th.name-col[data-student]");
  if (name) {
    query = name.dataset.student || "";
    boardSearch.value = query;
    renderStats();
    renderGrid();
    return;
  }
  const cell = event.target.closest("td.cell[data-student]");
  if (!cell) return;
  openAttempt(cell.dataset.student, cell.dataset.problem, cell.dataset.id);
});

attemptBox.addEventListener("click", async (event) => {
  if (event.target.closest("[data-copy-code]")) {
    const code = document.getElementById("attempt-code");
    try {
      await navigator.clipboard.writeText(code ? code.textContent : "");
      event.target.textContent = "Скопировано";
    } catch {
      event.target.textContent = "Не вышло";
    }
    return;
  }
  const button = event.target.closest("button.history-item[data-id]");
  if (!button) return;
  openAttempt(button.dataset.student, button.dataset.problem, button.dataset.id);
});

boardSearch.addEventListener("input", () => {
  query = boardSearch.value || "";
  renderStats();
  renderGrid();
});

boardTopic.addEventListener("change", () => {
  topicFilter = boardTopic.value || "все";
  renderStats();
  renderGrid();
});

boardCols.addEventListener("change", () => {
  colMode = boardCols.value || "attempted";
  renderGrid();
});

boardPeriod.addEventListener("change", () => {
  period = boardPeriod.value || "all";
  renderStats();
  renderGrid();
});

if (boardAuto) {
  boardAuto.addEventListener("change", () => {
    if (boardAuto.checked) startAuto();
    else stopAuto();
  });
}

document.addEventListener("click", findStudentFrom);
document.addEventListener("click", findProblemFrom);

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

const classroom = document.getElementById("classroom");
if (classroom) {
  classroom.addEventListener("click", (event) => {
    const button = event.target.closest("[data-find]");
    if (!button) return;
    query = button.dataset.find || "";
    boardSearch.value = query;
    renderStats();
    renderGrid();
  });
}

const importInput = document.getElementById("board-import");
const importNote = document.getElementById("import-note");
if (importInput) {
  importInput.addEventListener("change", async () => {
    const file = importInput.files && importInput.files[0];
    importInput.value = "";
    if (!file) return;
    const text = await file.text();
    const format = /\.json$/i.test(file.name) ? "json" : "csv";
    try {
      const result = await api("/api/teacher/import", {
        method: "POST",
        body: JSON.stringify({ format, text }),
      });
      await loadSummary();
      if (importNote) {
        importNote.classList.remove("hidden");
        importNote.textContent = `Вернул журнал: добавлено ${result.inserted}, пропущено ${result.skipped}.`;
      }
    } catch (error) {
      if (importNote) {
        importNote.classList.remove("hidden");
        importNote.textContent = error.message || "Не удалось вернуть журнал.";
      }
    }
  });
}

async function downloadExport(path, filename) {
  const response = await fetch(path, { method: "POST", headers: csrfHeaders() });
  if (response.status === 401) {
    stopAuto();
    clearTeacherState();
    showLogin();
    throw new Error("Нужен вход учителя");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Не удалось скачать файл");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function bindExport(id, path, filename) {
  const button = document.getElementById(id);
  if (!button) return;
  button.addEventListener("click", async () => {
    try {
      await downloadExport(path, filename);
    } catch (error) {
      if (importNote) {
        importNote.classList.remove("hidden");
        importNote.textContent = error.message || "Не удалось скачать файл.";
      }
    }
  });
}

bindExport("export-csv", "/api/teacher/export.csv", "attempts.csv");
bindExport("export-json", "/api/teacher/export.json", "attempts.json");
bindExport("backup-json", "/api/teacher/backup.json", "backup.json");

boot();
