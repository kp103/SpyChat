"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = { username: null, profile: null, hideFile: null, revealFile: null, capacity: 0, selectedChat: null, authMode: "login" };

// ---- API helpers ----------------------------------------------------------

async function api(path, opts = {}) {
  // CSRF: a custom header browsers won't add on cross-origin form posts.
  opts.headers = Object.assign({ "X-Requested-With": "SpyChat" }, opts.headers || {});
  const res = await fetch(path, opts);
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) {
    let msg = "Request failed";
    if (ct.includes("application/json")) msg = (await res.json()).error || msg;
    const err = new Error(msg); err.status = res.status; throw err;
  }
  return ct.includes("application/json") ? res.json() : res.blob();
}

function jpost(path, body) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

// ---- Toasts ----------------------------------------------------------------

function toast(message, kind = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = (kind === "ok" ? "✓  " : "✕  ") + message;
  $("#toast-stack").appendChild(el);
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 250);
  }, 3200);
}

// ---- Rendering -------------------------------------------------------------

function initials(name) { return (name || "?").trim().charAt(0).toUpperCase() || "?"; }

function render() {
  // State machine: not signed in -> auth; signed in but no spy -> onboarding; else app.
  if (!state.username) {
    $("#auth").classList.remove("hidden");
    $("#onboarding").classList.add("hidden");
    $("#app").classList.add("hidden");
    return;
  }
  $("#auth").classList.add("hidden");
  const p = state.profile;
  if (!p || !p.spy) {
    $("#onboarding").classList.remove("hidden");
    $("#app").classList.add("hidden");
    return;
  }
  $("#onboarding").classList.add("hidden");
  $("#app").classList.remove("hidden");

  $("#spy-name").textContent = p.spy.display_name;
  $("#spy-status").textContent = p.spy.current_status_message || "—";
  $("#spy-avatar").textContent = initials(p.spy.name);
  $("#status-input").value = p.spy.current_status_message || "";

  // Friend dropdowns
  const opts = '<option value="">— none —</option>' +
    p.friends.map((f, i) => `<option value="${i}">${escapeHtml(f.display_name)}</option>`).join("");
  $("#hide-friend").innerHTML = opts;
  $("#reveal-friend").innerHTML = opts;

  renderFriends();
  renderChatContacts();
  renderIdentity();
}

function renderFriends() {
  const list = $("#friends-list");
  const p = state.profile;
  if (!p.friends.length) { list.innerHTML = '<div class="empty-note">No friends yet. Recruit one →</div>'; return; }
  list.innerHTML = p.friends.map((f, i) => `
    <div class="friend-row">
      <div class="dot"></div>
      <div class="friend-meta"><div class="fn">${escapeHtml(f.display_name)}</div>
        <div class="fd">age ${f.age} · rating ${f.rating.toFixed(2)}</div></div>
      <button class="btn ghost-danger" data-remove="${i}">Remove</button>
    </div>`).join("");
  $$("[data-remove]", list).forEach(b => b.onclick = () => removeFriend(b.dataset.remove));
}

function renderChatContacts() {
  const el = $("#chat-contacts");
  const p = state.profile;
  if (!p.friends.length) { el.innerHTML = '<div class="empty-note">No contacts.</div>'; return; }
  el.innerHTML = p.friends.map((f, i) => `
    <div class="friend-row clickable ${state.selectedChat === i ? "selected" : ""}" data-chat="${i}">
      <div class="dot"></div>
      <div class="friend-meta"><div class="fn">${escapeHtml(f.display_name)}</div>
        <div class="fd">${f.chats.length} message(s)</div></div>
    </div>`).join("");
  $$("[data-chat]", el).forEach(r => r.onclick = () => { state.selectedChat = +r.dataset.chat; renderChatContacts(); renderThread(); });
  if (state.selectedChat !== null) renderThread();
}

function renderThread() {
  const i = state.selectedChat;
  const f = state.profile.friends[i];
  if (!f) { $("#chat-title").textContent = "Select a contact"; $("#chat-thread").innerHTML = ""; return; }
  $("#chat-title").textContent = f.display_name;
  const thread = $("#chat-thread");
  if (!f.chats.length) { thread.innerHTML = '<div class="empty-note">No messages yet.</div>'; return; }
  thread.innerHTML = f.chats.map(c => {
    const t = new Date(c.time).toLocaleString();
    return `<div class="bubble ${c.is_sent_by_me ? "me" : "them"}">${escapeHtml(c.message)}<span class="ts">${t}</span></div>`;
  }).join("");
  thread.scrollTop = thread.scrollHeight;
}

