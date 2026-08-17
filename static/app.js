const $ = (id) => document.getElementById(id);
const els = ["gear", "pick", "folder", "name", "rename", "progress", "empty", "grid", "toast", "undo", "stat",
  "settings", "key", "model", "custom", "keymsg", "test", "cancel", "save"].reduce((o, k) => (o[k] = $(k), o), {});
let items = [], status = {}, journal = null, toastTimer = null;
const MODEL_LABELS = {
  "google/gemini-2.5-flash": "Gemini 2.5 Flash", "google/gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite",
  "openai/gpt-4o-mini": "GPT-4o mini", "anthropic/claude-sonnet-4": "Claude Sonnet",
};

async function api(path, body) {
  const r = await fetch("/api/" + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function toast(msg, opts = {}) {
  clearTimeout(toastTimer);
  els.toast.firstElementChild.textContent = msg;
  els.toast.classList.toggle("error", !!opts.error);
  els.undo.hidden = !opts.undo;
  els.toast.hidden = false;
  toastTimer = setTimeout(() => (els.toast.hidden = true), opts.undo ? 12000 : 3500);
}

const stem = (name) => name.replace(/\.[^.]+$/, "");
const inputs = () => [...els.grid.querySelectorAll("input.name")];

function render() {
  els.grid.innerHTML = "";
  els.empty.hidden = items.length > 0;
  els.empty.firstElementChild.textContent = "Nothing to rename";
  els.empty.lastElementChild.textContent = "No supported files in that folder (png, jpg, webp, mp4, mov).";
  items.forEach((it, n) => {
    const card = document.createElement("article");
    card.className = "card";
    card.dataset.id = it.id;
    card.style.setProperty("--i", n);
    card.innerHTML = `<div class="thumb"><img alt=""><span class="idx">${String(n + 1).padStart(2, "0")}</span>${it.kind === "video" ? '<span class="kind">VIDEO</span>' : ""}</div>
      <div class="meta"><div class="orig"></div><input class="name" spellcheck="false" placeholder="—" aria-label="New name"></div>`;
    if (it.thumb) card.querySelector("img").src = "data:image/jpeg;base64," + it.thumb;
    card.querySelector(".orig").textContent = card.querySelector(".orig").title = it.name;
    const inp = card.querySelector("input");
    inp.value = stem(it.name);
    inp.addEventListener("input", () => updateChanged(inp, it));
    inp.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" || e.metaKey || e.ctrlKey) return;
      const all = inputs(), next = all[all.indexOf(inp) + 1];
      next ? (next.focus(), next.select()) : inp.blur();
    });
    els.grid.appendChild(card);
  });
  updateButtons();
}

function updateChanged(inp, it) {
  const changed = inp.value.trim() !== stem(it.name);
  inp.classList.toggle("changed", changed);
  inp.closest(".card").classList.toggle("is-changed", changed);
  updateButtons();
}

function updateButtons() {
  const changed = inputs().filter((i) => i.classList.contains("changed")).length;
  els.name.disabled = !items.length;
  els.rename.disabled = !changed;
  els.stat.innerHTML = items.length
    ? `<b>${items.length}</b> file${items.length === 1 ? "" : "s"}${changed ? ` · <span class="on">${changed} to rename</span>` : ""}`
    : "";
}

async function scan(folder) {
  if (!folder) return;
  try {
    items = (await api("scan", { folder })).items;
    render();
    els.progress.hidden = true;
  } catch (e) { toast(e.message, { error: true }); }
}

async function nameAll() {
  els.name.disabled = els.rename.disabled = true;
  els.progress.hidden = false;
  els.progress.className = "busy";
  els.progress.firstElementChild.style.width = "0";
  inputs().forEach((i) => (i.closest(".card").className = "card pending", i.disabled = true));
  try {
    const { job } = await api("name", { folder: els.folder.value.trim() });
    let r;
    do {
      await new Promise((res) => setTimeout(res, 700));
      r = await api("name/" + job);
      els.progress.firstElementChild.style.width = (r.total ? (r.progress / r.total) * 90 : 0) + "%";
    } while (!r.done);
    if (r.error) throw new Error(r.error);
    let errors = 0;
    for (const it of items) {
      const res = r.results[it.id], inp = els.grid.querySelector(`[data-id="${it.id}"] input`);
      inp.closest(".card").className = "card" + (res && res.error ? " error" : "");
      if (res && res.error) { errors++; inp.title = res.error; }
      if (res && res.proposed) { inp.value = res.proposed; updateChanged(inp, it); }
    }
    els.progress.firstElementChild.style.width = "100%";
    toast(errors ? `Named ${items.length - errors} of ${items.length} — ${errors} could not be read` : `Named ${items.length} files. Review, edit, then Rename all.`);
    inputs()[0] && inputs()[0].focus();
  } catch (e) {
    toast(e.message, { error: true });
    inputs().forEach((i, n) => { i.closest(".card").className = "card"; updateChanged(i, items[n]); });
  } finally {
    els.progress.className = "";
    setTimeout(() => (els.progress.hidden = true), 800);
    inputs().forEach((i) => (i.disabled = false));
    updateButtons();
  }
}

