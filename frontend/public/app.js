/* 나만의 AI 데이터 비서 — 바닐라 JS 프론트엔드 */
"use strict";

const API = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://localhost:8000").replace(/\/$/, "");
const UNIT = (window.APP_CONFIG && window.APP_CONFIG.DATA_UNIT) || "원";

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const state = {
  conversationId: null,
  sending: false,
  data: [],
  summary: null,
  stats: null,
};

/* ------------------------------------------------------------------ utils */
const fmt = (n) => (n == null ? "-" : Math.round(n).toLocaleString("ko-KR") + UNIT);
const fmtShort = (n) => {
  if (n == null) return "-";
  if (UNIT === "원" && Math.abs(n) >= 10000) {
    const man = n / 10000;
    return (man >= 100 ? Math.round(man).toLocaleString("ko-KR") : man.toFixed(1).replace(/\.0$/, "")) + "만원";
  }
  return fmt(n);
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); // 굵게만 간단 지원
const relTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso), diff = (Date.now() - d) / 1000;
  if (diff < 60) return "방금 전";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
};

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
}

/* ------------------------------------------------------------------ API */
async function api(path, { method = "GET", body, timeout = 60000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(API + path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(errorText(data, res.status));
    return data;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("서버 응답이 너무 늦어요. 잠시 후 다시 시도해 주세요.");
    if (e instanceof TypeError) throw new Error("서버에 연결할 수 없어요. (서버 주소 또는 CORS 설정 확인)");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
function errorText(data, status) {
  // FastAPI 422 검증 오류를 사람이 읽을 수 있게
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => `${(d.loc || []).slice(-1)[0] || ""}: ${d.msg.replace(/^Value error, /, "")}`).join(" / ");
  }
  return data.detail || `요청 실패 (${status})`;
}

/* ------------------------------------------------------------------ 서버 깨우기 (Render 콜드스타트 대응) */
async function wakeServer() {
  const status = $("#serverStatus");
  const banner = $("#wakeBanner");
  const slowTimer = setTimeout(() => banner.classList.remove("hidden"), 2500);
  for (let attempt = 0; attempt < 8; attempt++) {
    try {
      await api("/health", { timeout: 15000 });
      clearTimeout(slowTimer);
      banner.classList.add("hidden");
      status.className = "status ok";
      status.lastElementChild.textContent = "서버 연결됨";
      return true;
    } catch {
      status.lastElementChild.textContent = `서버 깨우는 중… (${attempt + 1})`;
      await new Promise((r) => setTimeout(r, 4000));
    }
  }
  clearTimeout(slowTimer);
  banner.classList.add("hidden");
  status.className = "status err";
  status.lastElementChild.textContent = "서버 연결 실패";
  toast("서버에 연결하지 못했어요. 새로고침해 주세요.");
  return false;
}

/* ------------------------------------------------------------------ 탭 / 테마 */
$$(".tab").forEach((b) =>
  b.addEventListener("click", () => {
    $$(".tab").forEach((x) => x.classList.toggle("active", x === b));
    $$(".view").forEach((v) => v.classList.toggle("hidden", v.id !== `view-${b.dataset.tab}`));
    requestAnimationFrame(b.dataset.tab === "data" ? drawChart : renderSummaryMini);
  })
);

$("#themeToggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("theme", next); } catch (e) {}
  drawChart();
  renderSummaryMini();
});

/* ------------------------------------------------------------------ 채팅 */
const messagesEl = $("#messages");
const input = $("#chatInput");

