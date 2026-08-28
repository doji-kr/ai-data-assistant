"use strict";
const API = window.API_BASE_URL || "";
const $ = (s) => document.querySelector(s);

let conversationId = null;
let history = []; // {role, content}

// ---------- 공통 ----------
async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

// ---------- 다크 모드 ----------
const themeBtn = $("#theme-toggle");
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  themeBtn.textContent = t === "dark" ? "☀️" : "🌙";
  try { localStorage.setItem("theme", t); } catch {}
}
themeBtn.onclick = () =>
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
try { applyTheme(localStorage.getItem("theme") || "light"); } catch { applyTheme("light"); }

// ---------- 요약 + 차트 ----------
async function loadSummary() {
  const s = await api("/api/data/summary");
  if (!s.count) { $("#summary-body").textContent = "데이터가 없습니다."; return; }
  const m = s.metrics;
  $("#summary-body").innerHTML = `
    <div class="stat"><b>${s.period}</b><span>기간 · ${s.count}일</span></div>
    <div class="stat"><b>${m.average}</b><span>일평균 (최대 ${m.max} / 최소 ${m.min})</span></div>
    <div class="stat"><b>${s.moving_average_7d}</b><span>최근 7일 이동평균</span></div>
    <div class="stat"><b>${s.trend}</b><span>추세 · 최다 요일 ${s.best_weekday}</span></div>`;
}

let chartRows = [];
const chartOpt = { range: "all", unit: "day" };

async function loadChart() {
  chartRows = await api("/api/data");
  renderChart();
}

function renderChart() {
  let pts = chartRows.map((r) => ({ x: r.date, y: Number(r.value) }));
  if (chartOpt.range !== "all") pts = pts.slice(-Number(chartOpt.range));
  if (chartOpt.unit === "week") {
    const weeks = new Map(); // ISO 주 시작일(월요일) → 합계
    for (const p of pts) {
      const d = new Date(p.x + "T00:00:00Z");
      d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
      const k = d.toISOString().slice(0, 10);
      weeks.set(k, (weeks.get(k) || 0) + p.y);
    }
    pts = [...weeks].map(([x, y]) => ({ x, y }));
  }
  drawChart($("#chart"), pts, chartOpt.unit === "week" ? 1 : 7);
}

document.querySelectorAll("#chart-controls .ctl-group").forEach((g) => {
  const key = g.dataset.key;
  const btns = g.querySelectorAll("button");
  const sync = () => btns.forEach((b) => b.classList.toggle("active", b.dataset.v === chartOpt[key]));
  btns.forEach((b) => (b.onclick = () => { chartOpt[key] = b.dataset.v; sync(); renderChart(); }));
  sync();
});

function drawChart(canvas, pts, maWindow = 7) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height, P = 34;
  ctx.clearRect(0, 0, W, H);
  if (pts.length < 2) return;
  const ys = pts.map((p) => p.y), ymax = Math.max(...ys) || 1;
  const x = (i) => P + (i / (pts.length - 1)) * (W - P * 2);
  const y = (v) => H - P - (v / ymax) * (H - P * 2);
  const css = getComputedStyle(document.documentElement);
  ctx.strokeStyle = css.getPropertyValue("--border"); ctx.lineWidth = 1;
  ctx.strokeRect(P, P, W - P * 2, H - P * 2);
  ctx.fillStyle = css.getPropertyValue("--muted"); ctx.font = "11px sans-serif";
  ctx.fillText(String(ymax), 4, y(ymax) + 4);
  ctx.fillText("0", 4, y(0) + 4);
  ctx.fillText(pts[0].x, P, H - 12);
  ctx.fillText(pts[pts.length - 1].x, W - P - 62, H - 12);
  // 원계열
  ctx.strokeStyle = css.getPropertyValue("--accent"); ctx.lineWidth = 1.2;
  ctx.globalAlpha = 0.45; ctx.beginPath();
  pts.forEach((p, i) => (i ? ctx.lineTo(x(i), y(p.y)) : ctx.moveTo(x(i), y(p.y))));
  ctx.stroke(); ctx.globalAlpha = 1;
  // 이동평균 (일 단위 7일 / 주 단위는 원계열 그대로)
  ctx.lineWidth = 2; ctx.beginPath();
  pts.forEach((p, i) => {
    const w = pts.slice(Math.max(0, i - maWindow + 1), i + 1);
    const v = w.reduce((a, q) => a + q.y, 0) / w.length;
    i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v));
  });
  ctx.stroke();
}

