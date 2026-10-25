// Task 4.12 - SEC RAG project showcase + query UI.
// Zero-build vanilla JS (ES module). Same-origin relative requests only -
// never hardcodes a host/port. Never uses innerHTML for API-returned or
// data-file text; every dynamic value goes through textContent or an
// explicit safe DOM builder below.

import { PROJECT_DATA } from "./project-data.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function el(tag, { className, text, attrs } = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  }
  return node;
}

/* ------------------------------------------------------------- theme --- */

function initTheme() {
  const toggle = $("#theme-toggle");
  if (!toggle) return;
  const stored = safeGet("sec-rag-theme");
  if (stored === "light" || stored === "dark") {
    document.documentElement.setAttribute("data-theme", stored);
    toggle.setAttribute("aria-pressed", String(stored === "light"));
  }
  toggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
    const effectiveCurrent = current || (prefersLight ? "light" : "dark");
    const next = effectiveCurrent === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    toggle.setAttribute("aria-pressed", String(next === "light"));
    safeSet("sec-rag-theme", next);
  });
}

function safeGet(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function safeSet(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* ignore */ }
}

/* ------------------------------------------------------------ live status */

async function fetchJSON(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const err = new Error(`request to ${path} failed with ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function setStatusDot(dotEl, state) {
  if (!dotEl) return;
  dotEl.setAttribute("data-state", state);
}

async function refreshLiveStatus() {
  const heroDot = $("#hero-status-dot");
  const heroLabel = $("#hero-status-label");

  try {
    await fetchJSON("/health");
  } catch {
    setStatusDot(heroDot, "down");
    if (heroLabel) heroLabel.textContent = "Service unreachable";
    return;
  }

  try {
    const status = await fetchJSON("/status");
    const ready = Boolean(status.ready);
    setStatusDot(heroDot, ready ? "ok" : "unknown");
    if (heroLabel) heroLabel.textContent = ready ? "Live and ready" : "Starting up";
    updateGenerationProviderNote(status);
  } catch {
    setStatusDot(heroDot, "unknown");
    if (heroLabel) heroLabel.textContent = "Status unavailable";
  }
}

function updateGenerationProviderNote(status) {
  const note = $("#provider-note");
  if (!note) return;
  const provider = status && status.config ? status.config.generation_provider : null;
  if (provider) {
    note.hidden = false;
    const textEl = $("#provider-note-text", note);
    if (textEl) textEl.textContent = `This deployment currently resolves generation through "${provider}". Answers on the dense route may call that external provider.`;
  } else {
    note.hidden = true;
  }
}

/* ---------------------------------------------------------------- chat -- */

const CHAT_MAX_LENGTH = 2000; // matches src/config.py's DEFAULT_INPUT_GUARD_MAX_LENGTH
const CHAT_NEAR_LIMIT_THRESHOLD = 1800;
const CHAT_REQUEST_TIMEOUT_MS = 30000;

function autosizeTextarea(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
}

function initChat() {
  const form = $("#chat-form");
  if (!form) return;
  const textarea = $("#chat-input");
  const sendBtn = $("#chat-send");
  const newChatBtn = $("#new-chat-btn");
  const messagesEl = $("#chat-messages");
  const emptyState = $("#chat-empty");
  const charCount = $("#chat-char-count");

  let inFlight = false;
  let conversationToken = 0;

  function updateCharCount() {
    if (!charCount) return;
    const len = textarea.value.length;
    if (len >= CHAT_NEAR_LIMIT_THRESHOLD) {
      charCount.hidden = false;
      charCount.textContent = `${len} / ${CHAT_MAX_LENGTH}`;
      charCount.setAttribute("data-near-limit", String(len >= CHAT_MAX_LENGTH));
    } else {
      charCount.hidden = true;
    }
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideEmptyState() {
    if (emptyState && !emptyState.hidden) emptyState.hidden = true;
  }

  function appendUserMessage(text) {
    const wrap = el("div", { className: "chat-msg chat-msg-user" });
    wrap.appendChild(el("div", { className: "chat-msg-bubble", text }));
    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  function appendThinking() {
    const wrap = el("div", { className: "chat-msg chat-msg-assistant" });
    const bubble = el("div", { className: "chat-msg-bubble" });
    const thinking = el("div", { className: "chat-thinking" });
    const dots = el("span", { className: "chat-thinking-dots", attrs: { "aria-hidden": "true" } });
    dots.appendChild(el("span"));
    dots.appendChild(el("span"));
    dots.appendChild(el("span"));
    thinking.appendChild(dots);
    thinking.appendChild(el("span", { text: "Thinking through SEC filings and financial data…" }));
    bubble.appendChild(thinking);
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function appendSystemMessage(text, { isError = false } = {}) {
    const wrap = el("div", { className: `chat-msg chat-msg-system${isError ? " is-error" : ""}` });
    wrap.appendChild(el("div", { className: "chat-msg-bubble", text }));
    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  function replaceWithAssistantMessage(placeholderNode, data, elapsedMs) {
    const wrap = el("div", { className: "chat-msg chat-msg-assistant" });
    const bubble = el("div", { className: "chat-msg-bubble" });

    const metaRow = el("div", { className: "chat-msg-meta" });
    metaRow.appendChild(el("span", {
      className: `badge ${data.status === "answered" ? "badge-answered" : "badge-rejected"}`,
      text: data.status,
    }));
    if (data.route) {
      metaRow.appendChild(el("span", { className: "badge badge-route", text: data.route }));
    }
    if (data.reason_code) {
      metaRow.appendChild(el("span", { className: "badge badge-rejected", text: data.reason_code }));
    }
    bubble.appendChild(metaRow);

    const answerText = data.answer || (data.status === "rejected"
      ? "This question was declined by an input guardrail before retrieval."
      : "No answer text was returned.");
    bubble.appendChild(el("p", { className: "chat-msg-answer", text: answerText }));

    if (Array.isArray(data.citations) && data.citations.length > 0) {
      const list = el("ul", { className: "chat-msg-citations" });
      for (const citation of data.citations) {
        list.appendChild(el("li", { text: citation }));
      }
      bubble.appendChild(list);
    }

    const footer = el("div", { className: "chat-msg-footer" });
    const footerMeta = el("span", { text: `Client-observed latency: ${elapsedMs} ms${data.request_id ? ` · request_id: ${data.request_id}` : ""}` });
    footer.appendChild(footerMeta);
    if (data.answer) {
      const copyBtn = el("button", { className: "chat-msg-copy", text: "Copy", attrs: { type: "button" } });
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(data.answer);
          copyBtn.textContent = "Copied";
          setTimeout(() => { copyBtn.textContent = "Copy"; }, 1500);
        } catch {
          /* clipboard API unavailable - silently no-op, never throw to the user */
        }
      });
      footer.appendChild(copyBtn);
    }
    bubble.appendChild(footer);

    wrap.appendChild(bubble);
    placeholderNode.replaceWith(wrap);
    scrollToBottom();
  }

  function replaceWithSystemMessage(placeholderNode, text) {
    placeholderNode.remove();
    appendSystemMessage(text, { isError: true });
  }

  async function sendQuery(question) {
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeoutId = controller ? setTimeout(() => controller.abort(), CHAT_REQUEST_TIMEOUT_MS) : null;
    try {
      return await fetchJSON("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: controller ? controller.signal : undefined,
      });
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }
  }

  function messageForError(err) {
    if (err && err.name === "AbortError") {
      return "That took longer than expected. Please try again.";
    }
    if (err && err.status === 503) {
      return "The generation provider is temporarily unavailable. Please try again in a moment.";
    }
    if (err && err.status === 500) {
      return "Something went wrong on the server. Please try again.";
    }
    if (err && err.status === 422) {
      return "That request wasn't valid. Try rephrasing your question.";
    }
    if (err && err.status) {
      return `The service returned an error (HTTP ${err.status}). Please try again.`;
    }
    return "Couldn't reach the RAG service. Check your connection and try again.";
  }

  async function handleSubmit(question) {
    hideEmptyState();
    appendUserMessage(question);
    const placeholder = appendThinking();
    const myToken = conversationToken;
    const started = performance.now();

    try {
      const data = await sendQuery(question);
      if (myToken !== conversationToken) return; // a New Chat happened meanwhile
      const elapsedMs = Math.round(performance.now() - started);
      replaceWithAssistantMessage(placeholder, data, elapsedMs);
    } catch (err) {
      if (myToken !== conversationToken) return;
      replaceWithSystemMessage(placeholder, messageForError(err));
    }
  }

  textarea.addEventListener("input", () => {
    autosizeTextarea(textarea);
    updateCharCount();
  });

  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  $$(".suggestion-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      textarea.value = chip.dataset.prompt || chip.textContent;
      autosizeTextarea(textarea);
      updateCharCount();
      textarea.focus();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (inFlight) return;
    const question = textarea.value.trim();
    if (!question) {
      textarea.focus();
      return;
    }

    inFlight = true;
    sendBtn.disabled = true;
    textarea.value = "";
    autosizeTextarea(textarea);
    updateCharCount();

    try {
      await handleSubmit(question);
    } finally {
      inFlight = false;
      sendBtn.disabled = false;
      textarea.focus();
    }
  });

  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      conversationToken += 1;
      $$(".chat-msg", messagesEl).forEach((n) => n.remove());
      if (emptyState) emptyState.hidden = false;
      textarea.value = "";
      autosizeTextarea(textarea);
      updateCharCount();
      textarea.focus();
    });
  }
}

/* --------------------------------------------------------- data cards --- */

function renderMetricCards(containerId, items) {
  const container = document.getElementById(containerId);
  if (!container || !Array.isArray(items)) return;
  container.textContent = "";
  for (const item of items) {
    const card = el("div", { className: "card" });
    if (item.status_type) {
      card.appendChild(el("span", { className: `status-type status-type-${item.status_type}`, text: labelForStatusType(item.status_type) }));
    }
    card.appendChild(el("p", { className: "card-label", text: item.label }));
    card.appendChild(el("p", { className: "card-value", text: formatValue(item) }));
    if (item.context) card.appendChild(el("p", { className: "card-context", text: item.context }));
    if (item.source_path) {
      card.appendChild(el("span", {
        className: "card-source",
        text: `Source: ${item.source_path}${item.source_key ? ` → ${item.source_key}` : ""}`,
      }));
    }
    container.appendChild(card);
  }
}

function formatValue(item) {
  if (item.value === null || item.value === undefined) return "—";
  return item.unit ? `${item.value} ${item.unit}` : String(item.value);
}

function labelForStatusType(type) {
  return {
    frozen: "Frozen result",
    "current-build": "Current build",
    "live-runtime": "Live runtime",
    roadmap: "Roadmap",
  }[type] || type;
}

/* ------------------------------------------------------------ bar charts */

function buildBarChart({ rows, winnerLabel, unit }) {
  const wrap = el("div");
  const max = Math.max(...rows.map((r) => Number(r.value) || 0), 1);
  const chart = el("div", { className: "bar-chart", attrs: { role: "img", "aria-label": `Bar chart comparing ${rows.map((r) => r.label).join(", ")}` } });
  for (const row of rows) {
    const isWinner = winnerLabel && row.label === winnerLabel;
    const rowEl = el("div", { className: `bar-row${isWinner ? " is-winner" : ""}` });
    rowEl.appendChild(el("span", { className: "bar-row-label", text: row.label }));
    const track = el("div", { className: "bar-track" });
    const pct = Math.max(2, Math.round(((Number(row.value) || 0) / max) * 100));
    const fill = el("div", { className: "bar-fill" });
    fill.style.width = `${pct}%`;
    track.appendChild(fill);
    rowEl.appendChild(track);
    rowEl.appendChild(el("span", { className: "bar-row-value", text: `${row.value}${unit ? ` ${unit}` : ""}` }));
    chart.appendChild(rowEl);
  }
  wrap.appendChild(chart);

  // Accessible fallback: a visible data table alongside the visual bars,
  // per standard chart-accessibility guidance (never encode meaning by
  // color/bar-length alone).
  const tableWrap = el("div", { className: "table-scroll" });
  const table = el("table", { className: "data-table" });
  const thead = el("thead");
  const headRow = el("tr");
  headRow.appendChild(el("th", { text: "Candidate" }));
  headRow.appendChild(el("th", { text: unit ? `Value (${unit})` : "Value" }));
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = el("tbody");
  for (const row of rows) {
    const tr = el("tr");
    if (winnerLabel && row.label === winnerLabel) tr.classList.add("is-winner");
    tr.appendChild(el("td", { text: row.label }));
    tr.appendChild(el("td", { text: String(row.value) }));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  wrap.appendChild(tableWrap);
  return wrap;
}

/* --------------------------------------------------------- experiments */

const OUTCOME_LABEL = {
  selected: "Selected",
  rejected: "Evaluated — not selected",
  evaluated: "Evaluated",
};

function renderExperiments(containerId, experiments) {
  const container = document.getElementById(containerId);
  if (!container || !Array.isArray(experiments)) return;
  container.textContent = "";
  for (const exp of experiments) {
    const card = el("div", { className: "card", attrs: { style: "margin-bottom:var(--space-5);" } });
    if (exp.status_type) {
      card.appendChild(el("span", { className: `status-type status-type-${exp.status_type}`, text: labelForStatusType(exp.status_type) }));
    }
    card.appendChild(el("h3", { text: exp.title, attrs: { style: "margin:0 0 var(--space-2);font-size:1.05rem;" } }));
    if (exp.outcome) {
      const badgeClass = exp.outcome === "rejected" ? "badge-rejected" : "badge-answered";
      card.appendChild(el("span", { className: `badge ${badgeClass}`, text: OUTCOME_LABEL[exp.outcome] || exp.outcome }));
    }
    card.appendChild(el("p", { text: exp.summary, attrs: { style: "margin:var(--space-3) 0;color:var(--color-muted-foreground);" } }));
    if (Array.isArray(exp.candidates) && exp.candidates.length > 0) {
      card.appendChild(buildBarChart({ rows: exp.candidates, winnerLabel: exp.winnerLabel, unit: exp.unit }));
    }
    if (exp.detail) {
      card.appendChild(el("p", { text: exp.detail, attrs: { style: "font-size:0.88rem;" } }));
    }
    if (exp.source_path) {
      card.appendChild(el("span", { className: "card-source", text: `Source: ${exp.source_path}${exp.source_key ? ` → ${exp.source_key}` : ""}` }));
    }
    container.appendChild(card);
  }
}

/* ------------------------------------------------------------- timeline */

function renderTimeline(containerId, items) {
  const container = document.getElementById(containerId);
  if (!container || !Array.isArray(items)) return;
  container.textContent = "";
  for (const item of items) {
    const li = el("div", { className: "timeline-item", attrs: { "data-status": item.status } });
    li.appendChild(el("p", { className: "timeline-title", text: item.title }));
    li.appendChild(el("p", { className: "timeline-desc", text: item.description }));
    container.appendChild(li);
  }
}

/* -------------------------------------------------------- roadmap cols */

function renderRoadmapColumn(containerId, items) {
  const container = document.getElementById(containerId);
  if (!container || !Array.isArray(items)) return;
  container.textContent = "";
  for (const item of items) {
    container.appendChild(el("li", { text: item }));
  }
}

/* ---------------------------------------------------------- guardrails */

function renderGuardrails(containerId, items) {
  const container = document.getElementById(containerId);
  if (!container || !Array.isArray(items)) return;
  container.textContent = "";
  for (const item of items) {
    const card = el("div", { className: "card guardrail-card" });
    card.appendChild(el("h3", { text: item.name }));
    card.appendChild(el("p", { text: item.description }));
    if (item.testCount) {
      card.appendChild(el("p", { className: "test-count", text: `${item.testCount} tests` }));
    }
    if (item.source_path) {
      card.appendChild(el("span", { className: "card-source", text: `Source: ${item.source_path}` }));
    }
    container.appendChild(card);
  }
}

/* ------------------------------------------ deep architecture (4.12a) */

function prefersReducedMotion() {
  try {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

let archTipCounter = 0;

function buildFlowStepBox(step) {
  const hasDetail = !!step.detail;
  const hasTooltip = !!step.tooltip;
  const attrs = { "data-status": step.status || "live" };
  if (hasDetail) attrs.type = "button";
  let tooltipId = null;
  if (hasTooltip) {
    tooltipId = `arch-tip-${archTipCounter++}`;
    attrs["aria-describedby"] = tooltipId;
  }
  const box = el(hasDetail ? "button" : "div", {
    className: `flow-step${hasDetail ? " is-clickable" : ""}${hasTooltip ? " has-tip" : ""}`,
    attrs,
  });

  const labelRow = el("span", { className: "flow-step-label" });
  labelRow.appendChild(el("span", {
    className: "arch-status-dot",
    attrs: { "data-status": step.status || "live", "aria-hidden": "true" },
  }));
  labelRow.appendChild(document.createTextNode(step.label));
  box.appendChild(labelRow);

  if (step.sublabel) {
    box.appendChild(el("span", { className: "flow-step-sublabel", text: step.sublabel }));
  }
  if (hasTooltip) {
    box.appendChild(el("span", {
      className: "tip-bubble",
      text: step.tooltip,
      attrs: { role: "tooltip", id: tooltipId },
    }));
  }
  if (hasDetail) {
    box.addEventListener("click", () => showArchDetail(step));
  }
  return box;
}

function renderFlowSteps(steps) {
  const flow = el("div", { className: "flow" });
  steps.forEach((step, i) => {
    if (i > 0) {
      flow.appendChild(el("div", { className: "flow-connector", attrs: { "aria-hidden": "true" } }));
    }
    if (step.branch) {
      const branchWrap = el("div", { className: "flow-branches" });
      for (const branchStep of step.branch) branchWrap.appendChild(buildFlowStepBox(branchStep));
      flow.appendChild(branchWrap);
    } else {
      flow.appendChild(buildFlowStepBox(step));
    }
  });
  return flow;
}

function renderDeepArchTabContent(panel, tab) {
  for (const flow of tab.flows) {
    const block = el("div", { className: "arch-flow-block" });
    block.appendChild(el("h3", { className: "arch-flow-title", text: flow.title }));
    if (flow.note) {
      block.appendChild(el("p", { className: "arch-flow-note", text: flow.note }));
    }
    if (Array.isArray(flow.steps)) {
      block.appendChild(renderFlowSteps(flow.steps));
    }
    if (Array.isArray(flow.multi)) {
      const grid = el("div", { className: "arch-multi-grid" });
      for (const col of flow.multi) {
        const colEl = el("div", { className: "arch-multi-col" });
        colEl.appendChild(el("h4", { text: col.label }));
        colEl.appendChild(renderFlowSteps(col.steps));
        grid.appendChild(colEl);
      }
      block.appendChild(grid);
    }
    panel.appendChild(block);
  }
}

function showArchDetail(step) {
  const panel = $("#arch-detail-panel");
  const title = $("#arch-detail-title");
  const body = $("#arch-detail-body");
  if (!panel || !title || !body || !step.detail) return;

  title.textContent = step.label;
  body.textContent = "";
  const fields = [
    ["purpose", "Purpose"], ["input", "Input"], ["output", "Output"],
    ["implementation", "Implementation"], ["evidence", "Evidence"], ["status", "Current status"],
  ];
  for (const [key, fieldLabel] of fields) {
    const value = step.detail[key];
    if (!value) continue;
    body.appendChild(el("dt", { text: fieldLabel }));
    body.appendChild(el("dd", { text: value }));
  }
  panel.hidden = false;
  panel.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "nearest" });
  $("#arch-detail-close")?.focus();
}

function initDeepArchitecture() {
  const data = PROJECT_DATA.deepArchitecture;
  const tablist = $("#deep-arch-tablist");
  const panelsContainer = $("#deep-arch-tabpanels");
  if (!data || !tablist || !panelsContainer) return;

  function activateTab(id) {
    $$('[role="tab"]', tablist).forEach((b) => {
      const isActive = b.id === `tab-btn-${id}`;
      b.setAttribute("aria-selected", String(isActive));
      b.tabIndex = isActive ? 0 : -1;
    });
    $$('[role="tabpanel"]', panelsContainer).forEach((p) => {
      p.hidden = p.id !== `tab-panel-${id}`;
    });
    // The detail panel is a single shared node below the tabs - switching
    // tabs must close it, otherwise it keeps showing a box's detail from
    // whichever tab was active when it was opened.
    const detailPanel = $("#arch-detail-panel");
    if (detailPanel) detailPanel.hidden = true;
  }

  data.tabs.forEach((tab, i) => {
    const btn = el("button", {
      className: "tab-btn", text: tab.label,
      attrs: {
        role: "tab", id: `tab-btn-${tab.id}`, "aria-controls": `tab-panel-${tab.id}`,
        "aria-selected": i === 0 ? "true" : "false", tabindex: i === 0 ? "0" : "-1", type: "button",
      },
    });
    btn.addEventListener("click", () => activateTab(tab.id));
    tablist.appendChild(btn);

    const panel = el("div", {
      className: "tab-panel",
      attrs: { role: "tabpanel", id: `tab-panel-${tab.id}`, "aria-labelledby": `tab-btn-${tab.id}` },
    });
    if (i !== 0) panel.hidden = true;
    renderDeepArchTabContent(panel, tab);
    panelsContainer.appendChild(panel);
  });

  tablist.addEventListener("keydown", (event) => {
    const tabs = $$('[role="tab"]', tablist);
    const currentIndex = tabs.indexOf(document.activeElement);
    if (currentIndex === -1) return;
    let nextIndex = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    else if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex !== null) {
      event.preventDefault();
      tabs[nextIndex].focus();
      activateTab(tabs[nextIndex].id.replace("tab-btn-", ""));
    }
  });

  const closeBtn = $("#arch-detail-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      const panel = $("#arch-detail-panel");
      if (panel) panel.hidden = true;
    });
  }
}

/* ------------------------------------------------------------- router -- */

const VIEW_FOR_PATH = {
  "/": "chat",
  "/architecture": "architecture",
  "/experiments": "experiments",
  "/data": "data",
  "/evaluation": "evaluation",
  "/roadmap": "roadmap",
};

const TITLE_FOR_VIEW = {
  chat: "Chat",
  architecture: "Architecture",
  experiments: "Experiments",
  data: "Data",
  evaluation: "Evaluation",
  roadmap: "Roadmap",
};

function routeFromPath(pathname) {
  return VIEW_FOR_PATH[pathname] || "chat";
}

function showView(viewName) {
  $$(".view").forEach((v) => { v.hidden = v.dataset.view !== viewName; });
  $$(".sidebar-nav a[data-view]").forEach((a) => {
    a.classList.toggle("is-active", a.dataset.view === viewName);
  });
  const titleEl = $("#topbar-title");
  if (titleEl) titleEl.textContent = TITLE_FOR_VIEW[viewName] || "";
  document.title = viewName === "chat"
    ? "SEC RAG — Chat"
    : `SEC RAG — ${TITLE_FOR_VIEW[viewName]}`;
}

function initRouter() {
  function navigate(pathname, { push = true } = {}) {
    const view = routeFromPath(pathname);
    if (push && location.pathname !== pathname) {
      history.pushState({ pathname }, "", pathname);
    }
    showView(view);
    closeSidebarDrawer();
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-route]");
    if (!link) return;
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(link.getAttribute("href"));
  });

  window.addEventListener("popstate", () => {
    showView(routeFromPath(location.pathname));
  });

  showView(routeFromPath(location.pathname));
}

/* -------------------------------------------------------- mobile drawer */

function closeSidebarDrawer() {
  const sidebar = $("#sidebar");
  const backdrop = $("#sidebar-backdrop");
  const openBtn = $("#sidebar-open-btn");
  if (sidebar) sidebar.classList.remove("is-open");
  if (backdrop) backdrop.hidden = true;
  if (openBtn) openBtn.setAttribute("aria-expanded", "false");
}

function openSidebarDrawer() {
  const sidebar = $("#sidebar");
  const backdrop = $("#sidebar-backdrop");
  const openBtn = $("#sidebar-open-btn");
  if (sidebar) sidebar.classList.add("is-open");
  if (backdrop) backdrop.hidden = false;
  if (openBtn) openBtn.setAttribute("aria-expanded", "true");
}

function initSidebarDrawer() {
  const openBtn = $("#sidebar-open-btn");
  const backdrop = $("#sidebar-backdrop");
  if (openBtn) {
    openBtn.addEventListener("click", () => {
      const sidebar = $("#sidebar");
      if (sidebar && sidebar.classList.contains("is-open")) closeSidebarDrawer();
      else openSidebarDrawer();
    });
  }
  if (backdrop) {
    backdrop.addEventListener("click", closeSidebarDrawer);
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSidebarDrawer();
  });
}

/* ---------------------------------------------------------------- init */

function renderStaticFooterLinks() {
  if (!PROJECT_DATA.meta || !PROJECT_DATA.meta.github_url) return;
  $$(".view-footer-github-link, #sidebar-github-link").forEach((link) => {
    link.href = PROJECT_DATA.meta.github_url;
    link.hidden = false;
  });
}

function init() {
  initTheme();
  initRouter();
  initSidebarDrawer();
  initChat();
  refreshLiveStatus();
  setInterval(refreshLiveStatus, 30000);

  renderMetricCards("dataset-cards", PROJECT_DATA.datasets);
  renderMetricCards("build-stage-cards", PROJECT_DATA.buildStages);
  renderMetricCards("gap-cards-runtime", PROJECT_DATA.integrationGap && PROJECT_DATA.integrationGap.liveRuntime);
  renderMetricCards("gap-cards-artifact", PROJECT_DATA.integrationGap && PROJECT_DATA.integrationGap.productionArtifact);
  renderMetricCards("evaluation-cards", PROJECT_DATA.evaluation);

  renderExperiments("experiments-container", PROJECT_DATA.experiments);

  initDeepArchitecture();

  renderGuardrails("guardrail-cards", PROJECT_DATA.guardrails);
  renderTimeline("project-timeline", PROJECT_DATA.timeline);

  if (PROJECT_DATA.roadmap) {
    renderRoadmapColumn("roadmap-complete", PROJECT_DATA.roadmap.completed);
    renderRoadmapColumn("roadmap-progress", PROJECT_DATA.roadmap.inProgress);
    renderRoadmapColumn("roadmap-deferred", PROJECT_DATA.roadmap.deferred);
  }

  renderStaticFooterLinks();

  const year = String(new Date().getFullYear());
  $$(".view-footer-year").forEach((n) => { n.textContent = year; });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
