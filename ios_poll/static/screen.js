"use strict";

const byId = (id) => document.getElementById(id);
let latestSession = null;
let latestVersion = -1;
let axisMax = 30;
let streamConnected = false;

function votesLabel(count) {
  return count + " " + (count % 10 === 1 && count % 100 !== 11 ? "голос" :
    count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14) ? "голоса" : "голосов");
}

function setConnection(ok, label) {
  const node = byId("connection-status");
  node.textContent = label;
  node.classList.toggle("offline", !ok);
}

function drawCategory(key, state) {
  const votes = state.results[key].votes;
  const percent = state.results[key].percentage;
  byId(key + "-percent").textContent = percent.toFixed(1) + "%";
  byId(key + "-votes").textContent = votesLabel(votes);
  const bar = byId(key + "-bar");
  bar.style.height = (100 * votes / axisMax).toFixed(3) + "%";
  bar.setAttribute("aria-label", (key === "ios" ? "iOS" : "Android") + ": " + votesLabel(votes));
}

function applySnapshot(state) {
  if (!state || !state.results || typeof state.total !== "number") return;
  if (state.session_id === latestSession && state.version < latestVersion) return;
  if (state.session_id !== latestSession) {
    latestSession = state.session_id;
    axisMax = 30;
  }
  latestVersion = state.version;
  const highest = Math.max(state.results.ios.votes, state.results.android.votes);
  if (highest >= axisMax) {
    axisMax = Math.ceil((highest * 1.25 + 1) / 10) * 10;
  }
  drawCategory("ios", state);
  drawCategory("android", state);
  byId("total").textContent = state.total;
  byId("other").textContent = state.results.other.votes;
  byId("scale").textContent = "0–" + axisMax;

  const status = byId("poll-status");
  status.className = "";
  if (state.status === "OPEN") {
    status.classList.add("open");
    status.textContent = "● Голосование идёт";
  } else if (state.status === "CLOSED") {
    status.classList.add("closed");
    status.textContent = "✓ Голосование завершено";
  } else {
    status.textContent = "Ожидаем начала голосования";
  }
}

async function loadSnapshot() {
  try {
    const response = await fetch("/api/results", { cache: "no-store" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    applySnapshot(await response.json());
    if (!streamConnected) setConnection(true, "Данные обновлены · резервный режим");
  } catch (_) {
    if (!streamConnected) setConnection(false, "Нет соединения · показаны последние данные");
  }
}

function connect() {
  if (typeof EventSource === "undefined") {
    setConnection(false, "SSE недоступен · резервный режим");
    return;
  }
  const events = new EventSource("/api/events");
  events.onopen = () => {
    streamConnected = true;
    setConnection(true, "● Подключено · онлайн");
  };
  events.onerror = () => {
    streamConnected = false;
    setConnection(false, "Нет связи · переподключение…");
  };
  function consume(event) {
    try { applySnapshot(JSON.parse(event.data)); } catch (_) { /* keep last known results */ }
  }
  events.addEventListener("results_updated", consume);
  events.addEventListener("poll_closed", consume);
  window.addEventListener("pagehide", () => events.close(), { once: true });
}

loadSnapshot();
connect();
// Recover when SSE is filtered by a proxy; avoid extra requests while it works.
setInterval(() => { if (!streamConnected) loadSnapshot(); }, 4000);
