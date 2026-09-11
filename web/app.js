const els = {
  list: document.getElementById("task-list"),
  level: document.getElementById("level"),
  title: document.getElementById("title"),
  statement: document.getElementById("statement"),
  input: document.getElementById("input-format"),
  output: document.getElementById("output-format"),
  examples: document.getElementById("examples"),
  code: document.getElementById("code"),
  run: document.getElementById("run"),
  result: document.getElementById("result"),
};

let currentId = null;

async function boot() {
  const problems = await (await fetch("/api/problems")).json();
  els.list.innerHTML = "";
  for (const item of problems) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.id = item.id;
    button.innerHTML = `${escapeHtml(item.title)}<small>${escapeHtml(item.level)}</small>`;
    button.addEventListener("click", () => openProblem(item.id));
    els.list.appendChild(button);
  }
  if (problems[0]) {
    await openProblem(problems[0].id);
  }
}

async function openProblem(id) {
  currentId = id;
  for (const button of els.list.querySelectorAll("button")) {
    button.classList.toggle("active", button.dataset.id === id);
  }
  const problem = await (await fetch(`/api/problems/${id}`)).json();
  els.level.textContent = problem.level;
  els.title.textContent = problem.title;
  els.statement.textContent = problem.statement;
  els.input.textContent = problem.input_format;
  els.output.textContent = problem.output_format;
  els.examples.innerHTML = problem.examples.map((example) => `
    <div class="example">
      <div><strong>вход</strong>\n${escapeHtml(example.stdin)}</div>
      <div><strong>выход</strong>\n${escapeHtml(example.stdout)}</div>
    </div>
  `).join("");
  if (!els.code.value.trim() || els.code.dataset.starter === "1") {
    els.code.value = starterFor(problem);
    els.code.dataset.starter = "1";
  }
  els.result.classList.add("hidden");
  els.code.classList.remove("syntax-mark");
}

function starterFor(problem) {
  return `# ${problem.title}
# прочитай ввод и выведи только ответ

`;
}

async function check() {
  if (!currentId) return;
  els.run.disabled = true;
  els.code.classList.remove("syntax-mark");
  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ problem_id: currentId, code: els.code.value }),
    });
    const data = await response.json();
    renderResult(data);
  } catch (error) {
    els.result.classList.remove("hidden");
    els.result.innerHTML = `<div class="banner bad">Не удалось связаться с проверяющей системой.</div>`;
  } finally {
    els.run.disabled = false;
  }
}

function renderResult(data) {
  els.result.classList.remove("hidden");
  if (data.status === "ok") {
    els.result.innerHTML = `
      <div class="banner ok">${escapeHtml(data.message)}</div>
      <p>Пройдено тестов: ${data.passed} из ${data.total}.</p>
    `;
    els.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  if (data.status === "syntax" && data.syntax) {
    els.code.classList.add("syntax-mark");
    const line = data.syntax.line ? `, строка ${data.syntax.line}` : "";
    els.result.innerHTML = `
      <div class="banner warn">${escapeHtml(data.message)}</div>
      <div class="hint-card syntax">
        <h4>Синтаксическая ошибка${line}</h4>
        <p>${escapeHtml(data.syntax.explanation)}</p>
      </div>
      ${data.syntax.snippet ? `<pre class="snippet">${escapeHtml(data.syntax.snippet)}</pre>` : ""}
    `;
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

els.code.addEventListener("input", () => {
  els.code.dataset.starter = "0";
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

els.run.addEventListener("click", check);
boot();