function addMessage(role, content, extra = {}) {
  $("#emptyState")?.remove();
  const div = document.createElement("div");
  div.className = `msg ${role}${extra.error ? " error" : ""}`;
  div.innerHTML = md(content);
  if (extra.tools && extra.tools.length) {
    const t = document.createElement("div");
    t.className = "tools";
    t.innerHTML = "🔧 호출한 도구: " + extra.tools
      .map((x) => `<code>${esc(x.name)}(${esc(Object.values(x.arguments || {}).join(" ~ "))})</code> ${esc(x.reason || "")}`)
      .join("<br>");
    div.appendChild(t);
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "msg assistant";
  div.innerHTML = `<span class="typing"><span></span><span></span><span></span><em>데이터를 살펴보는 중…</em></span>`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  // 콜드스타트 등으로 오래 걸리면 안내 문구 변경
  const t = setTimeout(() => { const em = div.querySelector("em"); if (em) em.textContent = "서버가 깨어나는 중일 수 있어요. 조금만 기다려 주세요…"; }, 8000);
  return () => { clearTimeout(t); div.remove(); };
}

async function sendMessage(text) {
  text = text.trim();
  if (!text || state.sending) return;
  state.sending = true;
  $("#sendBtn").disabled = true;
  input.value = "";
  autoGrow();
  addMessage("user", text);
  const hide = showTyping();
  try {
    const res = await api("/api/chat", {
      method: "POST",
      body: { message: text, conversation_id: state.conversationId, use_tools: $("#useTools").checked },
      timeout: 90000,
    });
    hide();
    addMessage("assistant", res.reply, { tools: res.tool_calls });
    const isNew = !state.conversationId;
    state.conversationId = res.conversation_id;
    if (isNew) $("#chatTitle").textContent = text.length > 30 ? text.slice(0, 30) + "…" : text;
    state.summary = res.summary_used;
    renderSummaryMini();
    loadConversations();
  } catch (e) {
    hide();
    addMessage("assistant", "⚠️ " + e.message, { error: true });
  } finally {
    state.sending = false;
    $("#sendBtn").disabled = false;
    input.focus();
  }
}

$("#chatForm").addEventListener("submit", (e) => { e.preventDefault(); sendMessage(input.value); });
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendMessage(input.value); }
});
function autoGrow() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; }
input.addEventListener("input", autoGrow);
messagesEl.addEventListener("click", (e) => { if (e.target.classList.contains("chip")) sendMessage(e.target.textContent); });

function resetChat() {
  state.conversationId = null;
  $("#chatTitle").textContent = "새 대화";
  messagesEl.innerHTML = `
    <div class="empty" id="emptyState">
      <p class="empty-title">무엇이든 물어보세요</p>
      <p class="muted">저장된 데이터 요약을 바탕으로 답해 드려요.</p>
      <div class="suggestions">
        <button class="chip">이번 달 실적이 어때?</button>
        <button class="chip">가장 실적이 좋았던 때는?</button>
        <button class="chip">무슨 요일에 제일 잘 팔려?</button>
        <button class="chip">지난 2주 흐름을 분석해줘</button>
      </div>
    </div>`;
  $$(".conv-item").forEach((x) => x.classList.remove("active"));
  input.focus();
}
$("#newChatBtn").addEventListener("click", resetChat);

/* ------------------------------------------------------------------ 대화 기록 */
async function loadConversations() {
  const list = $("#convList");
  try {
    const items = await api("/api/conversations");
    if (!items.length) { list.innerHTML = `<li class="muted small">아직 저장된 대화가 없어요.</li>`; return; }
    list.innerHTML = items.map((c) => `
      <li class="conv-item${c.id === state.conversationId ? " active" : ""}" data-id="${esc(c.id)}" title="${esc(c.preview)}">
        <div class="meta"><div class="t">${esc(c.title)}</div><div class="d">${relTime(c.updated_at)} · 메시지 ${c.message_count}개</div></div>
        <button class="del" data-del="${esc(c.id)}" aria-label="대화 삭제">✕</button>
      </li>`).join("");
  } catch (e) {
    list.innerHTML = `<li class="muted small">대화 목록을 불러오지 못했어요.</li>`;
  }
}

$("#convList").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del]");
  if (del) {
    e.stopPropagation();
    if (!confirm("이 대화를 삭제할까요?")) return;
    try {
      await api(`/api/conversations/${del.dataset.del}`, { method: "DELETE" });
      if (del.dataset.del === state.conversationId) resetChat();
      toast("대화를 삭제했어요.");
      loadConversations();
    } catch (err) { toast(err.message); }
    return;
  }
  const item = e.target.closest(".conv-item");
  if (item) openConversation(item.dataset.id);
});