async function renameAll() {
  const inp = inputs();
  const changed = items.map((it, i) => ({ path: it.path, new_name: inp[i].value.trim() }))
    .filter((x, i) => x.new_name && x.new_name !== stem(items[i].name));
  if (!changed.length) return;
  try {
    const r = await api("rename", { items: changed });
    journal = r.journal;
    const msg = `Renamed ${r.renamed} file${r.renamed === 1 ? "" : "s"}`;
    toast(r.error ? `${msg}, then stopped: ${r.error}` : msg, { undo: r.renamed > 0, error: !!r.error });
    await scan(els.folder.value.trim());
  } catch (e) { toast(e.message, { error: true }); }
}

async function undo() {
  try {
    const r = await api("undo", { journal });
    journal = null;
    toast(`Restored ${r.restored} file${r.restored === 1 ? "" : "s"}`);
    await scan(els.folder.value.trim());
  } catch (e) { toast(e.message, { error: true }); }
}

function fillSettings() {
  els.gear.classList.toggle("warn", !status.has_key);
  els.model.innerHTML = status.models.map((m) => `<option value="${m}">${MODEL_LABELS[m] || m}</option>`).join("") + '<option value="">Custom…</option>';
  const known = status.models.includes(status.model);
  els.model.value = known ? status.model : "";
  els.custom.hidden = known;
  els.custom.value = known ? "" : status.model;
  els.key.value = "";
  els.key.placeholder = status.has_key ? "•••••••• (saved — leave blank to keep)" : "sk-or-…";
  els.keymsg.textContent = "";
  els.keymsg.className = "msg";
}

async function saveSettings() {
  const body = { model: els.model.value || els.custom.value.trim() || status.model };
  if (els.key.value.trim()) body.key = els.key.value.trim();
  status = await api("settings", body);
  fillSettings();
  els.settings.close();
  toast("Settings saved");
}

async function testKey() {
  els.keymsg.textContent = "Checking…";
  els.keymsg.className = "msg";
  const r = await api("check-key", { key: els.key.value.trim() });
  els.keymsg.textContent = r.ok ? `Key works${r.label ? " (" + r.label + ")" : ""}` : r.error;
  els.keymsg.className = "msg " + (r.ok ? "ok" : "err");
}

els.pick.onclick = async () => {
  const { folder } = await api("pick-folder");
  if (folder) { els.folder.value = folder; scan(folder); } else els.folder.focus();
};
els.folder.onkeydown = (e) => e.key === "Enter" && scan(els.folder.value.trim());
els.folder.onchange = () => scan(els.folder.value.trim());
els.name.onclick = nameAll;
els.rename.onclick = renameAll;
els.undo.onclick = undo;
els.gear.onclick = () => { fillSettings(); els.settings.showModal(); };
els.cancel.onclick = () => els.settings.close();
const guarded = (fn) => () => fn().catch((e) => toast(e.message, { error: true }));
els.save.onclick = guarded(saveSettings);
els.test.onclick = guarded(testKey);
els.model.onchange = () => { els.custom.hidden = !!els.model.value; if (!els.model.value) els.custom.focus(); };
els.settings.onkeydown = (e) => e.key === "Enter" && e.target.tagName === "INPUT" && (e.preventDefault(), els.save.click());
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !els.rename.disabled) renameAll();
  if (e.key === "," && (e.metaKey || e.ctrlKey)) { e.preventDefault(); els.gear.click(); }
});

api("status").then((s) => { status = s; fillSettings(); if (!s.has_key) els.settings.showModal(); });
