const PY_WORDS = ["False","None","True","and","as","assert","async","await","break","class","continue","def","elif","else","except","finally","for","from","global","if","import","in","is","lambda","nonlocal","not","or","pass","raise","return","try","while","with","yield","abs","all","any","bin","bool","dict","enumerate","filter","float","input","int","len","list","map","max","min","open","ord","pow","print","range","reversed","round","set","sorted","str","sum","tuple","zip"];

function pythonHint(cm) {
  const cursor = cm.getCursor();
  const token = cm.getTokenAt(cursor);
  const prefix = (token.string || "").slice(0, cursor.ch - token.start);
  if (!/^[A-Za-z_]\w*$/.test(prefix)) return null;
  const list = PY_WORDS.filter((word) => word.startsWith(prefix) && word !== prefix);
  return { list, from: CodeMirror.Pos(cursor.line, token.start), to: cursor };
}

const code = CodeMirror.fromTextArea(document.getElementById("code"), {
  mode: { name: "python", version: 3 },
  theme: document.documentElement.getAttribute("data-theme") === "dark" ? "material" : "default",
  lineNumbers: true,
  indentUnit: 4,
  tabSize: 4,
  indentWithTabs: false,
  lineWrapping: true,
  matchBrackets: true,
  autoCloseBrackets: { pairs: "()[]{}''\"\"", explode: "[]{}" },
  styleActiveLine: true,
  foldGutter: true,
  gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
  hintOptions: { hint: pythonHint, completeSingle: false },
  extraKeys: {
    "Ctrl-Space": "autocomplete",
    "Alt-Space": "autocomplete",
    "Ctrl-/": "toggleComment",
    "Cmd-/": "toggleComment",
    "Ctrl-F": "findPersistent",
    "Cmd-F": "findPersistent",
    "Ctrl-H": "replace",
    "Cmd-Alt-F": "replace",
    "Shift-Tab": "indentLess",
    Tab(cm) {
      if (cm.somethingSelected()) return cm.execCommand("indentMore");
      const cursor = cm.getCursor();
      const line = cm.getLine(cursor.line).slice(0, cursor.ch);
      if (/\s$/.test(line) || !line.trim()) return cm.execCommand("indentMore");
      cm.showHint({ completeSingle: false, hint: pythonHint });
    },
    Enter(cm) {
      const cursor = cm.getCursor();
      const line = cm.getLine(cursor.line);
      cm.execCommand("newlineAndIndent");
      if (line.trimEnd().endsWith(":")) {
        const next = cm.getCursor();
        if (cm.getLine(next.line).trim() === "") cm.execCommand("indentMore");
      }
    },
  },
});
code.on("inputRead", (cm, change) => {
  if (cm.state.completionActive) return;
  const typed = change.text[0] || "";
  if (!/[A-Za-z_]/.test(typed)) return;
  const token = cm.getTokenAt(cm.getCursor());
  if ((token.string || "").length >= 2 && token.type !== "comment" && token.type !== "string") {
    cm.showHint({ completeSingle: false, hint: pythonHint });
  }
});
const stdin = document.getElementById("stdin");
const upload = document.getElementById("upload");
const fileName = document.getElementById("file-name");
const output = document.getElementById("output");
const run = document.getElementById("run");
const saved = localStorage.getItem("playground-code");
if (saved) code.setValue(saved);
code.on("change", () => localStorage.setItem("playground-code", code.getValue()));

upload.addEventListener("change", () => {
  const file = upload.files && upload.files[0];
  fileName.textContent = file ? `Будет доступен как open('${file.name}')` : "Файл не выбран.";
});

async function readUpload() {
  const file = upload.files && upload.files[0];
  if (!file) return { filename: "", file: "" };
  if (file.size > 20_000_000) throw new Error("Файл больше 20 МБ.");
  return { filename: file.name, file: await file.text() };
}

const timer = document.getElementById("timer");
let timerHandle = null;

function startTimer() {
  const started = performance.now();
  timer.textContent = "Время: 0.0 с";
  timerHandle = setInterval(() => {
    timer.textContent = `Время: ${((performance.now() - started) / 1000).toFixed(1)} с`;
  }, 100);
}

function stopTimer(elapsedMs) {
  clearInterval(timerHandle);
  timerHandle = null;
  timer.textContent = Number.isFinite(elapsedMs)
    ? `Время: ${(elapsedMs / 1000).toFixed(3)} с`
    : "Время: —";
}
run.addEventListener("click", async () => {
  if (run.disabled) return;
  run.disabled = true;
  startTimer();
  output.textContent = "Запускаю…";
  try {
    const uploaded = await readUpload();
    const response = await fetch("/api/playground", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code.getValue(), stdin: stdin.value, ...uploaded }),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      output.textContent = data.detail || "Не удалось запустить программу.";
      return;
    }
    const parts = [];
    if (data.stdout) parts.push(data.stdout);
    if (data.stderr) parts.push(data.stderr);
    if (data.detail) parts.push(data.detail);
    if (data.status === "timeout" && !data.detail) {
      parts.push("Программа остановлена по ограничению времени.");
    }
    if (data.translation) parts.push(data.translation);
    output.textContent = parts.join("\n") || "Программа завершилась без вывода.";
    stopTimer(data.elapsed_ms);
  } catch (error) {
    output.textContent = error.message || "Не удалось связаться с сервером.";
  } finally {
    if (timerHandle) stopTimer();
    run.disabled = false;
  }
});
