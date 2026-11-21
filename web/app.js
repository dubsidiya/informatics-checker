const els = {
  list: document.getElementById("task-list"),
  count: document.getElementById("task-count"),
  topics: document.getElementById("topic-filters"),
  levels: document.getElementById("level-filters"),
  level: document.getElementById("level"),
  title: document.getElementById("title"),
  statement: document.getElementById("statement"),
  input: document.getElementById("input-format"),
  output: document.getElementById("output-format"),
  examples: document.getElementById("examples"),
  fileBox: document.getElementById("file-box"),
  mistakeGuide: document.getElementById("mistake-guide"),
  readHelp: document.getElementById("read-help"),
  code: document.getElementById("code"),
  run: document.getElementById("run"),
  result: document.getElementById("result"),
  student: document.getElementById("student"),
  full: document.getElementById("editor-full"),
  cursor: document.getElementById("editor-cursor"),
  sig: document.getElementById("editor-sig"),
  keys: document.getElementById("editor-keys"),
  search: document.getElementById("task-search"),
  hideSolved: document.getElementById("hide-solved"),
  reset: document.getElementById("code-reset"),
  copy: document.getElementById("code-copy"),
  next: document.getElementById("next-task"),
  progress: document.getElementById("topic-progress"),
  progressLabel: document.getElementById("topic-progress-label"),
  progressBar: document.getElementById("topic-progress-bar"),
  examBar: document.getElementById("exam-bar"),
  examHeading: document.getElementById("exam-heading"),
  examStatus: document.getElementById("exam-status"),
  examExit: document.getElementById("exam-exit"),
  examSkip: document.getElementById("exam-skip"),
  startExam: document.getElementById("start-exam"),
  repeatErrors: document.getElementById("repeat-errors"),
  onboard: document.getElementById("onboard"),
  onboardOk: document.getElementById("onboard-ok"),
  coach: document.getElementById("coach"),
  coachTitle: document.getElementById("coach-title"),
  coachWhat: document.getElementById("coach-what"),
  coachSteps: document.getElementById("coach-steps"),
  coachWatch: document.getElementById("coach-watch"),
  progressCard: document.getElementById("progress-card"),
  progressHeading: document.getElementById("progress-heading"),
  progressSummary: document.getElementById("progress-summary"),
  progressRecommendations: document.getElementById("progress-recommendations"),
  exportProgress: document.getElementById("export-progress"),
};

const LEVELS = ["все", "старт", "средне", "сложно"];
const PATH_TOPICS = [
  "ввод-вывод",
  "условия",
  "циклы",
  "числа",
  "строки",
  "списки",
  "поиск",
  "на пути к ЕГЭ",
];
let problems = [];
let topicCards = [];
let currentId = null;
let currentProblem = null;
let topicFilter = "все";
let levelFilter = "все";
let searchQuery = "";
let hideSolved = false;
let repeatErrorsMode = false;
let editor = null;
let openGen = 0;
let progressTimer = 0;
let examMode = false;
let examTopic = "";
let examIds = [];
let examSkip = new Set();
let problemStats = {};
let solutionViewsByProblem = {};
let studentCsrf = "";
let solvedIds = new Set();
let sessionName = "";
let checkController = null;
let checkGeneration = 0;

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");
const PYTHON_WORDS = [
  "False", "None", "True", "and", "as", "assert", "break", "class", "continue",
  "def", "del", "elif", "else", "except", "finally", "for", "from", "global",
  "if", "import", "in", "is", "lambda", "not", "or", "pass", "raise", "return",
  "try", "while", "with", "yield",
  "abs", "all", "any", "bin", "bool", "chr", "dict", "enumerate", "filter",
  "float", "format", "hex", "input", "int", "isinstance", "len", "list", "map",
  "max", "min", "open", "ord", "pow", "print", "range", "reversed", "round",
  "set", "sorted", "str", "sum", "tuple", "zip",
  "itertools", "product", "permutations", "combinations",
  "functools", "lru_cache", "ipaddress", "ip_address", "ip_network",
  "collections", "Counter", "defaultdict", "string", "ascii_uppercase", "math",
];
const KEYWORDS = new Set([
  "False", "None", "True", "and", "as", "assert", "break", "class", "continue",
  "def", "del", "elif", "else", "except", "finally", "for", "from", "global",
  "if", "import", "in", "is", "lambda", "not", "or", "pass", "raise", "return",
  "try", "while", "with", "yield",
]);
const LIST_METHODS = ["append", "clear", "copy", "count", "extend", "index", "insert", "pop", "remove", "reverse", "sort"];
const STR_METHODS = [
  "count", "endswith", "find", "format", "index", "isalnum", "isalpha", "isdigit",
  "join", "lower", "lstrip", "replace", "rfind", "rjust", "rstrip", "split",
  "startswith", "strip", "upper", "zfill",
];
const DICT_METHODS = ["get", "items", "keys", "pop", "setdefault", "update", "values"];
const SET_METHODS = ["add", "discard", "intersection", "remove", "union", "update"];
const FILE_METHODS = ["close", "read", "readline", "readlines"];
const ALL_METHODS = [...new Set([...LIST_METHODS, ...STR_METHODS, ...DICT_METHODS, ...SET_METHODS, ...FILE_METHODS])];
const SNIPPETS = [
  { label: "for", snippet: "for i in range(|):\n    " },
  { label: "for-enum", snippet: "for i, x in enumerate(|):\n    " },
  { label: "while", snippet: "while |:\n    " },
  { label: "if", snippet: "if |:\n    " },
  { label: "elif", snippet: "elif |:\n    " },
  { label: "else", snippet: "else:\n    |" },
  { label: "def", snippet: "def |():\n    " },
  { label: "try", snippet: "try:\n    |\nexcept Exception:\n    " },
  { label: "with", snippet: "with open(|) as f:\n    " },
  { label: "print", snippet: "print(|)" },
  { label: "input", snippet: "input()" },
  { label: "int-input", snippet: "int(input())" },
  { label: "map-input", snippet: "list(map(int, input().split()))" },
  { label: "open", snippet: "open(|)" },
  { label: "lru", snippet: "@lru_cache(None)\ndef f(|):\n    " },
];
const SIGNATURES = {
  print: "print(*values, sep=' ', end='\\n')",
  input: "input(prompt='')",
  range: "range(stop)  или  range(start, stop, step=1)",
  open: "open(file, mode='r')",
  int: "int(x, base=10)",
  enumerate: "enumerate(iterable, start=0)",
  round: "round(number, ndigits=None)",
  sorted: "sorted(iterable, reverse=False)",
  map: "map(function, iterable)",
  zip: "zip(*iterables)",
  max: "max(iterable)  или  max(a, b, ...)",
  min: "min(iterable)  или  min(a, b, ...)",
  sum: "sum(iterable, start=0)",
  len: "len(obj)",
  abs: "abs(x)",
  pow: "pow(base, exp, mod=None)",
  lru_cache: "lru_cache(maxsize=None)",
  product: "product(*iterables, repeat=1)",
  permutations: "permutations(iterable, r=None)",
  combinations: "combinations(iterable, r)",
  split: "str.split(sep=None)",
  replace: "str.replace(old, new)",
  append: "list.append(x)",
  ip_network: "ip_network(address, strict=True)",
  ip_address: "ip_address(address)",
};

function readCookie(name) {
  const parts = document.cookie.split(";").map((item) => item.trim());
  for (const part of parts) {
    if (part.startsWith(`${name}=`)) {
      return decodeURIComponent(part.slice(name.length + 1));
    }
  }
  return "";
}

function csrfHeaders(extra) {
  const headers = Object.assign({ "Content-Type": "application/json" }, extra || {});
  const token = studentCsrf || readCookie("student_csrf");
  if (token) headers["X-CSRF-Token"] = token;
  return headers;
}

function studentName() {
  return (els.student.value || "").trim();
}

function solvedSet() {
  return solvedIds;
}

function markSolved(id) {
  solvedIds.add(id);
}

function codeKey(id, name) {
  return `draft:${name ?? (studentName() || "_")}:${id}`;
}

function loadSavedCode(id) {
  return localStorage.getItem(codeKey(id))
    || localStorage.getItem(codeKey(id, "_"))
    || "";
}

function getCode() {
  return editor ? editor.getValue() : els.code.value;
}

function setCode(value) {
  if (editor) {
    editor.setValue(value);
    editor.refresh();
  } else {
    els.code.value = value;
  }
}

function persistCode() {
  if (!currentId) return;
  localStorage.setItem(codeKey(currentId), getCode());
}

function starterFor(problem) {
  if (examMode) {
    return `# ${problem.title}\n# Напиши решение с нуля, как на экзамене.\n\n`;
  }
  const tags = problem.tags || [];
  const name = problem.files && problem.files[0] ? problem.files[0].name : "";
  if (tags.includes("ege3") && name) {
    return `# ${problem.title}\nfor line in open('${name}'):\n    fields = line.strip().split(';')\n\n`;
  }
  if (tags.includes("ege10") && name) {
    return `# ${problem.title}\ntext = open('${name}').read()\n\n`;
  }
  if (tags.includes("ege9") && name) {
    if (name.endsWith(".txt")) {
      return `# ${problem.title}\nfor line in open('${name}'):\n    a = [int(x) for x in line.split()]\n\n`;
    }
    return `# ${problem.title}\nfor line in open('${name}'):\n    a = [int(x) for x in line.replace(',', ';').split(';') if x.strip()]\n\n`;
  }
  if (name) {
    return `# ${problem.title}\ndata = [int(x) for x in open('${name}')]\n\n`;
  }
  if (tags.includes("ege8")) {
    return `# ${problem.title}\nfrom itertools import product\n\n`;
  }
  if (tags.includes("ege13")) {
    return `# ${problem.title}\nfrom ipaddress import ip_address, ip_network\n\n`;
  }
  if (tags.includes("ege16") || tags.includes("ege23")) {
    return `# ${problem.title}\nfrom functools import lru_cache\n\n`;
  }
  return `# ${problem.title}\n# прочитай ввод и выведи только ответ\n\n`;
}