async function openConversation(id) {
  try {
    const conv = await api(`/api/conversations/${id}`);
    state.conversationId = conv.id;
    $("#chatTitle").textContent = conv.title;
    messagesEl.innerHTML = "";
    if (!conv.messages.length) messagesEl.innerHTML = `<p class="muted">빈 대화입니다.</p>`;
    conv.messages.forEach((m) => addMessage(m.role, m.content));
    $$(".conv-item").forEach((x) => x.classList.toggle("active", x.dataset.id === id));
  } catch (e) { toast(e.message); }
}

/* ------------------------------------------------------------------ 요약 */
async function loadSummary() {
  try {
    state.summary = await api("/api/data/summary");
    renderSummaryMini();
  } catch (e) {
    $("#summaryMini").innerHTML = `<p class="muted small">요약을 불러오지 못했어요.</p>`;
  }
}

function renderSummaryMini() {
  const s = state.summary;
  const el = $("#summaryMini");
  if (!s) return;
  if (!s.count) { el.innerHTML = `<p class="muted small">데이터가 없어요. 데이터 관리 탭에서 추가해 주세요.</p>`; return; }
  const m = s.metrics;
  const last = s.monthly[s.monthly.length - 1];
  el.innerHTML = `
    <div class="kv"><span>기간</span><span>${esc(s.period)}</span></div>
    <div class="kv"><span>레코드</span><span>${s.count}개</span></div>
    <div class="kv"><span>합계</span><span>${fmtShort(m.total)}</span></div>
    <div class="kv"><span>평균</span><span>${fmtShort(m.average)}</span></div>
    <div class="kv"><span>최대</span><span>${fmtShort(m.max)} · ${m.max_date.slice(5)}</span></div>
    <div class="kv"><span>최소</span><span>${fmtShort(m.min)} · ${m.min_date.slice(5)}</span></div>
    ${last ? `<div class="kv"><span>최근 월 (${last.month})</span><span>${fmtShort(last.total)}</span></div>` : ""}
    <div class="trend-box">📈 ${esc(s.trend)}</div>
    <canvas class="spark" id="spark"></canvas>`;
  drawSpark(s.monthly.map((x) => x.average));
}

function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

function drawSpark(values) {
  const c = $("#spark");
  if (!c || values.length < 2) return;
  const dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight;
  c.width = w * dpr; c.height = h * dpr;
  const ctx = c.getContext("2d"); ctx.scale(dpr, dpr);
  const mn = Math.min(...values), mx = Math.max(...values), pad = 4;
  ctx.strokeStyle = cssVar("--chart-ma"); ctx.lineWidth = 2; ctx.beginPath();
  values.forEach((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - mn) / (mx - mn || 1)) * (h - pad * 2);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}

/* ------------------------------------------------------------------ 데이터 관리 */
async function loadData() {
  try {
    const [data, summary, stats] = await Promise.all([api("/api/data"), api("/api/data/summary"), api("/api/data/statistics")]);
    state.data = data; state.summary = summary; state.stats = stats;
    renderTable(); renderStatCards(); renderSummaryMini(); drawChart();
  } catch (e) {
    $("#dataBody").innerHTML = `<tr><td colspan="4" class="muted">${esc(e.message)}</td></tr>`;
  }
}

function renderStatCards() {
  const s = state.summary, st = state.stats;
  if (!s || !s.count) { $("#statCards").innerHTML = ""; return; }
  const m = s.metrics, last = s.monthly[s.monthly.length - 1];
  const cards = [
    ["기간", `${s.count}일`, s.period],
    ["합계", fmtShort(m.total), `평균 ${fmtShort(m.average)}`],
    ["최고", fmtShort(m.max), m.max_date],
    ["최저", fmtShort(m.min), m.min_date],
    ["최근 월", fmtShort(last.total), `${last.month} · 전월 대비 ${st.mom_change_pct == null ? "-" : (st.mom_change_pct > 0 ? "+" : "") + st.mom_change_pct + "%"}`],
  ];
  $("#statCards").innerHTML = cards.map(([l, v, sub]) => `<div class="stat"><div class="l">${l}</div><div class="v">${v}</div><div class="s">${esc(sub)}</div></div>`).join("");
  const wd = Object.entries(st.weekday_avg || {});
  const best = wd.sort((a, b) => b[1] - a[1])[0];
  $("#extraStats").innerHTML = `
    <span>추세 <b>${esc(s.trend)}</b></span>
    <span>중앙값 <b>${fmtShort(st.median)}</b></span>
    <span>표준편차 <b>${fmtShort(st.std_dev)}</b></span>
    ${best ? `<span>최고 요일 <b>${best[0]}요일 (${fmtShort(best[1])})</b></span>` : ""}
    ${st.best_month ? `<span>최고 월(일평균) <b>${st.best_month}</b></span>` : ""}`;
}