function renderIdentity() {
  const s = state.profile.spy;
  $("#identity-info").innerHTML = `
    <div class="ii"><span>Codename</span><span>${escapeHtml(s.name)}</span></div>
    <div class="ii"><span>Title</span><span>${escapeHtml(s.salutation)}</span></div>
    <div class="ii"><span>Age</span><span>${s.age}</span></div>
    <div class="ii"><span>Rating</span><span>${s.rating.toFixed(2)}</span></div>
    <div class="ii"><span>Friends</span><span>${state.profile.friends.length}</span></div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---- Navigation ------------------------------------------------------------

$$(".nav-item").forEach(btn => btn.onclick = () => {
  $$(".nav-item").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  $$(".view").forEach(v => v.classList.toggle("active", v.dataset.view === btn.dataset.view));
});

// ---- Auth ------------------------------------------------------------------

function setAuthMode(mode) {
  state.authMode = mode;
  const login = mode === "login";
  $("#tab-login").classList.toggle("active", login);
  $("#tab-register").classList.toggle("active", !login);
  $("#tab-login").setAttribute("aria-selected", String(login));
  $("#tab-register").setAttribute("aria-selected", String(!login));
  $("#auth-submit").textContent = login ? "Sign in ↗" : "Create identity ↗";
  $("#auth-hint").classList.toggle("hidden", login);
  $("#auth-pass").setAttribute("autocomplete", login ? "current-password" : "new-password");
}
$("#tab-login").onclick = () => setAuthMode("login");
$("#tab-register").onclick = () => setAuthMode("register");

$("#auth-form").onsubmit = async (e) => {
  e.preventDefault();
  const username = $("#auth-user").value, password = $("#auth-pass").value;
  const path = state.authMode === "login" ? "/api/login" : "/api/register";
  try {
    const r = await jpost(path, { username, password });
    state.username = r.username;
    $("#auth-pass").value = "";
    toast(state.authMode === "login" ? "Welcome back, spy." : "Identity created.");
    await refresh();
  } catch (err) { toast(err.message, "err"); }
};

$("#logout-btn").onclick = async () => {
  try { await api("/api/logout", { method: "POST" }); } catch (_) {}
  state.username = null; state.profile = null; state.selectedChat = null;
  setAuthMode("login");
  render();
  toast("Signed out.");
};

// ---- Onboarding ------------------------------------------------------------

$("#spy-form").onsubmit = async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    state.profile = await jpost("/api/spy", {
      name: fd.get("name"), salutation: fd.get("salutation"),
      age: fd.get("age"), rating: fd.get("rating"),
    });
    toast("Welcome aboard, spy.");
    render();
  } catch (err) { toast(err.message, "err"); }
};

// ---- Dropzones -------------------------------------------------------------

function wireDrop(zoneId, fileId, previewId, emptyId, onFile) {
  const zone = $("#" + zoneId), input = $("#" + fileId);
  zone.onclick = () => input.click();
  input.onchange = () => input.files[0] && handle(input.files[0]);
  ["dragover", "dragenter"].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove("drag"); }));
  zone.addEventListener("drop", e => { const f = e.dataTransfer.files[0]; if (f) handle(f); });
  function handle(file) {
    if (!file.type.startsWith("image/")) { toast("Please choose an image file.", "err"); return; }
    const url = URL.createObjectURL(file);
    $("#" + previewId).src = url;
    $("#" + previewId).classList.remove("hidden");
    $("#" + emptyId).classList.add("hidden");
    onFile(file);
  }
}

wireDrop("hide-drop", "hide-file", "hide-preview", "hide-drop-empty", async (file) => {
  state.hideFile = file;
  $("#hide-btn").disabled = false;
  // Fetch capacity
  const fd = new FormData(); fd.append("image", file);
  try {
    const cap = await api("/api/capacity", { method: "POST", body: fd });
    state.capacity = cap.capacity_bytes;
    $("#capacity-wrap").classList.remove("hidden");
    $("#capacity-max").textContent = cap.capacity_bytes;
    updateCapacity();
  } catch (err) { toast(err.message, "err"); }
});

wireDrop("reveal-drop", "reveal-file", "reveal-preview", "reveal-drop-empty", (file) => {
  state.revealFile = file;
  $("#reveal-btn").disabled = false;
});

// ---- Capacity meter --------------------------------------------------------

function updateCapacity() {
  const used = new Blob([$("#hide-message").value]).size;
  const max = state.capacity || 1;
  const pct = Math.min(100, (used / max) * 100);
  const fill = $("#capacity-fill");
  fill.style.width = pct + "%";
  fill.classList.toggle("warn", pct > 75 && pct <= 100);
  fill.classList.toggle("over", used > max);
  $("#capacity-used").textContent = used;
  $("#hide-btn").disabled = !state.hideFile || used === 0 || used > max;
}
$("#hide-message").oninput = updateCapacity;

// ---- Encryption toggle -----------------------------------------------------

$("#hide-encrypt").onchange = (e) => $("#hide-pass").classList.toggle("hidden", !e.target.checked);

// ---- Hide ------------------------------------------------------------------

$("#hide-btn").onclick = async () => {
  if (!state.hideFile) return;
  const encrypt = $("#hide-encrypt").checked;
  const pass = $("#hide-pass").value;
  if (encrypt && !pass) { toast("Enter a passphrase or turn off encryption.", "err"); return; }

  const fd = new FormData();
  fd.append("image", state.hideFile);
  fd.append("message", $("#hide-message").value);
  if (encrypt) fd.append("passphrase", pass);
  fd.append("friend_index", $("#hide-friend").value);

  const btn = $("#hide-btn"); btn.disabled = true; btn.textContent = "Hiding…";
  try {
    const blob = await api("/api/encode", { method: "POST", body: fd });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "secret_message.png"; a.click();
    URL.revokeObjectURL(url);
    toast(encrypt ? "Encrypted & hidden. PNG downloaded." : "Hidden. PNG downloaded.");
    await refresh();
  } catch (err) { toast(err.message, "err"); }
  finally { btn.disabled = false; btn.textContent = "Hide & download PNG ↓"; }
};

// ---- Reveal ----------------------------------------------------------------

$("#reveal-btn").onclick = async () => {
  if (!state.revealFile) return;
  const fd = new FormData();
  fd.append("image", state.revealFile);
  fd.append("passphrase", $("#reveal-pass").value);
  fd.append("friend_index", $("#reveal-friend").value);

  const btn = $("#reveal-btn"); btn.disabled = true; btn.textContent = "Revealing…";
  try {
    const r = await api("/api/decode", { method: "POST", body: fd });
    const badges = [];
    if (r.was_encrypted) badges.push('<span class="badge enc">🔒 Decrypted</span>');
    if (r.is_special) badges.push('<span class="badge special">⚡ Special message</span>');
    if (r.terminated) badges.push('<span class="badge term">☠ Friend terminated</span>');
    $("#reveal-result").innerHTML =
      `<div class="decoded">${escapeHtml(r.text)}</div>` +
      (badges.length ? `<div class="badges">${badges.join("")}</div>` : "");
    $("#reveal-result").classList.remove("hidden");
    toast("Message revealed.");
    await refresh();
  } catch (err) {
    $("#reveal-result").classList.add("hidden");
    toast(err.message, "err");
  } finally { btn.disabled = false; btn.textContent = "Reveal message →"; }
};

// ---- Friends ---------------------------------------------------------------

$("#friend-add").onclick = async () => {
  try {
    state.profile = await jpost("/api/friends", {
      name: $("#friend-name").value, salutation: $("#friend-sal").value,
      age: $("#friend-age").value, rating: $("#friend-rating").value,
    });
    $("#friend-name").value = "";
    toast("Friend recruited.");
    render();
  } catch (err) { toast(err.message, "err"); }
};

async function removeFriend(i) {
  try {
    state.profile = await api(`/api/friends/${i}`, { method: "DELETE" });
    if (state.selectedChat !== null) state.selectedChat = null;
    toast("Friend removed.");
    render();
  } catch (err) { toast(err.message, "err"); }
}

// ---- Status ----------------------------------------------------------------

$("#status-save").onclick = async () => {
  try {
    state.profile = await jpost("/api/status", { message: $("#status-input").value });
    toast("Status updated.");
    render();
  } catch (err) { toast(err.message, "err"); }
};

// ---- Boot ------------------------------------------------------------------

async function refresh() {
  try {
    state.profile = await api("/api/profile");
  } catch (err) {
    if (err.status === 401) { state.username = null; render(); return; }
    throw err;
  }
  render();
}

(async function boot() {
  setAuthMode("login");
  try {
    const me = await api("/api/me");
    state.username = me.username;
    if (state.username) await refresh();
    else render();
  } catch (err) {
    render();
    toast("Could not reach the server.", "err");
  }
})();
