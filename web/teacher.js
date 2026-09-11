const loginPanel = document.getElementById("login-panel");
const board = document.getElementById("board");
const stats = document.getElementById("stats");
const grid = document.getElementById("grid");
const attemptBox = document.getElementById("attempt");
const logout = document.getElementById("logout");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const pin = document.getElementById("pin");

let problems = [];

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
  problems = await api("/api/problems");
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

function showLogin() {
  loginPanel.classList.remove("hidden");
  board.classList.add("hidden");
  logout.classList.add("hidden");
}

async function showBoard() {
  loginPanel.classList.add("hidden");
  board.classList.remove("hidden");
  logout.classList.remove("hidden");
  const summary = await api("/api/teacher/summary");
  stats.innerHTML = `
    <article class="stat"><b>${summary.total_students}</b><span>учеников</span></article>
    <article class="stat"><b>${summary.total_attempts}</b><span>попыток</span></article>
    <article class="stat"><b>${problems.length}</b><span>задач в банке</span></article>
  `;
  if (!summary.students.length) {
    grid.innerHTML = `<p class="muted">Пока никто не отправлял решения. Пусть ученики укажут имя и нажмут «Проверить».</p>`;
    return;
  }
  const head = problems.map((problem) => `<th title="${escapeHtml(problem.title)}">${escapeHtml(problem.title)}</th>`).join("");
  const rows = summary.students.map((student) => {
    const cells = problems.map((problem) => {
      const cell = student.problems[problem.id];
      if (!cell) {
        return `<td class="cell empty">—</td>`;
      }
      const klass = cell.best_status === "ok" ? "ok" : cell.best_status === "syntax" ? "warn" : "bad";
      const label = cell.best_status === "ok" ? "сдано" : `${cell.passed}/${cell.total}`;
      return `<td class="cell ${klass}" data-student="${escapeHtml(student.name)}" data-problem="${problem.id}" data-id="${cell.attempt_id}">${label}<small>${cell.attempts} попыток</small></td>`;
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
  attemptBox.classList.remove("hidden");
  attemptBox.innerHTML = `<p class="muted">Загружаю попытку…</p>`;
  try {
    const item = attemptId
      ? await api(`/api/teacher/attempts/${attemptId}`)
      : await api(`/api/teacher/latest?student=${encodeURIComponent(student)}&problem_id=${encodeURIComponent(problemId)}`);
    const problem = problems.find((entry) => entry.id === item.problem_id);
    attemptBox.innerHTML = `
      <div class="banner ${item.status === "ok" ? "ok" : item.status === "syntax" ? "warn" : "bad"}">
        ${escapeHtml(item.student)} · ${escapeHtml(problem ? problem.title : item.problem_id)} · ${escapeHtml(item.message)}
      </div>
      <p class="muted">${when(item.ts)} · тесты ${item.passed} / ${item.total}</p>
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
loginForm.querySelector("button").addEventListener("click", doLogin);

logout.addEventListener("click", async () => {
  await api("/api/teacher/logout", { method: "POST" });
  showLogin();
});

grid.addEventListener("click", (event) => {
  const cell = event.target.closest("td.cell[data-student]");
  if (!cell) return;
  openAttempt(cell.dataset.student, cell.dataset.problem, cell.dataset.id);
});

boot();