function renderTable(flashId) {
  const q = $("#filter").value.trim();
  const rows = state.data.slice().reverse().filter((r) => !q || r.date.includes(q) || (r.memo || "").includes(q));
  $("#dataCount").textContent = `(${state.data.length}개${q ? `, 검색 ${rows.length}개` : ""})`;
  $("#dataBody").innerHTML = rows.length
    ? rows.map((r) => `
      <tr data-id="${esc(r.id)}"${r.id === flashId ? ' class="flash"' : ""}>
        <td>${esc(r.date)}</td><td class="num">${fmt(r.value)}</td><td>${esc(r.memo)}</td>
        <td class="act"><button class="btn ghost sm" data-edit="${esc(r.id)}">수정</button> <button class="btn ghost sm danger" data-remove="${esc(r.id)}">삭제</button></td>
      </tr>`).join("")
    : `<tr><td colspan="4" class="muted">데이터가 없어요.</td></tr>`;
}
$("#filter").addEventListener("input", () => renderTable());

$("#dataBody").addEventListener("click", async (e) => {
  const edit = e.target.closest("[data-edit]");
  const rm = e.target.closest("[data-remove]");
  if (edit) {
    const r = state.data.find((x) => x.id === edit.dataset.edit);
    $("#editId").value = r.id; $("#fDate").value = r.date; $("#fValue").value = r.value; $("#fMemo").value = r.memo || "";
    $("#formTitle").textContent = "데이터 수정"; $("#formSubmit").textContent = "수정 저장";
    $("#formCancel").classList.remove("hidden");
    $("#fValue").focus();
  }
  if (rm) {
    const r = state.data.find((x) => x.id === rm.dataset.remove);
    if (!confirm(`${r.date} (${fmt(r.value)}) 데이터를 삭제할까요?`)) return;
    try {
      await api(`/api/data/${r.id}`, { method: "DELETE" });
      toast("삭제했어요.");
      await loadData();
    } catch (err) { toast(err.message); }
  }
});

function resetForm() {
  $("#dataForm").reset(); $("#editId").value = "";
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset()); // 로컬 날짜
  $("#fDate").value = now.toISOString().slice(0, 10);
  $("#formTitle").textContent = "새 데이터 추가"; $("#formSubmit").textContent = "추가";
  $("#formCancel").classList.add("hidden");
}
$("#formCancel").addEventListener("click", resetForm);

$("#dataForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("#formMsg");
  const id = $("#editId").value;
  const body = { date: $("#fDate").value, value: Number($("#fValue").value), memo: $("#fMemo").value.trim() };
  if (!body.date || Number.isNaN(body.value) || body.value < 0) {
    msg.className = "form-msg err"; msg.textContent = "날짜와 0 이상의 값을 입력해 주세요."; return;
  }
  $("#formSubmit").disabled = true;
  try {
    const saved = await api(id ? `/api/data/${id}` : "/api/data", { method: id ? "PUT" : "POST", body });
    msg.className = "form-msg ok";
    msg.textContent = id ? `✓ ${saved.date} 데이터를 수정했어요.` : `✓ ${saved.date} · ${fmt(saved.value)} 저장 완료 (id: ${saved.id.slice(0, 8)}…)`;
    resetForm();
    await loadData();
    renderTable(saved.id);
  } catch (err) {
    msg.className = "form-msg err"; msg.textContent = "저장 실패: " + err.message;
  } finally {
    $("#formSubmit").disabled = false;
  }
});

