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
  onboard: document.getElementById("onboard"),
  onboardOk: document.getElementById("onboard-ok"),
  coach: document.getElementById("coach"),
  coachTitle: document.getElementById("coach-title"),
  coachWhat: document.getElementById("coach-what"),
  coachSteps: document.getElementById("coach-steps"),
  coachWatch: document.getElementById("coach-watch"),
};

const LEVELS = ["все", "старт", "средне", "сложно"];
const EXAM_SIZE = 8;
let problems = [];
let topicCards = [];
let currentId = null;
let currentProblem = null;
let topicFilter = "все";
let levelFilter = "все";
let searchQuery = "";
let hideSolved = false;
let editor = null;
let openGen = 0;
let progressTimer = 0;
let examMode = false;
let examTopic = "";
let examIds = [];
let examSkip = new Set();
let problemStats = {};

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

function studentName() {
  return (els.student.value || "").trim();
}

function solvedSet() {
  try {
    return new Set(JSON.parse(localStorage.getItem("solved") || "[]"));
  } catch {
    return new Set();
  }
}

function markSolved(id) {
  const set = solvedSet();
  set.add(id);
  localStorage.setItem("solved", JSON.stringify([...set]));
}

function codeKey(id, name) {
  return `code:${name ?? (studentName() || "_")}:${id}`;
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
    sessionStorage.setItem(resultKey(id), JSON.stringify(data));
  } catch {
    /* quota */
  }
}

function loadResult(id) {
  try {
    return JSON.parse(sessionStorage.getItem(resultKey(id)) || "null");
  } catch {
    return null;
  }
}

function renderProgress() {
  if (!els.progress || !els.progressLabel || !els.progressBar) return;
  const topicNow = examMode ? examTopic : topicFilter;
  if (!examMode && topicNow === "все") {
    els.progress.classList.add("hidden");
    renderExamBar();
    return;
  }
  const pool = examMode
    ? examProblems()
    : problems.filter((item) => item.topic === topicNow);
  if (!pool.length) {
    els.progress.classList.add("hidden");
    return;
  }
  const solved = solvedSet();
  const done = pool.filter((item) => solved.has(item.id)).length;
  els.progress.classList.remove("hidden");
  els.progressLabel.textContent = examMode
    ? `Зачёт: сдано ${done} из ${pool.length}`
    : `Сдано ${done} из ${pool.length}`;
  els.progressBar.style.width = `${Math.round((done / pool.length) * 100)}%`;
  renderExamBar();
}

