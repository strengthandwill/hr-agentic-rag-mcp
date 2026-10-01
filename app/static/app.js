const chatWindow = document.getElementById("chat-window");
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const empInput = document.getElementById("employee-id");
const statusPill = document.getElementById("status-pill");
const statusText = document.getElementById("status-text");

let sessionId = localStorage.getItem("cpda_session_id") || null;

async function refreshStatus() {
  try {
    const resp = await fetch("/health");
    const data = await resp.json();
    const ok = data.status === "ok";
    statusPill.className = "header-status " + (ok ? "ok" : "degraded");
    statusText.textContent = ok
      ? `Online — ${data.mcp_tool_count} MCP tools, ${data.rag_chunk_count} policy chunks indexed`
      : "Degraded — some capabilities may be unavailable";
  } catch (err) {
    statusPill.className = "header-status error";
    statusText.textContent = "Unable to reach the assistant service";
  }
}
refreshStatus();
setInterval(refreshStatus, 60000);

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

// Minimal, dependency-free markdown -> HTML renderer for a safe subset (bold, italic, inline
// code, headings, bullet/numbered lists, paragraphs). Escapes all input first so LLM output can
// never inject raw HTML/script, then only ever re-introduces the specific tags below.
function renderMarkdown(raw) {
  const escaped = escapeHtml(raw);
  const lines = escaped.split("\n");
  const htmlParts = [];
  let listType = null; // "ul" | "ol" | null
  let paragraphBuf = [];

  function flushParagraph() {
    if (paragraphBuf.length) {
      htmlParts.push(`<p>${paragraphBuf.join("<br/>")}</p>`);
      paragraphBuf = [];
    }
  }
  function closeList() {
    if (listType) {
      htmlParts.push(`</${listType}>`);
      listType = null;
    }
  }
  function inline(text) {
    return text
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
      .replace(/__([^_]+)__/g, "<strong>$1</strong>");
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    const headingMatch = line.match(/^(#{1,4})\s+(.*)$/);
    const bulletMatch = line.match(/^[-*]\s+(.*)$/);
    const numberedMatch = line.match(/^\d+\.\s+(.*)$/);

    if (headingMatch) {
      flushParagraph();
      closeList();
      const level = Math.min(headingMatch[1].length + 2, 6); // keep headings small in a chat bubble
      htmlParts.push(`<h${level}>${inline(headingMatch[2])}</h${level}>`);
    } else if (bulletMatch) {
      flushParagraph();
      if (listType !== "ul") {
        closeList();
        htmlParts.push("<ul>");
        listType = "ul";
      }
      htmlParts.push(`<li>${inline(bulletMatch[1])}</li>`);
    } else if (numberedMatch) {
      flushParagraph();
      if (listType !== "ol") {
        closeList();
        htmlParts.push("<ol>");
        listType = "ol";
      }
      htmlParts.push(`<li>${inline(numberedMatch[1])}</li>`);
    } else if (line === "") {
      flushParagraph();
      closeList();
    } else if (listType) {
      // Soft-wrapped continuation of the current list item (common in the source policy
      // corpus, which hand-wraps long list entries across multiple indented lines) -- append
      // to the open <li> instead of closing the list and starting a stray paragraph.
      const lastIdx = htmlParts.length - 1;
      htmlParts[lastIdx] = htmlParts[lastIdx].replace(/<\/li>$/, ` ${inline(line)}</li>`);
    } else {
      paragraphBuf.push(inline(line));
    }
  }
  flushParagraph();
  closeList();
  return htmlParts.join("");
}

function removeEmptyState() {
  const empty = chatWindow.querySelector(".empty-state");
  if (empty) empty.remove();
}

function addUserMessage(text) {
  removeEmptyState();
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
  const bubble = el("div", "bubble");
  bubble.innerHTML = renderMarkdown(data.answer);
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
      const argsStr = escapeHtml(JSON.stringify(step.arguments));
      const toolName = escapeHtml(step.tool);
      stepEl.innerHTML = `<strong>${step.step}. ${toolName}</strong>(${argsStr}) &rarr; ${step.latency_ms}ms` +
        (step.error
          ? `<br/><span style="color:var(--error)">error: ${escapeHtml(step.error)}</span>`
          : `<br/><code>${escapeHtml(step.result_summary)}</code>`);
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
      const docId = escapeHtml(c.doc_id);
      const section = escapeHtml(c.section);
      const docTitle = escapeHtml(c.doc_title);
      const snippetHtml = renderMarkdown((c.snippet || "").slice(0, 200) + "...");
      item.innerHTML = `<strong>[${docId} &sect; ${section}]</strong> ${docTitle}<div class="citation-snippet">${snippetHtml}</div>`;
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