/* 내보내기: 서버 export 엔드포인트를 받아 파일로 저장 */
$$("[data-export]").forEach((b) => b.addEventListener("click", async () => {
  const f = b.dataset.export;
  try {
    const res = await fetch(`${API}/api/data/export?format=${f}`);
    if (!res.ok) throw new Error("내보내기 실패");
    const blob = await res.blob();
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `my-data-${new Date().toISOString().slice(0, 10)}.${f}` });
    a.click(); URL.revokeObjectURL(a.href);
  } catch (e) { toast(e.message); }
}));

/* ------------------------------------------------------------------ 차트 (Canvas, 라이브러리 없음) */
let chartPoints = [];
function drawChart() {
  const c = $("#chart");
  if (!c || !c.clientWidth || !state.data.length) return;
  const dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = 260;
  c.width = w * dpr; c.height = h * dpr; c.style.height = h + "px";
  const ctx = c.getContext("2d"); ctx.scale(dpr, dpr);
  const pad = { l: 56, r: 12, t: 12, b: 28 };
  const data = state.data, ma = (state.stats && state.stats.moving_avg_7) || [];
  const vals = data.map((d) => d.value);
  const mx = Math.max(...vals) * 1.05, mn = 0;
  const X = (i) => pad.l + (data.length === 1 ? 0.5 : i / (data.length - 1)) * (w - pad.l - pad.r);
  const Y = (v) => h - pad.b - ((v - mn) / (mx - mn || 1)) * (h - pad.t - pad.b);

  ctx.font = "11px Pretendard Variable, system-ui, sans-serif";
  ctx.fillStyle = cssVar("--muted"); ctx.strokeStyle = cssVar("--border"); ctx.lineWidth = 1;
  for (let k = 0; k <= 4; k++) {
    const v = mn + (mx - mn) * (k / 4), y = Y(v);
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
    ctx.textAlign = "right"; ctx.fillText(fmtShort(v), pad.l - 6, y + 4);
  }
  ctx.textAlign = "center";
  let lastMonth = "", lastX = -999;
  data.forEach((d, i) => {
    const m = d.date.slice(0, 7);
    if (m !== lastMonth) {
      lastMonth = m;
      if (X(i) - lastX > 34) { ctx.fillText(`${Number(m.slice(5))}월`, X(i), h - 8); lastX = X(i); }
    }
  });

  ctx.strokeStyle = cssVar("--chart-raw"); ctx.lineWidth = 1.2; ctx.beginPath();
  data.forEach((d, i) => (i ? ctx.lineTo(X(i), Y(d.value)) : ctx.moveTo(X(i), Y(d.value))));
  ctx.stroke();

  if (ma.length === data.length) {
    ctx.strokeStyle = cssVar("--chart-ma"); ctx.lineWidth = 2.4; ctx.beginPath();
    ma.forEach((d, i) => (i ? ctx.lineTo(X(i), Y(d.value)) : ctx.moveTo(X(i), Y(d.value))));
    ctx.stroke();
  }
  chartPoints = data.map((d, i) => ({ x: X(i), y: Y(d.value), d, ma: ma[i] && ma[i].value }));
}

$("#chart").addEventListener("mousemove", (e) => {
  if (!chartPoints.length) return;
  const rect = e.target.getBoundingClientRect(), x = e.clientX - rect.left;
  let best = chartPoints[0];
  for (const p of chartPoints) if (Math.abs(p.x - x) < Math.abs(best.x - x)) best = p;
  const tip = $("#tooltip");
  tip.innerHTML = `<b>${best.d.date}</b> ${fmt(best.d.value)}${best.ma ? ` · 7일평균 ${fmtShort(best.ma)}` : ""}${best.d.memo ? `<br>${esc(best.d.memo)}` : ""}`;
  tip.style.left = best.x + "px"; tip.style.top = best.y + "px";
  tip.classList.remove("hidden");
});
$("#chart").addEventListener("mouseleave", () => $("#tooltip").classList.add("hidden"));
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawChart, 150); });

/* ------------------------------------------------------------------ 시작 */
(async function init() {
  if (window.APP_CONFIG && window.APP_CONFIG.DATA_NAME) $("#dataName").textContent = `${window.APP_CONFIG.DATA_NAME} 데이터를 아는 AI`;
  resetForm();
  const ok = await wakeServer();
  if (!ok) return;
  loadSummary();
  loadConversations();
  loadData();
})();