function resultKey(id) {
  return `result:${studentName() || "_"}:${id}`;
}

function saveResult(id, data) {
  try {
    // Keep the last check after a reload; the server remains authoritative.
    localStorage.setItem(resultKey(id), JSON.stringify(data));
  } catch {
    /* quota */
  }
}

function loadResult(id) {
  try {
    return JSON.parse(localStorage.getItem(resultKey(id)) || "null");
  } catch {
    return null;
  }
}

function renderProgress() {
  if (!els.progress || !els.progressLabel || !els.progressBar) return;
  const topicNow = examMode ? examTopic : topicFilter;
  if (!examMode && topicNow === "все") {
    els.progress.classList.add("hidden");
    els.progress.setAttribute("aria-hidden", "true");
    renderExamBar();
    return;
  }
  const pool = examMode
    ? examProblems()
    : problems.filter((item) => item.topic === topicNow);
  if (!pool.length) {
    els.progress.classList.add("hidden");
    els.progress.setAttribute("aria-hidden", "true");
    return;
  }
  const solved = solvedSet();
  const done = pool.filter((item) => solved.has(item.id)).length;
  els.progress.classList.remove("hidden");
  els.progress.setAttribute("aria-hidden", "false");
  els.progressLabel.textContent = examMode
    ? `Зачёт: сдано ${done} из ${pool.length}`
    : `Сдано ${done} из ${pool.length}`;
  const pct = Math.round((done / pool.length) * 100);
  els.progressBar.style.width = `${pct}%`;
  const meter = document.getElementById("topic-progress-meter");
  if (meter) meter.setAttribute("aria-valuenow", String(pct));
  renderExamBar();
}

async function ensureSession() {
  const name = studentName();
  if (!name) return false;
  if (sessionName === name && (studentCsrf || readCookie("student_csrf"))) return true;
  const response = await fetch("/api/student/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ student: name }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Не удалось сохранить имя");
  }
  sessionName = data.student || name;
  studentCsrf = data.csrf || readCookie("student_csrf");
  if (data.student) els.student.value = data.student;
  localStorage.setItem("student", sessionName);
  return true;
}

function applyProgress(data) {
  solvedIds = new Set(data.solved || []);
  problemStats = data.problems || {};
  solutionViewsByProblem = data.solution_views || {};
  renderLearningProgress();
}

function exportMyProgress() {
  const name = studentName() || "ученик";
  const drafts = {};
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key && key.startsWith("draft:")) {
      const code = localStorage.getItem(key) || "";
      if (code.trim()) drafts[key] = code;
    }
  }
  const payload = {
    format: "informatics-checker-progress",
    exported_at: new Date().toISOString(),
    student: name,
    solved: [...solvedIds].sort(),
    attempts: Object.keys(problemStats).length,
    problems: problemStats,
    drafts,
  };
  const body = JSON.stringify(payload, null, 2);
  const blob = new Blob([body], { type: "application/json; charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const safe = name.replace(/[^\p{L}\p{N}]+/gu, "_").slice(0, 40) || "student";
  const link = document.createElement("a");
  link.href = url;
  link.download = `progress-${safe}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function renderLearningProgress() {
  if (!els.progressCard || !studentName()) return;
  const attempted = Object.keys(problemStats).length;
  const stuck = problems
    .filter((item) => !solvedIds.has(item.id) && (problemStats[item.id]?.fails || 0) >= 3)
    .sort((a, b) => (problemStats[b.id]?.fails || 0) - (problemStats[a.id]?.fails || 0));
  const topic = currentProblem?.topic || (topicFilter !== "все" ? topicFilter : "");
  const recommendations = problems
    .filter((item) => !solvedIds.has(item.id) && item.id !== currentId)
    .sort((a, b) => {
      const score = (item) => (item.topic === topic ? 100 : 0) + (item.level === currentProblem?.level ? 20 : 0)
        + Math.min(30, (problemStats[item.id]?.fails || 0) * 5);
      return score(b) - score(a);
    })
    .slice(0, 3);
  els.progressCard.classList.remove("hidden");
  els.progressHeading.textContent = stuck.length ? "Разберём то, где было сложно" : "Продолжим обучение?";
  els.progressSummary.textContent = `Сдано ${solvedIds.size} задач · начато ${attempted}.`;
  const items = [...stuck.slice(0, 1), ...recommendations]
    .filter((item, index, all) => all.findIndex((other) => other.id === item.id) === index)
    .slice(0, 3);
  els.progressRecommendations.innerHTML = items.length
    ? items.map((item) => `<button type="button" class="progress-task" data-progress-task="${escapeAttr(item.id)}">
        <strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.topic)} · ${escapeHtml(item.level)}${problemStats[item.id]?.fails ? ` · ${problemStats[item.id].fails} ошибок` : ""}</small>
      </button>`).join("")
    : `<span class="muted">Все доступные задачи решены — отличный результат.</span>`;
}

async function syncProgress() {
  try {
    if (!studentName() && !readCookie("student")) {
      renderList();
      renderProgress();
      return;
    }
    const response = await fetch("/api/progress");
    if (response.status === 401) {
      solvedIds = new Set();
      problemStats = {};
      renderList();
      renderProgress();
      return;
    }
    if (!response.ok) return;
    applyProgress(await response.json());
    renderList();
    renderProgress();
    pingExamProgress();
  } catch {
    renderProgress();
  }
}

function scheduleProgressSync() {
  clearTimeout(progressTimer);
  progressTimer = setTimeout(syncProgress, 400);
}

function examKey() {
  return `exam-draft:${studentName() || "_"}`;
}

let examCache = null;
let examCacheKey = "";

function examProblems() {
  // Memoize: examIds/examTopic/problems change rarely, but this is called 13+ times per render.
  const key = `${examIds.length}:${examTopic}:${problems.length}`;
  if (examCache && examCacheKey === key) return examCache;
  examCacheKey = key;
  examCache = examIds.length
    ? examIds.map((id) => problems.find((item) => item.id === id)).filter(Boolean)
    : problems.filter((item) => item.topic === examTopic);
  return examCache;
}

function examCounts() {
  const items = examProblems();
  const solved = solvedSet();
  const done = items.filter((item) => solved.has(item.id)).length;
  return { items, done, skipped: examSkip.size };
}

function renderCoach(topic) {
  if (!els.coach) return;
  const name = topic && topic !== "все" ? topic : (currentProblem && currentProblem.topic);
  const card = topicCards.find((item) => item.topic === name);
  if (!card) {
    els.coach.classList.add("hidden");
    return;
  }
  els.coach.classList.remove("hidden");
  if (els.coachTitle) els.coachTitle.textContent = card.title;
  if (els.coachWhat) els.coachWhat.textContent = card.what;
  if (els.coachSteps) {
    els.coachSteps.innerHTML = (card.steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("");
  }
  if (els.coachWatch) els.coachWatch.textContent = card.watch || "";
  if (examMode) els.coach.open = true;
}

function renderOnboard() {
  if (!els.onboard) return;
  const seen = localStorage.getItem("onboard") === "1";
  els.onboard.classList.toggle("hidden", seen || examMode);
}

function applyExam(exam) {
  if (!exam || exam.status !== "live") return false;
  examMode = true;
  examTopic = exam.topic;
  topicFilter = exam.topic;
  examIds = Array.isArray(exam.problem_ids) ? exam.problem_ids : [];
  examSkip = new Set(Array.isArray(exam.skipped_ids) ? exam.skipped_ids : []);
  examCache = null;
  return true;
}

async function pingExam(action, extra) {
  if (!studentCsrf && !readCookie("student_csrf")) return null;
  try {
    const response = await fetch("/api/exam", {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify(Object.assign({ action, topic: examTopic }, extra || {})),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function pingExamProgress() {
  if (!examMode) return;
  const { items, done, skipped } = examCounts();
  const finished = items.length && done >= items.length;
  pingExam(finished ? "finish" : "progress", {
    solved: done,
    skipped,
    total: items.length,
  });
}

function renderExamBar() {
  if (!els.examBar) return;
  if (!examMode) {
    els.examBar.classList.add("hidden");
    document.body.classList.remove("exam-on");
    return;
  }
  els.examBar.classList.remove("hidden");
  document.body.classList.add("exam-on");
  const { items, done } = examCounts();
  const idx = items.findIndex((item) => item.id === currentId);
  if (els.examHeading) els.examHeading.textContent = examTopic;
  if (els.examStatus) {
    els.examStatus.textContent = items.length && done === items.length
      ? `Зачёт закрыт: сдано ${done} из ${items.length}`
      : `Задача ${idx >= 0 ? idx + 1 : "—"} из ${items.length} · сдано ${done} · пропущено ${examSkip.size}`;
  }
}

async function startExam() {
  try {
    if (!await ensureSession()) {
      markNameState();
      els.student.focus();
      els.result.classList.remove("hidden");
      els.result.innerHTML = `<div class="banner warn">Напиши имя сверху — учитель увидит, кто пишет зачёт.</div>`;
      return;
    }
  } catch (error) {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner warn">${escapeHtml(error.message)}</div>`;
    return;
  }
  const topic = topicFilter !== "все" ? topicFilter : (currentProblem && currentProblem.topic);
  if (!topic || topic === "все") {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner warn">Сначала выбери тему слева сверху. Экзамен — 8 задач одной темы, как зачёт.</div>`;
    return;
  }
  const exam = await pingExam("start", { topic });
  if (!exam || !applyExam(exam)) {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner warn">Не удалось начать зачёт. Обнови страницу.</div>`;
    return;
  }
  hideSolved = false;
  if (els.hideSolved) els.hideSolved.checked = false;
  renderCoach(topic);
  renderChips();
  renderList();
  const solved = solvedSet();
  const items = examProblems();
  const next = items.find((item) => !solved.has(item.id) && !examSkip.has(item.id)) || items[0];
  if (next) openProblem(next.id, true);
  renderExamBar();
  renderOnboard();
}