async function syncProgress() {
  const name = studentName();
  if (!name) {
    renderList();
    renderProgress();
    return;
  }
  try {
    const response = await fetch(`/api/progress?student=${encodeURIComponent(name)}`);
    if (!response.ok) return;
    const data = await response.json();
    const set = solvedSet();
    for (const id of data.solved || []) set.add(id);
    localStorage.setItem("solved", JSON.stringify([...set]));
    problemStats = data.problems || {};
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
  return `exam:${studentName() || "_"}`;
}

function examProblems() {
  if (examIds.length) {
    return examIds.map((id) => problems.find((item) => item.id === id)).filter(Boolean);
  }
  return problems.filter((item) => item.topic === examTopic);
}

function examCounts() {
  const items = examProblems();
  const solved = solvedSet();
  const done = items.filter((item) => solved.has(item.id)).length;
  return { items, done, skipped: examSkip.size };
}

function saveExamState() {
  if (!examMode) return;
  localStorage.setItem(examKey(), JSON.stringify({
    topic: examTopic,
    ids: examIds,
    skip: [...examSkip],
  }));
}

function pickExamSet(topic) {
  const pool = problems.filter((item) => item.topic === topic);
  const solved = solvedSet();
  const unsolved = pool.filter((item) => !solved.has(item.id));
  const source = unsolved.length ? unsolved : pool;
  const buckets = { "старт": [], "средне": [], "сложно": [] };
  for (const item of source) {
    (buckets[item.level] || buckets["средне"]).push(item);
  }
  const picked = [];
  function take(list, n) {
    while (n > 0 && list.length) {
      picked.push(list.shift());
      n -= 1;
    }
  }
  take(buckets["старт"], 3);
  take(buckets["средне"], 3);
  take(buckets["сложно"], 2);
  const rest = source.filter((item) => !picked.includes(item));
  take(rest, EXAM_SIZE - picked.length);
  return picked.slice(0, EXAM_SIZE).map((item) => item.id);
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

async function pingExam(action, extra) {
  const name = studentName();
  if (!name) return;
  try {
    await fetch("/api/exam", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({
        student: name,
        action,
        topic: examTopic,
        ids: examIds,
      }, extra || {})),
    });
  } catch {
    /* teacher board is best-effort */
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

function startExam() {
  if (!studentName()) {
    markNameState();
    els.student.focus();
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner warn">Напиши имя сверху — учитель увидит, кто пишет зачёт.</div>`;
    return;
  }
  const topic = topicFilter !== "все" ? topicFilter : (currentProblem && currentProblem.topic);
  if (!topic || topic === "все") {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner warn">Сначала выбери тему слева сверху. Экзамен — 8 задач одной темы, как зачёт.</div>`;
    return;
  }
  examMode = true;
  examTopic = topic;
  topicFilter = topic;
  examIds = pickExamSet(topic);
  examSkip = new Set();
  hideSolved = false;
  if (els.hideSolved) els.hideSolved.checked = false;
  saveExamState();
  pingExam("start", { ids: examIds, topic });
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
  localStorage.removeItem(examKey());
  renderExamBar();
  renderChips();
  renderList();
  renderCoach(topicFilter);
  renderOnboard();
}

function skipExamTask() {
  if (!examMode || !currentId) return;
  examSkip.add(currentId);
  saveExamState();
  pingExamProgress();
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

function restoreExam() {
  const saved = localStorage.getItem(examKey());
  if (!saved) return;
  let topic = "";
  let ids = [];
  let skip = [];
  try {
    const data = JSON.parse(saved);
    if (typeof data === "string") {
      topic = data;
    } else {
      topic = data.topic || "";
      ids = Array.isArray(data.ids) ? data.ids : [];
      skip = Array.isArray(data.skip) ? data.skip : [];
    }
  } catch {
    topic = saved;
  }
  if (!topic || !problems.some((item) => item.topic === topic)) return;
  examMode = true;
  examTopic = topic;
  topicFilter = topic;
  examIds = ids.filter((id) => problems.some((item) => item.id === id));
  if (!examIds.length) examIds = pickExamSet(topic);
  examSkip = new Set(skip);
  pingExam("start", { ids: examIds, topic });
  renderExamBar();
  renderChips();
  renderCoach(topic);
  renderOnboard();
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
    return topicOk && levelOk && searchOk && solvedOk;
  });
}

function renderChips() {
  const topics = examMode
    ? [examTopic]
    : ["все", ...[...new Set(problems.map((item) => item.topic))]];
  const activeTopic = examMode ? examTopic : topicFilter;
  els.topics.innerHTML = topics.map((topic) => `
    <button type="button" data-topic="${escapeAttr(topic)}" class="${topic === activeTopic ? "active" : ""}">${escapeHtml(topic)}</button>
  `).join("");
  els.levels.innerHTML = LEVELS.map((level) => `
    <button type="button" data-level="${escapeAttr(level)}" class="${level === levelFilter ? "active" : ""}">${escapeHtml(level)}</button>
  `).join("");
  if (els.startExam) {
    els.startExam.textContent = examMode ? "Идёт зачёт" : "Начать зачёт · 8 задач";
    els.startExam.disabled = examMode;
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
    button.className = [
      item.id === currentId ? "active" : "",
      examSkip.has(item.id) ? "skipped" : "",
      !solved.has(item.id) && (problemStats[item.id]?.fails || 0) >= 3 ? "stuck" : "",
    ].filter(Boolean).join(" ");
    const fails = problemStats[item.id]?.fails || 0;
    const mark = solved.has(item.id) ? "<i>✓</i>" : examSkip.has(item.id) ? "<i>~</i>" : "";
    const extra = fails && !solved.has(item.id) ? ` · ${fails} попыток` : "";
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
  renderOnboard();
  renderChips();
  renderProgress();
  restoreExam();
  renderCoach(examMode ? examTopic : topicFilter);
  syncProgress();
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
    for (const name of names.concat(["9.txt", "17.txt"])) add(name, "hint-file");
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
  const gen = ++openGen;
  currentId = id;
  if (updateHash) {
    history.replaceState(null, "", `#${id}`);
  }
  renderList();
  els.title.textContent = "Загрузка…";
  els.statement.textContent = "";
  try {
    const response = await fetch(`/api/problems/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error("missing");
    const problem = await response.json();
    if (gen !== openGen) return;
    currentProblem = problem;
    els.level.textContent = `${problem.topic} · ${problem.level}`;
    renderCoach(problem.topic);
    els.title.textContent = problem.title;
    els.statement.textContent = problem.statement;
    if (problem.files && problem.files[0]) {
      const name = problem.files[0].name;
      els.fileBox.classList.remove("hidden");
      const alias = (problem.tags || []).includes("ege9") ? "9.txt" : "17.txt";
      els.fileBox.innerHTML = `К задаче приложен <a href="/api/problems/${encodeURIComponent(problem.id)}/file">${escapeHtml(name)}</a>. <code>open('${escapeHtml(name)}')</code> или <code>open('${alias}')</code> его откроет.`;
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
    const saved = loadSavedCode(id);
    setCode(saved && saved.trim() ? saved : starterFor(problem));
    const previous = loadResult(id);
    if (previous) {
      renderResult(previous);
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
  persistCode();
  if (!studentName()) {
    markNameState();
    els.student.focus();
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner warn">Напиши своё имя сверху, чтобы учитель увидел работу.</div>`;
    return;
  }
  els.run.disabled = true;
  els.run.textContent = "Проверяю…";
  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_id: currentId,
        code: getCode(),
        student: studentName(),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Ошибка проверки");
    }
    if (data.status === "ok") {
      markSolved(currentId);
      examSkip.delete(currentId);
      saveExamState();
      renderList();
      renderProgress();
      pingExamProgress();
    }
    saveResult(currentId, data);
    renderResult(data);
  } catch (error) {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner bad">${escapeHtml(error.message || "Не удалось связаться с проверяющей системой.")}</div>`;
  } finally {
    els.run.disabled = false;
    els.run.textContent = "Проверить";
  }
}

function renderResult(data) {
  els.result.classList.remove("hidden");
  const wrap = editor ? editor.getWrapperElement() : els.code;
  wrap.classList.toggle("syntax-mark", data.status === "syntax");

  const explain = explanationCard(data);
  const examBit = examFooter(data);

  if (data.status === "ok") {
    els.result.innerHTML = `
      ${explain}
      <div class="banner ok">${escapeHtml(data.message)}</div>
      <p>Пройдено тестов: ${data.passed} из ${data.total}.</p>
      ${examBit}
    `;
    els.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
    renderExamBar();
    return;
  }

  if (data.status === "syntax" && data.syntax) {
    els.result.innerHTML = `
      ${explain}
      ${data.syntax.snippet ? `<pre class="snippet">${escapeHtml(data.syntax.snippet)}</pre>` : ""}
    `;
    if (editor && data.syntax.line) {
      editor.setCursor({ line: data.syntax.line - 1, ch: Math.max(0, (data.syntax.column || 1) - 1) });
      editor.focus();
    }
    els.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  const tests = (data.tests || []).map((test) => `
    <tr>
      <td>${test.index + 1}${test.hidden ? " · скрытый" : ""}</td>
      <td><span class="pill ${test.verdict}">${test.verdict}</span></td>
      <td><code>${test.hidden ? "скрыт" : escapeHtml(preview(test.stdin))}</code></td>
      <td><code>${test.hidden ? "скрыт" : escapeHtml(preview(test.expected))}</code></td>
      <td><code>${test.hidden ? (test.verdict === "OK" ? "совпало" : escapeHtml(test.error || "не совпало")) : escapeHtml(test.verdict === "OK" ? (test.got || "").trim() : (test.got || test.error || "—"))}</code></td>
    </tr>
  `).join("");

  const extraHints = (data.hints || []).slice(1).map((hint) => `
    <article class="hint-card ${hint.kind}">
      <h4>${escapeHtml(hint.title)}</h4>
      <p>${escapeHtml(hint.detail)}</p>
      ${hint.line ? `<div class="line">смотри строку ${hint.line}</div>` : ""}
    </article>
  `).join("");

  const trace = (data.trace || []).map((step) => {
    const locals = Object.entries(step.locals || {})
      .map(([key, value]) => `${key} = ${value}`)
      .join(", ");
    return `<div class="trace"><b>стр. ${step.line}</b> ${escapeHtml(locals || "—")}</div>`;
  }).join("");

  els.result.innerHTML = `
    ${explain}
    <details class="more-checks">
      <summary>Тесты и ещё подсказки</summary>
      <table class="tests">
        <thead>
          <tr><th>#</th><th>Вердикт</th><th>Ввод</th><th>Ожидали</th><th>Получили</th></tr>
        </thead>
        <tbody>${tests}</tbody>
      </table>
      ${extraHints}
      ${trace ? `<h3 style="margin-top:18px">Ход программы на упавшем тесте</h3>${trace}` : ""}
    </details>
  `;
  if (data.explanation && data.explanation.line && editor) {
    editor.setCursor({ line: data.explanation.line - 1, ch: 0 });
  }
  els.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function explanationCard(data) {
  const exp = data.explanation;
  if (!exp) return `<div class="banner ${data.status === "ok" ? "ok" : data.status === "syntax" ? "warn" : "bad"}">${escapeHtml(data.message || "")}</div>`;
  const line = exp.line ? `<div class="line">смотри строку ${exp.line}</div>` : "";
  const tries = data.tries > 1 ? ` · попытка ${data.tries}` : "";
  return `
    <article class="explain-card ${escapeAttr(exp.kind || "logic")}">
      <p class="explain-kicker">Разбор для ученика${tries}</p>
      <h3>${escapeHtml(exp.headline)}</h3>
      <div class="explain-block"><span>Что случилось</span><p>${escapeHtml(exp.what)}</p></div>
      <div class="explain-block"><span>Почему так</span><p>${escapeHtml(exp.why)}</p></div>
      <div class="explain-block"><span>Что сделать</span><p>${escapeHtml(exp.how)}</p></div>
      ${line}
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
els.student.addEventListener("change", () => {
  localStorage.setItem("student", studentName());
  markNameState();
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
  const later = items.slice(idx + 1).find(wanted);
  const next = later || items.find((item) => wanted(item) && item.id !== currentId) || items.slice(idx + 1)[0];
  if (next) openProblem(next.id, true);
}

if (els.copy) els.copy.addEventListener("click", copyCode);
if (els.reset) els.reset.addEventListener("click", resetCode);
if (els.next) els.next.addEventListener("click", openNextUnsolved);
els.result.addEventListener("click", (event) => {
  if (event.target.closest("[data-next]")) openNextUnsolved();
  if (event.target.closest("[data-exam-exit]")) stopExam();
  if (event.target.closest("[data-exam-skip]")) skipExamTask();
});

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