$("#export-csv").onclick = () => { location.href = API + "/api/data/export.csv"; };

// ---------- 채팅 ----------
function addMsg(role, text, cls = "") {
  const div = document.createElement("div");
  div.className = `msg ${role} ${cls}`;
  div.textContent = text;
  $("#chat-log").appendChild(div);
  $("#chat-log").scrollTop = $("#chat-log").scrollHeight;
  return div;
}

$("#chat-form").onsubmit = async (e) => {
  e.preventDefault();
  const input = $("#chat-input"), btn = $("#chat-send");
  const text = input.value.trim();
  if (!text) return;
  input.value = ""; input.disabled = btn.disabled = true;
  addMsg("user", text);
  const loading = addMsg("assistant", "생각 중…", "loading");
  try {
    const r = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, conversation_id: conversationId, history }),
    });
    loading.remove();
    addMsg("assistant", r.reply);
    conversationId = r.conversation_id;
    history.push({ role: "user", content: text }, { role: "assistant", content: r.reply });
    $("#chat-status").textContent = r.used_tools.length ? `도구 호출: ${r.used_tools.join(", ")}` : "";
    loadConversations();
  } catch (err) {
    loading.remove();
    addMsg("assistant", `⚠️ ${err.message}`);
  } finally {
    input.disabled = btn.disabled = false; input.focus();
  }
};

// ---------- 대화 기록 ----------
async function loadConversations() {
  const list = await api("/api/conversations");
  const ul = $("#conv-list");
  ul.innerHTML = "";
  if (!list.length) { ul.innerHTML = "<li class='meta'>저장된 대화가 없습니다.</li>"; return; }
  for (const c of list) {
    const li = document.createElement("li");
    const when = (c.created_at || "").slice(0, 16).replace("T", " ");
    li.innerHTML = `<button class="load"></button>
      <span class="meta">${when} · ${c.message_count}개</span>
      <button class="ghost del">삭제</button>`;
    li.querySelector(".load").textContent = c.title || "(제목 없음)";
    li.querySelector(".load").onclick = () => loadConversation(c.id);
    li.querySelector(".del").onclick = async () => {
      await api(`/api/conversations/${c.id}`, { method: "DELETE" });
      if (conversationId === c.id) { conversationId = null; history = []; $("#chat-log").innerHTML = ""; }
      loadConversations();
    };
    ul.appendChild(li);
  }
}

async function loadConversation(id) {
  const c = await api(`/api/conversations/${id}`);
  conversationId = c.id;
  history = c.messages.map((m) => ({ role: m.role, content: m.content }));
  $("#chat-log").innerHTML = "";
  c.messages.forEach((m) => addMsg(m.role, m.content));
  $("#chat-status").textContent = `불러온 대화: ${c.title}`;
}

// ---------- 데이터 관리 ----------
async function loadData() {
  const rows = await api("/api/data");
  const tb = $("#data-table tbody");
  tb.innerHTML = "";
  for (const r of [...rows].reverse()) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.date}</td><td>${r.value}</td><td></td>
      <td><button class="ghost edit">수정</button> <button class="ghost del">삭제</button></td>`;
    tr.children[2].textContent = r.memo || "";
    tr.querySelector(".del").onclick = async () => {
      await api(`/api/data/${r.id}`, { method: "DELETE" });
      refreshAll();
    };
    tr.querySelector(".edit").onclick = async () => {
      const v = prompt(`${r.date} 값 수정`, r.value);
      if (v === null) return;
      await api(`/api/data/${r.id}`, {
        method: "PUT",
        body: JSON.stringify({ date: r.date, value: Number(v), memo: r.memo }),
      });
      refreshAll();
    };
    tb.appendChild(tr);
  }
}

$("#data-form").onsubmit = async (e) => {
  e.preventDefault();
  await api("/api/data", {
    method: "POST",
    body: JSON.stringify({
      date: $("#d-date").value,
      value: Number($("#d-value").value),
      memo: $("#d-memo").value || null,
    }),
  });
  e.target.reset();
  refreshAll();
};

function refreshAll() {
  Promise.all([loadSummary(), loadChart(), loadData()]).catch((err) => {
    $("#summary-body").textContent = `⚠️ ${err.message}`;
  });
}
refreshAll();
loadConversations().catch(() => {});