function stopExam() {
  if (examMode) {
    const { items, done, skipped } = examCounts();
    pingExam("leave", { solved: done, skipped, total: items.length });
  }
  examMode = false;
  examTopic = "";
  examIds = [];
  examSkip = new Set();
  examCache = null;
  localStorage.removeItem(examKey());
  els.result.classList.add("hidden");
  els.result.innerHTML = "";
  renderExamBar();
  renderChips();
  renderList();
  renderCoach(topicFilter);
  renderOnboard();
}

function skipExamTask() {
  if (!examMode || !currentId) return;
  examSkip.add(currentId);
  pingExam("skip", { problem_id: currentId });
  const solved = solvedSet();
  const items = examProblems();
  const later = items.slice(items.findIndex((item) => item.id === currentId) + 1);
  const next = later.find((item) => !solved.has(item.id) && !examSkip.has(item.id))
    || items.find((item) => !solved.has(item.id) && !examSkip.has(item.id) && item.id !== currentId)
    || later[0];
  if (next) openProblem(next.id, true);
  renderList();
  renderExamBar();
}


function pathProblems() {
  const rank = new Map(PATH_TOPICS.map((topic, index) => [topic, index]));
  return problems
    .filter((item) => rank.has(item.topic))
    .sort((a, b) => rank.get(a.topic) - rank.get(b.topic));
}

function pathFrontier() {
  return pathProblems().find((item) => !solvedSet().has(item.id)) || null;
}

function pathAllows(id) {
  const items = pathProblems();
  const known = items.find((item) => item.id === id);
  if (!known) return false;
  if (solvedSet().has(id)) return true;
  const frontier = items.find((item) => !solvedSet().has(item.id));
  return !!frontier && frontier.id === id;
}

function pathVisible() {
  const items = pathProblems();
  const solved = solvedSet();
  const frontier = items.findIndex((item) => !solved.has(item.id));
  const currentIndex = items.findIndex((item) => item.id === currentId);
  let end = frontier === -1 ? items.length : frontier + 1;
  // The next unsolved stays closed until «Следующая нерешённая» opens it.
  if (currentIndex >= 0 && (frontier === -1 || frontier > currentIndex)) {
    end = currentIndex + 1;
  }
  const shown = items.slice(0, end);
  const q = searchQuery.trim().toLowerCase();
  return shown.filter((item) => {
    const searchOk = !q || item.title.toLowerCase().includes(q) || item.id.toLowerCase().includes(q);
    const solvedOk = !hideSolved || !solved.has(item.id);
    const errorsOk = !repeatErrorsMode || ((problemStats[item.id]?.fails || 0) > 0 && !solved.has(item.id));
    return searchOk && solvedOk && errorsOk;
  });
}

function filteredProblems() {
  const q = searchQuery.trim().toLowerCase();
  const solved = solvedSet();
  const pool = examMode ? examProblems() : problems;
  const examTopicNow = examMode ? examTopic : topicFilter;
  return pool.filter((item) => {
    const topicOk = examMode || examTopicNow === "все" || item.topic === examTopicNow;
    const levelOk = examMode || levelFilter === "все" || item.level === levelFilter;
    const searchOk = !q
      || item.title.toLowerCase().includes(q)
      || item.id.toLowerCase().includes(q)
      || (item.topic || "").toLowerCase().includes(q);
    const solvedOk = !hideSolved || !solved.has(item.id);
    const errorsOk = !repeatErrorsMode || ((problemStats[item.id]?.fails || 0) > 0 && !solved.has(item.id));
    return topicOk && levelOk && searchOk && solvedOk && errorsOk;
  });
}

function renderChips() {
  const topics = examMode
    ? [examTopic]
    : ["все", ...[...new Set(problems.map((item) => item.topic))]];
  const activeTopic = examMode ? examTopic : topicFilter;
  els.topics.innerHTML = topics.map((topic) => `
    <button type="button" data-topic="${escapeAttr(topic)}" aria-pressed="${topic === activeTopic}" class="${topic === activeTopic ? "active" : ""}">${escapeHtml(topic)}</button>
  `).join("");
  if (els.levels) {
    els.levels.innerHTML = LEVELS.map((level) => `
      <button type="button" data-level="${escapeAttr(level)}" aria-pressed="${level === levelFilter}" class="${level === levelFilter ? "active" : ""}">${escapeHtml(level)}</button>
    `).join("");
  }
  if (els.startExam) {
    els.startExam.textContent = examMode ? "Идёт зачёт" : "Начать зачёт · 8 задач";
    els.startExam.disabled = examMode;
    els.startExam.setAttribute("aria-pressed", String(examMode));
  }
}

function renderList() {
  const items = filteredProblems();
  const solved = solvedSet();
  els.count.textContent = `${items.length} · сдано ${items.filter((item) => solved.has(item.id)).length}`;
  renderProgress();
  els.list.innerHTML = "";
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.id = item.id;
    button.setAttribute("aria-pressed", String(item.id === currentId));
    if (item.id === currentId) button.setAttribute("aria-current", "true");
    button.className = [
      item.id === currentId ? "active" : "",
      examSkip.has(item.id) ? "skipped" : "",
      !solved.has(item.id) && (problemStats[item.id]?.fails || 0) >= 3 ? "stuck" : "",
    ].filter(Boolean).join(" ");
    const fails = problemStats[item.id]?.fails || 0;
    const mark = solved.has(item.id) ? "<i>✓</i>" : examSkip.has(item.id) ? "<i>~</i>" : "";
    const authorMark = item.author_created ? " · тренировка" : "";
    const extra = `${authorMark}${fails && !solved.has(item.id) ? ` · ${fails} попыток` : ""}`;
    button.innerHTML = `
      <span class="task-title">${mark}${escapeHtml(item.title)}</span>
      <small>${escapeHtml(item.topic)} · ${escapeHtml(item.level)}${extra}</small>
    `;
    button.addEventListener("click", () => openProblem(item.id, true));
    els.list.appendChild(button);
  }
  if (!items.length) {
    els.list.innerHTML = `<p class="muted">Нет задач в этом фильтре.</p>`;
  }
}

