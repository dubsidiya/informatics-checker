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
};

const LEVELS = ["все", "старт", "средне", "сложно"];
let problems = [];
let currentId = null;
let currentProblem = null;
let topicFilter = "все";
let levelFilter = "все";
let editor = null;

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

function codeKey(id) {
  return `code:${studentName() || "_"}:${id}`;
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

function filteredProblems() {
  return problems.filter((item) => {
    const topicOk = topicFilter === "все" || item.topic === topicFilter;
    const levelOk = levelFilter === "все" || item.level === levelFilter;
    return topicOk && levelOk;
  });
}

function renderChips() {
  const topics = ["все", ...[...new Set(problems.map((item) => item.topic))]];
  els.topics.innerHTML = topics.map((topic) => `
    <button type="button" data-topic="${escapeAttr(topic)}" class="${topic === topicFilter ? "active" : ""}">${escapeHtml(topic)}</button>
  `).join("");
  els.levels.innerHTML = LEVELS.map((level) => `
    <button type="button" data-level="${escapeAttr(level)}" class="${level === levelFilter ? "active" : ""}">${escapeHtml(level)}</button>
  `).join("");
}

function renderList() {
  const items = filteredProblems();
  const solved = solvedSet();
  els.count.textContent = `${items.length} из ${problems.length}`;
  els.list.innerHTML = "";
  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.id = item.id;
    button.className = item.id === currentId ? "active" : "";
    button.innerHTML = `
      <span class="task-title">${solved.has(item.id) ? "<i>✓</i>" : ""}${escapeHtml(item.title)}</span>
      <small>${escapeHtml(item.topic)} · ${escapeHtml(item.level)}</small>
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
  setupEditor();
  problems = await (await fetch("/api/problems")).json();
  renderChips();
  const fromHash = decodeURIComponent((location.hash || "").replace(/^#/, ""));
  const start = problems.some((item) => item.id === fromHash) ? fromHash : problems[0]?.id;
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

function pythonHint(cm) {
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
    if (!prefix || prefix.length < 4) {
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
  if (!window.CodeMirror) {
    els.code.addEventListener("input", persistCode);
    return;
  }
  if (window.CodeMirror.registerHelper) {
    window.CodeMirror.registerHelper("hint", "python", pythonHint);
  }
  editor = window.CodeMirror.fromTextArea(els.code, {
    mode: { name: "python", version: 3 },
    theme: "material",
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
    viewportMargin: Infinity,
    gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
    highlightSelectionMatches: { showToken: /\w/, minChars: 2 },
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
    if (typed !== "." && (token.string || "").length < 2 && token.type !== "string") return;
    cm.showHint({ completeSingle: false });
  });
  if (els.full) els.full.addEventListener("click", toggleEditorFull);
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("editor-full")) {
      toggleEditorFull();
    }
  });
  setTimeout(() => {
    editor.refresh();
    editor.setSize(null, "100%");
    updateStatus(editor);
  }, 40);
}

async function openProblem(id, updateHash) {
  if (currentId && currentId !== id) {
    persistCode();
  }
  currentId = id;
  if (updateHash) {
    history.replaceState(null, "", `#${id}`);
  }
  renderList();
  const problem = await (await fetch(`/api/problems/${id}`)).json();
  currentProblem = problem;
  els.level.textContent = `${problem.topic} · ${problem.level}`;
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
  els.examples.innerHTML = problem.examples.map((example) => `
    <div class="example">
      <div><strong>вход</strong>\n${escapeHtml(example.stdin)}</div>
      <div><strong>выход</strong>\n${escapeHtml(example.stdout)}</div>
    </div>
  `).join("");
  const saved = localStorage.getItem(codeKey(id));
  setCode(saved && saved.trim() ? saved : starterFor(problem));
  els.result.classList.add("hidden");
  if (editor) {
    editor.getWrapperElement().classList.remove("syntax-mark");
  } else {
    els.code.classList.remove("syntax-mark");
  }
}

async function check() {
  if (!currentId) return;
  persistCode();
  els.run.disabled = true;
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
      renderList();
    }
    renderResult(data);
  } catch (error) {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner bad">${escapeHtml(error.message || "Не удалось связаться с проверяющей системой.")}</div>`;
  } finally {
    els.run.disabled = false;
  }
}

function renderResult(data) {
  els.result.classList.remove("hidden");
  const wrap = editor ? editor.getWrapperElement() : els.code;
  wrap.classList.toggle("syntax-mark", data.status === "syntax");

  if (data.status === "ok") {
    els.result.innerHTML = `
      <div class="banner ok">${escapeHtml(data.message)}</div>
      <p>Пройдено тестов: ${data.passed} из ${data.total}.</p>
    `;
    els.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  if (data.status === "syntax" && data.syntax) {
    const line = data.syntax.line ? `, строка ${data.syntax.line}` : "";
    els.result.innerHTML = `
      <div class="banner warn">${escapeHtml(data.message)}</div>
      <div class="hint-card syntax">
        <h4>Синтаксическая ошибка${line}</h4>
        <p>${escapeHtml(data.syntax.explanation)}</p>
      </div>
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
      <td><code>${escapeHtml(preview(test.stdin))}</code></td>
      <td><code>${escapeHtml(preview(test.expected))}</code></td>
      <td><code>${escapeHtml(test.verdict === "OK" ? test.got.trim() : (test.got || test.error || "—"))}</code></td>
    </tr>
  `).join("");

  const hints = (data.hints || []).map((hint) => `
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
    <div class="banner bad">${escapeHtml(data.message)} Пройдено ${data.passed} из ${data.total}.</div>
    <div class="grid-2">
      <div>
        <h3>Тесты</h3>
        <table class="tests">
          <thead>
            <tr><th>#</th><th>Вердикт</th><th>Ввод</th><th>Ожидали</th><th>Получили</th></tr>
          </thead>
          <tbody>${tests}</tbody>
        </table>
      </div>
      <div>
        <h3>Где ошибка</h3>
        ${hints || "<p>Автоматический разбор не нашёл типичного шаблона. Сверь ход программы с условием.</p>"}
        ${trace ? `<h3 style="margin-top:18px">Ход программы на первом упавшем тесте</h3>${trace}` : ""}
      </div>
    </div>
  `;
  els.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
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

els.topics.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-topic]");
  if (!button) return;
  topicFilter = button.dataset.topic;
  renderChips();
  renderList();
});

els.levels.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-level]");
  if (!button) return;
  levelFilter = button.dataset.level;
  renderChips();
  renderList();
});

els.student.addEventListener("change", () => {
  localStorage.setItem("student", studentName());
});

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
boot();
