const chatWindow = document.getElementById("chat-window");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const empInput = document.getElementById("employee-id");

let sessionId = localStorage.getItem("cpda_session_id") || null;

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function addUserMessage(text) {
  const wrap = el("div", "msg user");
  const bubble = el("div", "bubble", text);
  wrap.appendChild(bubble);
  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function addLoadingMessage() {
  const wrap = el("div", "msg assistant");
  wrap.id = "loading-msg";
  const bubble = el("div", "bubble loading", "Thinking (calling tools as needed)...");
  wrap.appendChild(bubble);
  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function removeLoadingMessage() {
  const n = document.getElementById("loading-msg");
  if (n) n.remove();
}

function addAssistantMessage(data) {
  const wrap = el("div", "msg assistant");
  const bubble = el("div", "bubble", data.answer);
  wrap.appendChild(bubble);

  const meta = el("div", "meta", `${data.latency_ms} ms`);
  wrap.appendChild(meta);

  if (data.escalated) {
    wrap.appendChild(el("span", "escalated-badge", "Escalated to People & Culture"));
  }

  if (data.trace && data.trace.length) {
    const details = document.createElement("details");
    details.className = "trace";
    const summary = el("summary", null, `Tool-call trace (${data.trace.length} step${data.trace.length > 1 ? "s" : ""})`);
    details.appendChild(summary);
    data.trace.forEach((step) => {
      const stepEl = el("div", "trace-step");
      const argsStr = JSON.stringify(step.arguments);
      stepEl.innerHTML = `<strong>${step.step}. ${step.tool}</strong>(${argsStr}) &rarr; ${step.latency_ms}ms` +
        (step.error ? `<br/><span style="color:var(--error)">error: ${step.error}</span>` : `<br/><code>${step.result_summary}</code>`);
      details.appendChild(stepEl);
    });
    wrap.appendChild(details);
  }

  if (data.citations && data.citations.length) {
    const details = document.createElement("details");
    details.className = "citations";
    const summary = el("summary", null, `Citations (${data.citations.length})`);
    details.appendChild(summary);
    data.citations.forEach((c) => {
      const item = el("div", "citation-item");
      item.innerHTML = `<strong>[${c.doc_id} &sect; ${c.section}]</strong> ${c.doc_title}<br/><em>${(c.snippet || "").slice(0, 200)}...</em>`;
      details.appendChild(item);
    });
    wrap.appendChild(details);
  }

  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendMessage(text) {
  addUserMessage(text);
  addLoadingMessage();
  input.disabled = true;

  try {
    const resp = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    sessionId = data.session_id;
    localStorage.setItem("cpda_session_id", sessionId);
    removeLoadingMessage();
    addAssistantMessage(data);
  } catch (err) {
    removeLoadingMessage();
    const wrap = el("div", "msg assistant");
    wrap.appendChild(el("div", "bubble", `Error contacting the assistant: ${err.message}`));
    chatWindow.appendChild(wrap);
  } finally {
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const empId = empInput.value.trim();
  let text = input.value.trim();
  if (!text) return;
  if (empId && !text.toLowerCase().includes(empId.toLowerCase())) {
    text = `[My employee ID is ${empId}] ${text}`;
  }
  input.value = "";
  sendMessage(text);
});

document.querySelectorAll(".quick-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.emp) empInput.value = btn.dataset.emp;
    sendMessage(btn.dataset.msg);
  });
});