async function boot() {
  els.student.value = localStorage.getItem("student") || "";
  studentCsrf = readCookie("student_csrf");
  markNameState();
  setupEditor();
  try {
    const [problemRes, topicRes] = await Promise.all([
      fetch("/api/problems"),
      fetch("/api/topics"),
    ]);
    if (!problemRes.ok) throw new Error("bad");
    problems = await problemRes.json();
    if (topicRes.ok) topicCards = await topicRes.json();
  } catch {
    els.title.textContent = "Не удалось загрузить задачи";
    els.statement.textContent = "Обнови страницу. Если снова ошибка — сервер проверяльщика недоступен.";
    return;
  }
  let me = null;
  try {
    const meRes = await fetch("/api/student/me");
    if (meRes.ok) me = await meRes.json();
  } catch {
    me = null;
  }
  if (me && me.ok) {
    sessionName = me.student || "";
    els.student.value = sessionName;
    localStorage.setItem("student", sessionName);
    studentCsrf = studentCsrf || readCookie("student_csrf");
    applyProgress(me.progress || {});
    applyExam(me.exam);
  }
  renderOnboard();
  renderChips();
  renderProgress();
  renderCoach(examMode ? examTopic : topicFilter);
  if (!me || !me.ok) await syncProgress();
  const fromHash = decodeURIComponent((location.hash || "").replace(/^#/, ""));
  let start = problems.some((item) => item.id === fromHash) ? fromHash : problems[0]?.id;
  if (examMode) {
    const solved = solvedSet();
    const items = examProblems();
    const hashOk = fromHash && items.some((item) => item.id === fromHash);
    start = hashOk
      ? fromHash
      : (items.find((item) => !solved.has(item.id)) || items[0] || {}).id || start;
  }
  if (start) {
    await openProblem(start, false);
  } else {
    renderList();
  }
}

function pickCompletion(cm) {
  const active = cm.state.completionActive;
  if (active && active.widget && typeof active.widget.pick === "function") {
    active.widget.pick();
    return true;
  }
  return false;
}

function insertSnippet(cm, data, completion) {
  const from = completion.from || data.from;
  const to = completion.to || data.to;
  const raw = completion.snippet;
  const mark = raw.indexOf("|");
  const text = raw.replace("|", "");
  cm.replaceRange(text, from, to);
  const pos = cm.posFromIndex(cm.indexFromPos(from) + (mark < 0 ? text.length : mark));
  cm.setCursor(pos);
}

function hintItem(text, className, extra) {
  return Object.assign({ text, displayText: text, className }, extra || {});
}

function pythonHint(cm, options) {
  const auto = !!(options && options.pythonAuto);
  const cursor = cm.getCursor();
  const token = cm.getTokenAt(cursor);
  const line = cm.getLine(cursor.line).slice(0, cursor.ch);
  const afterDot = /\.\s*[\w]*$/.test(line) && !/open\(\s*['"][^'"]*$/.test(line);
  let start = token.start;
  let prefix = token.string || "";
  if (afterDot) {
    const match = line.match(/\.(\w*)$/);
    prefix = match ? match[1] : "";
    start = cursor.ch - prefix.length;
  } else if (!/^[\w.]+$/.test(prefix)) {
    prefix = "";
    start = cursor.ch;
  } else {
    prefix = prefix.slice(0, cursor.ch - token.start);
  }

  const lower = prefix.toLowerCase();
  const from = CodeMirror.Pos(cursor.line, start);
  const list = [];
  const seen = new Set();

  function add(text, className, extra) {
    if (!text || seen.has(text) || (lower && !text.toLowerCase().startsWith(lower)) || text === prefix) return;
    seen.add(text);
    list.push(hintItem(text, className, extra));
  }

  if (/open\(\s*['"][^'"]*$/.test(line)) {
    const names = (currentProblem && currentProblem.files || []).map((file) => file.name);
    prefix = line.split(/['"]/).pop() || "";
    start = cursor.ch - prefix.length;
    const extras = [];
    const alias = fileAlias(currentProblem);
    if (alias) extras.push(alias);
    for (const name of names.concat(extras)) add(name, "hint-file");
    if (!list.length) return;
    return { list, from: CodeMirror.Pos(cursor.line, start), to: cursor };
  }

  if (afterDot) {
    const owner = (line.match(/([\w.\]]+)\.\w*$/) || ["", ""])[1];
    let methods = ALL_METHODS;
    if (/^(a|arr|nums|data|row|line_vals)$/.test(owner) || /\[:?-?1?\]$/.test(owner)) methods = LIST_METHODS;
    else if (/^(s|t|line|word|text|name)$/.test(owner)) methods = STR_METHODS;
    else if (/^(d|mp)$/.test(owner)) methods = DICT_METHODS;
    else if (/^(st|seen)$/.test(owner)) methods = SET_METHODS;
    else if (/^(f|fin|file)$/.test(owner) || /open\(/.test(owner)) methods = FILE_METHODS;
    for (const method of methods) add(method, "hint-method");
    if (!list.length) return;
    return { list, from, to: cursor };
  }

  if (/from\s+itertools\s+import\s+[\w,\s]*$/.test(line)) {
    for (const name of ["product", "permutations", "combinations", "combinations_with_replacement"]) add(name);
  } else if (/from\s+functools\s+import\s+[\w,\s]*$/.test(line)) {
    add("lru_cache");
  } else if (/from\s+ipaddress\s+import\s+[\w,\s]*$/.test(line)) {
    for (const name of ["ip_address", "ip_network", "ip_interface"]) add(name);
  } else if (/from\s+collections\s+import\s+[\w,\s]*$/.test(line)) {
    for (const name of ["Counter", "defaultdict"]) add(name);
  } else if (/^\s*import\s+[\w.]*$/.test(line)) {
    for (const name of ["itertools", "functools", "ipaddress", "collections", "string", "math"]) add(name);
  } else if (token.type !== "string" && token.type !== "comment") {
    if (auto && prefix.length < 3) {
      if (!list.length) return;
      return { list, from, to: cursor };
    }
    if (!auto) {
      for (const item of SNIPPETS) {
        if (lower && !item.label.toLowerCase().startsWith(lower) && !item.snippet.toLowerCase().startsWith(lower)) continue;
        list.push({
          text: item.snippet.replace("|", ""),
          displayText: item.label,
          className: "hint-snippet",
          snippet: item.snippet,
          hint: insertSnippet,
        });
        seen.add(item.label);
      }
    }
    for (const word of PYTHON_WORDS) add(word, KEYWORDS.has(word) ? "hint-keyword" : "");
    const words = cm.getValue().match(/[A-Za-z_][A-Za-z0-9_]*/g) || [];
    for (const word of words) {
      if (word.length > 1) add(word);
    }
  }

  if (!list.length) return;
  return { list, from, to: cursor };
}

function smartTab(cm) {
  if (pickCompletion(cm)) return;
  if (cm.somethingSelected()) {
    cm.indentSelection("add");
    return;
  }
  const cursor = cm.getCursor();
  const left = cm.getLine(cursor.line).slice(0, cursor.ch).trim();
  if (left) {
    const hit = SNIPPETS.find((item) => item.label === left);
    if (hit) {
      insertSnippet(cm, { from: { line: cursor.line, ch: cursor.ch - left.length }, to: cursor }, hit);
      return;
    }
  }
  cm.replaceSelection(" ".repeat(4 - (cursor.ch % 4) || 4), "end");
}

function smartBackspace(cm) {
  if (cm.somethingSelected()) return CodeMirror.Pass;
  const cursor = cm.getCursor();
  if (cursor.ch === 0) return CodeMirror.Pass;
  const before = cm.getLine(cursor.line).slice(0, cursor.ch);
  if (!/^ +$/.test(before) || before.length < 4) return CodeMirror.Pass;
  const n = before.length % 4 === 0 ? 4 : before.length % 4;
  cm.replaceRange("", { line: cursor.line, ch: cursor.ch - n }, cursor);
}

function pythonEnter(cm) {
  if (pickCompletion(cm)) return;
  if (cm.somethingSelected()) {
    cm.execCommand("newlineAndIndent");
    return;
  }
  const cursor = cm.getCursor();
  const line = cm.getLine(cursor.line);
  const left = line.slice(0, cursor.ch);
  const right = line.slice(cursor.ch);
  const pairs = { "(": ")", "[": "]", "{": "}" };
  const open = left.slice(-1);
  if (pairs[open] && right.startsWith(pairs[open])) {
    const pad = (left.match(/^ +/) || [""])[0];
    cm.replaceSelection(`\n${pad}    \n${pad}`, "end");
    cm.setCursor({ line: cursor.line + 1, ch: pad.length + 4 });
    return;
  }
  const indentMore = /:\s*(#.*)?$/.test(left);
  const indentLess = /^(return|break|continue|pass|raise)\b/.test(left.trim());
  const prevPad = (left.match(/^ +/) || [""])[0];
  cm.execCommand("newlineAndIndent");
  if (indentMore) {
    const now = cm.getCursor();
    const pad = (cm.getLine(now.line).match(/^ +/) || [""])[0];
    if (pad.length <= prevPad.length) {
      cm.replaceSelection("    ", "end");
    }
  } else if (indentLess) {
    const now = cm.getCursor();
    const pad = (cm.getLine(now.line).match(/^ +/) || [""])[0];
    if (pad.length >= 4) {
      cm.replaceRange(pad.slice(0, -4), { line: now.line, ch: 0 }, { line: now.line, ch: pad.length });
    }
  }
}

function duplicateLine(cm) {
  cm.operation(() => {
    if (cm.somethingSelected()) {
      const selected = cm.getSelection();
      cm.replaceSelection(selected + selected, "around");
      return;
    }
    const cursor = cm.getCursor();
    const line = cm.getLine(cursor.line);
    cm.replaceRange(`\n${line}`, { line: cursor.line, ch: line.length });
    cm.setCursor({ line: cursor.line + 1, ch: cursor.ch });
  });
}

function moveLines(cm, dir) {
  const selections = cm.listSelections();
  const from = Math.min(...selections.map((item) => Math.min(item.anchor.line, item.head.line)));
  const to = Math.max(...selections.map((item) => Math.max(item.anchor.line, item.head.line)));
  if (from + dir < 0 || to + dir >= cm.lineCount()) return;
  const block = [];
  for (let line = from; line <= to; line += 1) block.push(cm.getLine(line));
  cm.operation(() => {
    if (dir > 0) {
      const next = cm.getLine(to + 1);
      cm.replaceRange(`${next}\n${block.join("\n")}`, { line: from, ch: 0 }, { line: to + 1, ch: next.length });
    } else {
      const prev = cm.getLine(from - 1);
      cm.replaceRange(`${block.join("\n")}\n${prev}`, { line: from - 1, ch: 0 }, { line: to, ch: cm.getLine(to).length });
    }
    const head = selections[0].head;
    const anchor = selections[0].anchor;
    cm.setSelection(
      { line: anchor.line + dir, ch: anchor.ch },
      { line: head.line + dir, ch: head.ch },
    );
  });
}

function insertLineAfter(cm) {
  const cursor = cm.getCursor();
  const line = cm.getLine(cursor.line);
  const indent = (line.match(/^\s*/) || [""])[0];
  cm.replaceRange(`\n${indent}`, { line: cursor.line, ch: line.length });
  cm.setCursor({ line: cursor.line + 1, ch: indent.length });
}

function selectNextOccurrence(cm) {
  const selected = cm.getSelection();
  if (!selected) {
    const word = cm.findWordAt(cm.getCursor());
    cm.setSelection(word.anchor, word.head);
    return;
  }
  let cursor = cm.getSearchCursor(selected, cm.getCursor("to"));
  if (!cursor.findNext()) {
    cursor = cm.getSearchCursor(selected, { line: 0, ch: 0 });
    if (!cursor.findNext()) return;
  }
  cm.addSelection(cursor.from(), cursor.to());
}

let lintMarks = [];
let lintTimer = 0;

function lintBrackets(cm) {
  lintMarks.forEach((mark) => mark.clear());
  lintMarks = [];
  const stack = [];
  const closers = { ")": "(", "]": "[", "}": "{" };
  for (let line = 0; line < cm.lineCount(); line += 1) {
    for (const tok of cm.getLineTokens(line)) {
      if (tok.type && /string|comment/.test(tok.type)) continue;
      for (let i = 0; i < tok.string.length; i += 1) {
        const ch = tok.string[i];
        const pos = { line, ch: tok.start + i };
        if ("([{".includes(ch)) stack.push({ ch, pos });
        else if (closers[ch]) {
          if (!stack.length || stack[stack.length - 1].ch !== closers[ch]) {
            lintMarks.push(cm.markText(pos, { line, ch: pos.ch + 1 }, { className: "cm-python-error", title: "Лишняя скобка" }));
          } else {
            stack.pop();
          }
        }
      }
    }
  }
  for (const item of stack) {
    lintMarks.push(cm.markText(item.pos, { line: item.pos.line, ch: item.pos.ch + 1 }, { className: "cm-python-error", title: "Скобка не закрыта" }));
  }
}

function callNameAtCursor(cm) {
  const cursor = cm.getCursor();
  const left = cm.getLine(cursor.line).slice(0, cursor.ch);
  const depth = [];
  for (let i = left.length - 1; i >= 0; i -= 1) {
    const ch = left[i];
    if (ch === ")") depth.push(ch);
    else if (ch === "(") {
      if (depth.length) depth.pop();
      else {
        const name = left.slice(0, i).match(/([A-Za-z_][\w]*)\s*$/);
        return name ? name[1] : "";
      }
    }
  }
  return "";
}

function updateStatus(cm) {
  const cur = cm.getCursor();
  if (els.cursor) els.cursor.textContent = `стр. ${cur.line + 1}, кол. ${cur.ch + 1}`;
  if (els.sig) els.sig.textContent = SIGNATURES[callNameAtCursor(cm)] || "";
}

function toggleEditorFull() {
  document.body.classList.toggle("editor-full");
  if (els.full) {
    els.full.textContent = document.body.classList.contains("editor-full") ? "Свернуть" : "На весь экран";
  }
  setTimeout(() => editor && editor.refresh(), 40);
}

function fillShortcutHelp() {
  if (!els.keys) return;
  const list = els.keys.querySelector("ul");
  if (!list) return;
  const mod = IS_MAC ? "⌘" : "Ctrl";
  const rows = [
    [IS_MAC ? "Ctrl + Space / Alt + Space" : "Ctrl + Space", "подсказки"],
    ["Tab / Shift+Tab", "принять шаблон или отступ"],
    [`${mod} + /`, "комментарий"],
    [`${mod} + D`, "дублировать"],
    [IS_MAC ? "⌘ + Shift + K" : "Ctrl + Y", "удалить строку"],
    ["Alt + ↑ / ↓", "сдвинуть строку"],
    [`${mod} + F`, "поиск"],
    [IS_MAC ? "⌥⌘F" : "Ctrl + H", "замена"],
    [`${mod} + L`, "перейти к строке"],
    ["Alt + J", "выделить следующее такое же"],
    ["Alt + клик", "несколько курсоров"],
    [`${mod} + Enter`, "проверить"],
  ];
  list.innerHTML = rows.map(([keys, label]) => `<li><kbd>${keys}</kbd> — ${label}</li>`).join("");
}

function setupEditor() {
  fillShortcutHelp();
  if (!window.CodeMirror || !els.code) {
    if (els.code) els.code.addEventListener("input", persistCode);
    return;
  }
  if (window.CodeMirror.registerHelper) {
    window.CodeMirror.registerHelper("hint", "python", pythonHint);
  }
  try {
  editor = window.CodeMirror.fromTextArea(els.code, {
    mode: { name: "python", version: 3 },
    theme: "material",
    inputStyle: "contenteditable",
    spellcheck: false,
    autocorrect: false,
    autocapitalize: false,
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: true,
    matchBrackets: true,
    autoCloseBrackets: true,
    styleActiveLine: true,
    foldGutter: true,
    scrollPastEnd: true,
    gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
    highlightSelectionMatches: { minChars: 2 },
    hintOptions: { hint: pythonHint, completeSingle: false, alignWithWord: true, extraKeys: { Tab: pickCompletion, Enter: pickCompletion } },
    extraKeys: {
      Tab: smartTab,
      "Shift-Tab": "indentLess",
      Backspace: smartBackspace,
      Enter: pythonEnter,
      "Ctrl-Space": "autocomplete",
      "Alt-Space": "autocomplete",
      "Ctrl-/": "toggleComment",
      "Cmd-/": "toggleComment",
      "Ctrl-D": duplicateLine,
      "Cmd-D": duplicateLine,
      "Ctrl-Y": "deleteLine",
      "Cmd-Shift-K": "deleteLine",
      "Alt-Up": (cm) => moveLines(cm, -1),
      "Alt-Down": (cm) => moveLines(cm, 1),
      "Shift-Enter": insertLineAfter,
      "Ctrl-F": "findPersistent",
      "Cmd-F": "findPersistent",
      "Ctrl-H": "replace",
      "Cmd-Alt-F": "replace",
      "Ctrl-L": "jumpToLine",
      "Cmd-L": "jumpToLine",
      "Alt-J": selectNextOccurrence,
      "Ctrl-Enter": check,
      "Cmd-Enter": check,
      F11: toggleEditorFull,
    },
    configureMouse(_cm, _repeat, event) {
      if (event.altKey) return { addNew: true };
    },
  });
  const wrap = editor.getWrapperElement();
  wrap.style.clipPath = "none";
  wrap.addEventListener("mousedown", () => editor.focus());
  editor.setOption("readOnly", false);
  editor.on("change", (cm) => {
    persistCode();
    clearTimeout(lintTimer);
    lintTimer = setTimeout(() => lintBrackets(cm), 280);
    updateStatus(cm);
  });
  editor.on("cursorActivity", updateStatus);
  editor.on("inputRead", (cm, change) => {
    if (cm.state.completionActive) return;
    const typed = change.text[0] || "";
    if (typed !== "." && !/[A-Za-z_]/.test(typed)) return;
    const token = cm.getTokenAt(cm.getCursor());
    if (token.type === "comment") return;
    if (typed !== "." && (token.string || "").length < 3 && token.type !== "string") return;
    cm.showHint({ completeSingle: false, pythonAuto: true, hint: pythonHint });
  });
  if (els.full) els.full.addEventListener("click", toggleEditorFull);
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("editor-full")) {
      toggleEditorFull();
    }
  });
  setTimeout(() => {
    editor.refresh();
    updateStatus(editor);
  }, 40);
  } catch (err) {
    console.error(err);
    editor = null;
    els.code.style.display = "block";
    els.code.addEventListener("input", persistCode);
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = "Редактор с подсветкой не загрузился — можно писать в этом поле.";
    els.code.insertAdjacentElement("beforebegin", note);
  }
}

async function openProblem(id, updateHash) {
  if (currentId && currentId !== id) {
    persistCode();
  }
  if (checkController) {
    checkController.abort();
    checkController = null;
  }
  checkGeneration += 1;
  const gen = ++openGen;
  currentId = id;
  if (updateHash) {
    history.replaceState(null, "", `#${id}`);
  }
  renderList();
  els.title.textContent = "Загрузка…";
  els.statement.textContent = "";
  els.result.classList.add("hidden");
  els.result.innerHTML = "";
  try {
    const response = await fetch(`/api/problems/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error("missing");
    const problem = await response.json();
    if (gen !== openGen) return;
    currentProblem = problem;
    els.level.textContent = `${problem.topic} · ${problem.level}`;
    renderCoach(problem.topic);
    els.title.textContent = problem.title;
    revealStatement();
    els.statement.textContent = problem.statement;
    const oldProvenance = document.querySelector(".problem-provenance");
    if (oldProvenance) oldProvenance.remove();
    const guide = readingGuide(problem);
    if (els.readHelp) {
      const noInput = (problem.input_format || "").toLowerCase().includes("ввода нет");
      const tags = new Set(problem.tags || []);
      if (noInput && !tags.has("ip_restore")) {
        els.readHelp.classList.add("hidden");
        els.readHelp.innerHTML = "";
      } else {
        els.readHelp.classList.remove("hidden");
        els.readHelp.innerHTML = `
          <h3>${escapeHtml(guide.title)}</h3>
          <p>${escapeHtml(guide.text)}</p>
          <pre>${escapeHtml(guide.code)}</pre>
        `;
      }
    }
    if (problem.files && problem.files[0]) {
      const name = problem.files[0].name;
      els.fileBox.classList.remove("hidden");
      const alias = fileAlias(problem);
      const same = !alias || alias === name;
      const how = same
        ? `<code>open('${escapeHtml(name)}')</code>`
        : `<code>open('${escapeHtml(name)}')</code> или <code>open('${escapeHtml(alias)}')</code>`;
      els.fileBox.innerHTML = `К задаче приложен <a href="/api/problems/${encodeURIComponent(problem.id)}/file">${escapeHtml(name)}</a>. ${how} его откроет.`;
    } else if (els.fileBox) {
      els.fileBox.classList.add("hidden");
      els.fileBox.innerHTML = "";
    }
    els.input.textContent = problem.input_format;
    els.output.textContent = problem.output_format;
    els.examples.innerHTML = (problem.examples || []).map((example) => `
      <div class="example">
        <div><strong>вход</strong>\n${escapeHtml(example.stdin)}</div>
        <div><strong>выход</strong>\n${escapeHtml(example.stdout)}</div>
      </div>
    `).join("") || `<p class="muted">Для этой задачи отдельный пример ввода не показан — смотри условие.</p>`;
    if (problem.fast_path && els.coach) {
      const fast = document.createElement("p");
      fast.className = "coach-fast-path";
      fast.innerHTML = `<strong>Быстрый путь:</strong> ${escapeHtml(problem.fast_path)}`;
      const oldFast = els.coach.querySelector(".coach-fast-path");
      if (oldFast) oldFast.remove();
      els.coach.appendChild(fast);
    }
    if (els.mistakeGuide) {
      const items = (problem.mistake_hints || []).slice(0, 3);
      els.mistakeGuide.innerHTML = items.length
        ? `<h3 id="mistake-guide-title">Типичные ошибки именно здесь</h3><ul>${items.map((item) => `<li><b>${escapeHtml(item.title || "Ошибка")}</b><span>${escapeHtml(item.detail || "Сверь шаги решения с условием.")}</span></li>`).join("")}</ul>`
        : "";
    }
    const saved = loadSavedCode(id);
    setCode(saved && saved.trim() ? saved : starterFor(problem));
    const previous = loadResult(id);
    if (previous) {
      if (previous.status === "solution_viewed" && previous.solution) {
        renderSolution(previous.solution, { scroll: false });
      } else {
        if (previous.status !== "ok" && (problemStats[id]?.fails || 0) >= 10) {
          previous.solution_available = true;
        }
        renderResult(previous);
      }
    } else if ((problemStats[id]?.fails || 0) >= 10) {
      const priorViews = Number(solutionViewsByProblem[id] || 0);
      els.result.classList.remove("hidden");
      els.result.innerHTML = `
        <div class="banner warn">По этой задаче уже ${problemStats[id].fails} неудачных попыток.${priorViews ? " Разбор уже открывали ранее." : ""}</div>
        <button type="button" class="solution-button" data-view-solution="1">Посмотреть подробное решение</button>
      `;
    } else {
      els.result.classList.add("hidden");
    }
    if (editor) {
      editor.getWrapperElement().classList.remove("syntax-mark");
    } else {
      els.code.classList.remove("syntax-mark");
    }
  } catch {
    if (gen !== openGen) return;
    els.title.textContent = "Не удалось открыть задачу";
    els.statement.textContent = "Обнови страницу или выбери другую задачу из списка.";
  }
}

async function check() {
  if (!currentId) return;
  const requestGeneration = ++checkGeneration;
  // Capture before any session/focus work.  Focusing the name field or
  // replacing the result must not choose a new page position in another
  // browser engine.
  const checkPagePosition = capturePagePosition();
  persistCode();
  try {
    if (!await ensureSession()) {
      markNameState();
      els.student.focus();
      els.result.classList.remove("hidden");
      els.result.innerHTML = `<div class="banner warn">Напиши своё имя сверху, чтобы учитель увидел работу.</div>`;
      return;
    }
  } catch (error) {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner warn">${escapeHtml(error.message)}</div>`;
    return;
  }
  els.run.disabled = true;
  els.run.textContent = "Проверяю…";
  const controller = new AbortController();
  checkController = controller;
  const timeout = setTimeout(() => controller.abort(), 35_000);
  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: csrfHeaders(),
      signal: controller.signal,
      body: JSON.stringify({
        problem_id: currentId,
        code: getCode(),
      }),
    });
    const data = await response.json();
    if (requestGeneration !== checkGeneration) return;
    if (!response.ok) {
      throw new Error(data.detail || "Ошибка проверки");
    }
    if (data.status === "ok") {
      markSolved(currentId);
      examSkip.delete(currentId);
      localStorage.removeItem(ladderKey());
      renderList();
      renderProgress();
      pingExamProgress();
    } else {
      data.tries = sameErrorTries(data);
    }
    saveResult(currentId, data);
    renderResult(data, { scrollToCard: true, x: checkPagePosition.x, y: checkPagePosition.y });
  } catch (error) {
    if (requestGeneration !== checkGeneration) return;
    els.result.classList.remove("hidden");
    const message = error.name === "AbortError"
      ? "Проверка заняла слишком много времени или соединение прервалось."
      : (error.message || "Не удалось связаться с проверяющей системой.");
    els.result.innerHTML = `
      <div class="banner bad">${escapeHtml(message)}</div>
      <button type="button" class="ghost-link" data-retry-check="1">Повторить проверку</button>
    `;
    restorePageScroll(checkPagePosition);
  } finally {
    clearTimeout(timeout);
    if (checkController === controller) checkController = null;
    els.run.disabled = false;
    els.run.textContent = "Проверить";
  }
}

function renderResult(data, savedPosition = capturePagePosition()) {
  els.result.classList.remove("hidden");
  const wrap = editor ? editor.getWrapperElement() : els.code;
  wrap.classList.toggle("syntax-mark", data.status === "syntax");

  const explain = explanationCard(data);
  const examBit = examFooter(data);
  const solutionBit = data.solution_available
    ? `<button type="button" class="solution-button" data-view-solution="1">Посмотреть подробное решение</button>`
    : "";

  if (data.status === "ok") {
    els.result.innerHTML = `${explain}${examBit}`;
    settleAfterCheck(savedPosition);
    renderExamBar();
    return;
  }

  els.result.innerHTML = `${explain}${solutionBit}`;
  placeCursor(data);
  settleAfterCheck(savedPosition);
}

function renderSolution(data, options = {}) {
  const lines = (data.annotated_code || []).map((item) => `
    <div class="solution-line"><code>${escapeHtml(String(item.line).padStart(3, " "))}  ${escapeHtml(item.code)}</code><span>${escapeHtml(item.purpose)}</span></div>
  `).join("");
  const steps = (data.steps || []).map((step) => `<li><b>${escapeHtml(step.title)}</b><span>${escapeHtml(step.text)}</span></li>`).join("");
  const mistakes = (data.common_mistakes || []).map((item) => `<li><b>${escapeHtml(item.title)}</b><span>${escapeHtml(item.detail)}</span></li>`).join("");
  els.result.classList.remove("hidden");
  els.result.innerHTML = `
    <article class="solution-card">
      <p class="explain-kicker">Подробное решение после 10 неудачных попыток</p>
      <h3>${escapeHtml(data.title || "Решение")}</h3>
       <p>${escapeHtml(data.overview || "")}</p>
      <div class="solution-io"><div><b>Что дано</b><span>${escapeHtml(data.input_format || "Смотри условие.")}</span></div><div><b>Что вывести</b><span>${escapeHtml(data.output_format || "Смотри условие.")}</span></div></div>
      <h4>Идея метода: ${escapeHtml(data.method || "")}</h4>
      <ol class="solution-steps">${steps}</ol>
      <h4>Код по строкам</h4>
      <div class="solution-code">${lines}</div>
      <p><b>Сложность:</b> ${escapeHtml(data.complexity || "")}</p>
      <p>${escapeHtml(data.why || "")}</p>
      <h4>Что часто путают</h4>
      <ul class="solution-mistakes">${mistakes}</ul>
      <div class="solution-fast"><b>Быстрый путь:</b> ${escapeHtml(data.fast_path || "")}</div>
    </article>
  `;
  if (options.scroll !== false) scrollResultIntoView();
}

// Rendering a large result can change document height.  Do not let the
// browser choose a new page position differently in different engines.  The
// learner can use the explicit "Показать разбор" control when they want to
// jump to the result.
function capturePagePosition() {
  return { x: window.pageXOffset || window.scrollX || 0, y: window.pageYOffset || window.scrollY || 0 };
}

function restorePageScroll(position) {
  if (!position || !Number.isFinite(position.y)) return;
  const restore = () => window.scrollTo(position.x || 0, position.y);
  restore();
  requestAnimationFrame(() => {
    restore();
    requestAnimationFrame(restore);
  });
}

function scrollResultIntoView() {
  els.result.scrollIntoView({ behavior: "smooth", block: "start" });
}

function revealStatement() {
  const fold = document.getElementById("statement-fold");
  if (fold) fold.open = true;
}

function collapseStatement() {
  const fold = document.getElementById("statement-fold");
  if (fold) fold.open = false;
}

function lineFromExplanation(data) {
  const exp = data && data.explanation;
  if (exp && Number.isInteger(exp.line) && exp.line > 0) return exp.line;
  if (data && data.syntax && data.syntax.line) return data.syntax.line;
  if (!editor) return 0;
  const how = (exp && exp.how) || "";
  const snippets = [...how.matchAll(/`([^`]+)`/g)]
    .map((match) => match[1].replace(/\s+/g, ""))
    .filter((snippet) => snippet);
  const lines = editor.getValue().split("\n");
  for (const needle of snippets) {
    for (let index = 0; index < lines.length; index += 1) {
      if (lines[index].replace(/\s+/g, "").includes(needle)) return index + 1;
    }
  }
  return 0;
}

function placeCursor(data) {
  if (!editor) return;
  const line = lineFromExplanation(data);
  if (!line) return;
  editor.setCursor({ line: line - 1, ch: 0 });
  focusWithoutScrolling(editor);
}

function settleAfterCheck(savedPosition) {
  if (savedPosition && savedPosition.scrollToCard) {
    collapseStatement();
    const jump = () => {
      if (!els.result || els.result.classList.contains("hidden")) return;
      const top = els.result.getBoundingClientRect().top + window.scrollY - 12;
      window.scrollTo(0, Math.max(0, top));
    };
    jump();
    requestAnimationFrame(jump);
    setTimeout(jump, 60);
    setTimeout(jump, 180);
    return;
  }
  restorePageScroll(savedPosition);
}

function focusWithoutScrolling(cm) {
  const field = cm && typeof cm.getInputField === "function" ? cm.getInputField() : null;
  if (field && typeof field.focus === "function") {
    try {
      field.focus({ preventScroll: true });
      return;
    } catch {
      /* Older browsers do not accept focus options. */
    }
  }
}

function replacedLineBlock(data) {
  if (!data || Number(data.tries) < 3 || !editor) return "";
  const how = (data.explanation && data.explanation.how) || "";
  const match = /Замени `([^`]+)` на `([^`]+)`/.exec(how);
  if (!match) return "";
  const lineNo = lineFromExplanation(data);
  if (!lineNo) return "";
  const sourceLine = editor.getLine(lineNo - 1);
  if (!sourceLine || !sourceLine.includes(match[1])) return "";
  const next = sourceLine.replace(match[1], match[2]);
  if (!next || next === sourceLine) return "";
  return `<div class="replaced-line"><span>Эта строка после замены</span><code>${escapeHtml(next)}</code></div>`;
}

function ladderKey() {
  return `ladder:${studentName() || "_"}:${currentId}`;
}

function sameErrorTries(data) {
  const sig = (data.explanation && data.explanation.headline) || data.message || "";
  let prev = {};
  try {
    prev = JSON.parse(localStorage.getItem(ladderKey()) || "{}");
  } catch {
    prev = {};
  }
  const tries = prev.sig === sig ? (Number(prev.tries) || 0) + 1 : 1;
  localStorage.setItem(ladderKey(), JSON.stringify({ sig, tries }));
  return tries;
}

function shorterHint(exp) {
  const text = ((exp && exp.next_step) || "").trim();
  if (!/можно короче/i.test(text)) return "";
  return `<p class="can-shorter">${escapeHtml(text)}</p>`;
}

function openFailure(data) {
  return (data.tests || []).find((test) => !test.hidden && test.verdict && test.verdict !== "OK") || null;
}

function counterexampleBlock(test) {
  if (!test) return "";
  return `<div class="counterexample">
      <code>ввод: ${escapeHtml(preview(test.stdin))}</code>
      <code>нужно: ${escapeHtml(preview(test.expected))}</code>
      <code>получилось: ${escapeHtml(preview(test.got || test.error || "ничего"))}</code>
    </div>`;
}

function explainBlock(label, text, extraClass) {
  if (!text) return "";
  const cls = extraClass ? `explain-block ${extraClass}` : "explain-block";
  return `<div class="${cls}"><span>${label}</span><p>${escapeHtml(text)}</p></div>`;
}

function testsTable(data) {
  const rows = (data.tests || []).map((test) => `
    <tr>
      <td>${test.index + 1}${test.hidden ? " · скрытый" : ""}</td>
      <td><span class="pill ${test.verdict}">${test.verdict}</span></td>
      <td><code>${test.hidden ? "скрыт" : escapeHtml(preview(test.stdin))}</code></td>
      <td><code>${test.hidden ? "скрыт" : escapeHtml(preview(test.expected))}</code></td>
      <td><code>${test.hidden ? (test.verdict === "OK" ? "совпало" : escapeHtml(test.error || "не совпало")) : escapeHtml(test.verdict === "OK" ? (test.got || "").trim() : (test.got || test.error || "—"))}</code></td>
    </tr>
  `).join("");
  if (!rows) return "";
  return `<table class="tests">
      <thead><tr><th>#</th><th>Вердикт</th><th>Ввод</th><th>Ожидали</th><th>Получили</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function explainMore(exp, data) {
  const checks = (data.hints || []).slice(0, 3).map((hint) => `
    <li><b>${escapeHtml(hint.title)}</b><span>${escapeHtml(hint.detail)}</span></li>
  `).join("");
  const trace = (data.trace || []).map((step) => {
    const locals = Object.entries(step.locals || {})
      .map(([key, value]) => `${key} = ${value}`)
      .join(", ");
    return `<div class="trace"><b>стр. ${step.line}</b> ${escapeHtml(locals || "—")}</div>`;
  }).join("");
  const snippet = data.syntax && data.syntax.snippet
    ? `<pre class="snippet">${escapeHtml(data.syntax.snippet)}</pre>`
    : "";
  const tries = data.tries > 1 ? `<p class="explain-kicker">попытка ${data.tries}</p>` : "";
  const inner = [
    tries,
    explainBlock("Как я прочитал твой замысел", exp.intent, "intent"),
    explainBlock("Возможная мысль, которая подвела", exp.thought, "thought"),
    explainBlock("Что случилось", exp.what),
    explainBlock("Почему так", exp.why),
    explainBlock("Как можно решить быстрее в следующий раз", exp.next_step, "next-step"),
    exp.question ? `<div class="coach-question"><span>Вопрос преподавателя</span><p>${escapeHtml(exp.question)}</p></div>` : "",
    explainBlock("Самопроверка перед запуском", exp.self_check, "self-check-step"),
    checks ? `<div class="self-check"><h4>Проверь перед следующей попыткой</h4><ul>${checks}</ul></div>` : "",
    exp.line ? `<div class="line">смотри строку ${exp.line}</div>` : "",
    snippet,
    testsTable(data),
    trace ? `<h3 class="trace-head">Ход программы на упавшем тесте</h3>${trace}` : "",
  ].join("");
  if (!inner.trim()) return "";
  return `<details class="explain-more"><summary>подробнее</summary>${inner}</details>`;
}

function explanationCard(data) {
  const exp = data.explanation;
  if (!exp) {
    return `<div class="banner ${data.status === "ok" ? "ok" : data.status === "syntax" ? "warn" : "bad"}">${escapeHtml(data.message || "")}</div>`;
  }
  if (data.status === "ok") {
    return `
      <article class="explain-card ok">
        <h3>Задача сдана</h3>
        ${shorterHint(exp)}
      </article>
    `;
  }
  const failed = openFailure(data);
  return `
    <article class="explain-card ${escapeAttr(exp.kind || "logic")}">
      <h3>${escapeHtml(exp.headline)}</h3>
      <div class="explain-block"><span>Что сделать</span><p>${escapeHtml(exp.how || "")}</p></div>
      ${replacedLineBlock(data)}
      ${counterexampleBlock(failed)}
      ${explainMore(exp, data)}
    </article>
  `;
}

function examFooter(data) {
  const skipBit = examMode
    ? ` <button type="button" class="ghost-link" data-exam-skip="1">Пропустить</button>`
    : "";
  if (data.status !== "ok") {
    return `<p><button type="button" class="ghost-link" data-next="1">Следующая нерешённая</button>${skipBit}</p>`;
  }
  if (!examMode) {
    return `<p><button type="button" class="ghost-link" data-next="1">Следующая нерешённая</button></p>`;
  }
  const { items, done } = examCounts();
  if (items.length && done >= items.length) {
    return `<div class="banner ok">Зачёт по теме «${escapeHtml(examTopic)}» закрыт: ${done} из ${items.length}.</div>
      <p><button type="button" class="ghost-link" data-exam-exit="1">Завершить экзамен</button></p>`;
  }
  return `<p>В зачёте сдано ${done} из ${items.length}. <button type="button" class="ghost-link" data-next="1">Дальше по теме</button>${skipBit}</p>`;
}

function readingGuide(problem) {
  const tags = new Set(problem.tags || []);
  const file = problem.files && problem.files[0] ? problem.files[0].name : "";
  const alias = fileAlias(problem);
  const sample = ((problem.examples || [])[0] || {}).stdin || "";
  const lines = sample.split("\n").filter((line) => line.trim());
  const first = lines[0] || "";
  const words = first.trim().split(/\s+/).filter(Boolean);
  const numbers = words.length > 0 && words.every((word) => /^-?\d+$/.test(word));

  if (tags.has("ip_restore")) {
    return {
      title: "Правило IPv4",
      text: "Адрес состоит ровно из четырёх десятичных частей. В каждой — от 0 до 255 и от одной до трёх цифр; многозначная часть не начинается с 0. Поставь три точки так, чтобы все четыре части выполняли это правило.",
      code: "часть.часть.часть.часть\n0…255 в каждой части",
    };
  }

  if (file) {
    const name = alias && alias !== file ? alias : file;
    if (tags.has("ege9")) {
      return {
        title: "Как читать таблицу",
        text: "Данные уже лежат в файле. Каждая строка таблицы — отдельная строка файла. Сначала открой файл, потом раздели строку.",
        code: `for line in open('${name}'):\n    parts = line.strip().split(';')`,
      };
    }
    if (tags.has("ege3")) {
      return {
        title: "Как читать таблицу",
        text: "Каждая строка файла — запись с полями через точку с запятой. Сначала раздели строку, затем преобразуй числовые поля.",
        code: `for line in open('${name}'):\n    fields = line.strip().split(';')`,
      };
    }
    if (tags.has("ege10")) {
      return {
        title: "Как читать текст",
        text: "Файл содержит сплошной текст. Прочитай его целиком, нормализуй регистр и только потом ищи слова.",
        code: `text = open('${name}').read().lower()`,
      };
    }
    return {
      title: "Как читать файл",
      text: "Ничего вводить с клавиатуры не нужно. Файл уже подставлен проверяльщиком: открой его и обработай каждую строку.",
      code: tags.has("ege24")
        ? `s = open('${name}').read().strip()`
        : `data = [int(x) for x in open('${name}')]`,
    };
  }
  if (lines.length >= 2 && numbers && lines[1].trim().split(/\s+/).length > 1) {
    return {
      title: "Как читать ввод",
      text: "Сначала в первой строке одно число, затем во второй — несколько чисел через пробел. Нужны два отдельных чтения.",
      code: "n = int(input())\nnums = list(map(int, input().split()))",
    };
  }
  if (lines.length >= 2) {
    return {
      title: "Как читать ввод",
      text: `Во вводе ${lines.length} строки. Каждый вызов input() читает ровно одну следующую строку.`,
      code: lines.slice(0, 3).map((_, index) => `line${index + 1} = input()`).join("\n"),
    };
  }
  if (numbers && words.length > 1) {
    return {
      title: "Как читать ввод",
      text: "Все числа находятся в одной строке и разделены пробелами. Одного int(input()) недостаточно: сначала раздели строку.",
      code: words.length === 2
        ? "a, b = map(int, input().split())"
        : "nums = list(map(int, input().split()))",
    };
  }
  if (numbers && words.length === 1) {
    return {
      title: "Как читать ввод",
      text: "Во вводе ровно одно целое число. input() получает его как текст, поэтому сразу преобразуй в int.",
      code: "n = int(input())",
    };
  }
  if (first && !numbers) {
    return {
      title: "Как читать ввод",
      text: "Здесь вход — текст, а не число. input() уже возвращает строку, int() для неё не нужен.",
      code: "s = input().strip()",
    };
  }
  return {
    title: "Как читать ввод",
    text: "Сверь количество строк и значений с примером. Один input() читает одну строку целиком.",
    code: "line = input().strip()",
  };
}

function fileAlias(problem) {
  const tags = (problem && problem.tags) || [];
  if (tags.includes("ege3")) return "3.txt";
  if (tags.includes("ege9")) return "9.txt";
  if (tags.includes("ege10")) return "10.txt";
  if (tags.includes("ege17")) return "17.txt";
  if (tags.includes("ege18")) return "18.txt";
  if (tags.includes("ege22")) return "22.txt";
  if (tags.includes("ege24")) return "24.txt";
  return "";
}

function preview(text) {
  return String(text || "").replaceAll("\n", " ↵ ").trim() || "—";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function markNameState() {
  els.student.classList.toggle("missing", !studentName());
}

els.topics.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-topic]");
  if (!button) return;
  topicFilter = button.dataset.topic;
  renderChips();
  renderList();
  renderCoach(topicFilter);
  const items = filteredProblems();
  if (topicFilter !== "все" && items[0] && (!currentProblem || currentProblem.topic !== topicFilter)) {
    openProblem(items[0].id, true);
  }
});

els.levels.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-level]");
  if (!button) return;
  levelFilter = button.dataset.level;
  renderChips();
  renderList();
});

