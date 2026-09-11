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
};

const LEVELS = ["все", "старт", "средне", "сложно"];
let problems = [];
let currentId = null;
let topicFilter = "все";
let levelFilter = "все";
let editor = null;

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
  if (problem.files && problem.files[0]) {
    const name = problem.files[0].name;
    return `# ${problem.title}\ndata = [int(x) for x in open('${name}')]\n\n`;
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
  problems = await (await fetch("/api/problems")).json();
  renderChips();
  const fromHash = decodeURIComponent((location.hash || "").replace(/^#/, ""));
  const start = problems.some((item) => item.id === fromHash) ? fromHash : problems[0]?.id;
  if (start) {
    await openProblem(start, false);
  } else {
    renderList();
  }
  setupEditor();
}

function setupEditor() {
  if (!window.CodeMirror) {
    els.code.addEventListener("input", persistCode);
    return;
  }
  editor = window.CodeMirror.fromTextArea(els.code, {
    mode: "python",
    theme: "material",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: true,
    extraKeys: {
      Tab: (cm) => cm.replaceSelection("    "),
      "Ctrl-Enter": check,
      "Cmd-Enter": check,
    },
  });
  editor.on("change", persistCode);
  setTimeout(() => editor.refresh(), 40);
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
  els.level.textContent = `${problem.topic} · ${problem.level}`;
  els.title.textContent = problem.title;
  els.statement.textContent = problem.statement;
  if (problem.files && problem.files[0]) {
    const name = problem.files[0].name;
    els.fileBox.classList.remove("hidden");
    els.fileBox.innerHTML = `К задаче приложен <a href="/api/problems/${encodeURIComponent(problem.id)}/file">${escapeHtml(name)}</a>. <code>open('${escapeHtml(name)}')</code> или <code>open('17.txt')</code> его откроет.`;
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