els.student.addEventListener("input", () => {
  const prev = localStorage.getItem("student") || "";
  const now = studentName();
  if (currentId) {
    const oldKey = codeKey(currentId, prev || "_");
    const newKey = codeKey(currentId, now || "_");
    if (oldKey !== newKey) {
      localStorage.setItem(newKey, getCode() || localStorage.getItem(oldKey) || "");
    }
  }
  localStorage.setItem("student", now);
  markNameState();
  scheduleProgressSync();
});
els.student.addEventListener("change", async () => {
  localStorage.setItem("student", studentName());
  markNameState();
  try {
    if (studentName()) await ensureSession();
  } catch {
    /* name shown in check */
  }
  syncProgress();
});

if (els.search) {
  els.search.addEventListener("input", () => {
    searchQuery = els.search.value || "";
    renderList();
  });
}

if (els.hideSolved) {
  els.hideSolved.addEventListener("change", () => {
    hideSolved = els.hideSolved.checked;
    renderList();
  });
}

els.code.addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    event.preventDefault();
    const start = els.code.selectionStart;
    const end = els.code.selectionEnd;
    els.code.value = `${els.code.value.slice(0, start)}    ${els.code.value.slice(end)}`;
    els.code.selectionStart = els.code.selectionEnd = start + 4;
  }
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    check();
  }
});

window.addEventListener("hashchange", () => {
  const id = decodeURIComponent((location.hash || "").replace(/^#/, ""));
  if (id && id !== currentId && problems.some((item) => item.id === id)) {
    openProblem(id, false);
  }
});

els.run.addEventListener("click", check);

function flashAction(button, text) {
  if (!button) return;
  const previous = button.textContent;
  button.textContent = text;
  setTimeout(() => {
    button.textContent = previous;
  }, 1200);
}

async function copyCode() {
  const text = getCode();
  try {
    await navigator.clipboard.writeText(text);
    flashAction(els.copy, "Скопировано");
  } catch {
    els.code.focus();
    els.code.select?.();
    flashAction(els.copy, "Выдели код");
  }
}

function resetCode() {
  if (!currentProblem) return;
  if (!window.confirm("Вернуть заготовку? Текст в поле заменится.")) return;
  setCode(starterFor(currentProblem));
  persistCode();
}

function openNextUnsolved() {
  const solved = solvedSet();
  const items = filteredProblems();
  if (!items.length) return;
  const idx = items.findIndex((item) => item.id === currentId);
  const wanted = (item) => !solved.has(item.id) && (!examMode || !examSkip.has(item.id));
  if (examMode) {
    const later = items.slice(idx + 1);
    const next = later.find(wanted)
      || items.find((item) => wanted(item) && item.id !== currentId)
      || later[0];
    if (next) openProblem(next.id, true);
    return;
  }
  const candidates = items.filter((item) => wanted(item) && item.id !== currentId);
  if (!candidates.length) {
    const fallback = items.slice(idx + 1)[0];
    if (fallback) openProblem(fallback.id, true);
    return;
  }
  const currentTopic = currentProblem?.topic || topicFilter;
  const currentLevel = currentProblem?.level || levelFilter;
  const score = (item) => {
    const stats = problemStats[item.id] || {};
    const fails = Number(stats.fails || 0);
    let value = 0;
    if (fails >= 3) value += 1000 + fails * 20;
    if (item.topic === currentTopic) value += 300;
    if (item.level === currentLevel) value += 100;
    if (item.id === items[(idx + 1 + items.length) % items.length]?.id) value += 20;
    return value;
  };
  const next = candidates.sort((a, b) => score(b) - score(a))[0];
  if (next) openProblem(next.id, true);
}

if (els.copy) els.copy.addEventListener("click", copyCode);
if (els.reset) els.reset.addEventListener("click", resetCode);
if (els.next) els.next.addEventListener("click", openNextUnsolved);
if (els.exportProgress) els.exportProgress.addEventListener("click", exportMyProgress);
if (els.repeatErrors) els.repeatErrors.addEventListener("click", () => {
  repeatErrorsMode = !repeatErrorsMode;
  els.repeatErrors.classList.toggle("active", repeatErrorsMode);
  els.repeatErrors.setAttribute("aria-pressed", String(repeatErrorsMode));
  renderList();
});
els.result.addEventListener("click", (event) => {
  if (event.target.closest("[data-show-result]")) {
    scrollResultIntoView();
    return;
  }
  if (event.target.closest("[data-retry-check]")) {
    check();
    return;
  }
  const solutionButton = event.target.closest("[data-view-solution]");
  if (solutionButton) {
    viewSolution(solutionButton);
    return;
  }
  if (event.target.closest("[data-next]")) openNextUnsolved();
  if (event.target.closest("[data-exam-exit]")) stopExam();
  if (event.target.closest("[data-exam-skip]")) skipExamTask();
});

async function viewSolution(button) {
  if (!currentId) return;
  button.disabled = true;
  button.textContent = "Открываю решение…";
  try {
    const response = await fetch("/api/solution/view", {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify({ problem_id: currentId }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Не удалось открыть решение");
    renderSolution(data);
    saveResult(currentId, { status: "solution_viewed", solution: data, tries: data.failed_attempts });
  } catch (error) {
    button.disabled = false;
    button.textContent = "Посмотреть подробное решение";
    const note = document.createElement("p");
    note.className = "banner warn";
    note.textContent = error.message;
    button.insertAdjacentElement("afterend", note);
  }
}
if (els.progressRecommendations) {
  els.progressRecommendations.addEventListener("click", (event) => {
    const button = event.target.closest("[data-progress-task]");
    if (button) openProblem(button.dataset.progressTask, true);
  });
}

if (els.startExam) els.startExam.addEventListener("click", startExam);
if (els.examExit) els.examExit.addEventListener("click", stopExam);
if (els.examSkip) els.examSkip.addEventListener("click", skipExamTask);
if (els.onboardOk) {
  els.onboardOk.addEventListener("click", () => {
    localStorage.setItem("onboard", "1");
    renderOnboard();
  });
}

boot();
