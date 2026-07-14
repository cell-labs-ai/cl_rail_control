"use strict";

// Web UI logic for the rail control panel. Panels are built generically from
// /api/config, so adding a parameter server-side needs no changes here.

const POLL_INTERVAL_MS = 250;

// Parameters with group "pid" go in the PID card; the rest go in the
// Parameters card. Within that card only these keys stay visible -- everything
// else is tucked into a collapsed "More parameters" disclosure.
const ALWAYS_VISIBLE = new Set(["jog_speed"]);

// Direction button labels per controller role.
const JOG_LABELS = {
  cart: { "-1": "◀ Left", "1": "Right ▶" },
  lift: { "-1": "Down ▼", "1": "▲ Up" },
};

const panelsEl = document.getElementById("panels");
const linkBadge = document.getElementById("link-badge");
const modeBadge = document.getElementById("mode-badge");

// --- theme toggle ----------------------------------------------------------

function getTheme() {
  return localStorage.getItem("theme") || "dark";
}

function updateThemeToggle(theme) {
  document.getElementById("theme-icon").textContent = theme === "dark" ? "☀️" : "🌙";
  document.getElementById("theme-label").textContent = theme === "dark" ? "Light" : "Dark";
}

function setTheme(theme) {
  localStorage.setItem("theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
  updateThemeToggle(theme);
}

document.getElementById("theme-toggle").addEventListener("click", () => {
  setTheme(getTheme() === "dark" ? "light" : "dark");
});
updateThemeToggle(getTheme());

const panels = {};   // name -> { root, inputs: {key: el}, readoutCells: {key: td}, flags, errLine }
let config = null;

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok && res.status >= 500) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

async function post(name, action, payload) {
  try {
    return await api(`/api/${name}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
  } catch (err) {
    console.error(err);
    return { ok: false, message: String(err) };
  }
}

// --- panel construction ---------------------------------------------------

// A collapsed <details> disclosure that param rows get appended into.
function makeDisclosure(label) {
  const details = document.createElement("details");
  details.className = "advanced";
  const summary = document.createElement("summary");
  summary.textContent = label;
  details.appendChild(summary);
  return details;
}

function makeParamRow(name, spec) {
  const row = document.createElement("div");
  row.className = "param-row";

  if (spec.kind === "select") {
    const label = document.createElement("label");
    label.textContent = spec.label;
    const select = document.createElement("select");
    for (const opt of spec.options) {
      const o = document.createElement("option");
      o.value = opt.value;
      o.textContent = opt.label;
      select.appendChild(o);
    }
    select.value = spec.default;
    select.addEventListener("change", () =>
      post(name, "param", { key: spec.key, value: Number(select.value) }));
    row.append(label, select);
    return { row, input: select };
  }

  if (spec.kind === "number") {
    const label = document.createElement("label");
    label.textContent = spec.label;
    const input = document.createElement("input");
    input.type = "number";
    if (spec.min !== undefined) input.min = spec.min;
    if (spec.max !== undefined) input.max = spec.max;
    if (spec.step !== undefined) input.step = spec.step;
    input.value = spec.default;
    input.addEventListener("change", () =>
      post(name, "param", { key: spec.key, value: Number(input.value) }));
    row.append(label, input);
    return { row, input };
  }

  // slider
  row.className = "param-row slider-row";
  const head = document.createElement("div");
  head.className = "slider-head";
  const label = document.createElement("label");
  label.textContent = spec.label;
  const val = document.createElement("span");
  val.className = "val";
  val.textContent = spec.default;
  head.append(label, val);

  const input = document.createElement("input");
  input.type = "range";
  input.min = spec.min;
  input.max = spec.max;
  input.step = spec.step || 1;
  input.value = spec.default;
  input.addEventListener("input", () => { val.textContent = input.value; });
  input.addEventListener("change", () =>
    post(name, "param", { key: spec.key, value: Number(input.value) }));
  row.append(head, input);
  return { row, input, valEl: val };
}

function buildPanel(ctrl) {
  const name = ctrl.name;
  const tpl = document.getElementById("panel-template").content.cloneNode(true);
  const root = tpl.querySelector(".panel");
  root.dataset.controller = name;
  root.querySelector(".panel-title").textContent =
    `${name} — …${ctrl.suffix}`;

  const inputs = {};
  const valEls = {};

  // Split params between the PID card and the general Parameters card. In the
  // Parameters card, only jog speed stays visible; the rest collapse into a
  // "More parameters" disclosure that is closed by default.
  const paramsBox = root.querySelector(".params");
  const pidBox = root.querySelector(".pid-params");

  // Both cards keep their settings collapsed behind a "More parameters"
  // disclosure. In the Parameters card jog speed stays visible; the PID card
  // hides all its tuning behind the disclosure, leaving only Start/Stop.
  const advanced = makeDisclosure("More parameters");
  const pidAdvanced = makeDisclosure("PID settings");

  for (const spec of config.params) {
    const { row, input, valEl } = makeParamRow(name, spec);
    inputs[spec.key] = input;
    if (valEl) valEls[spec.key] = valEl;
    if (spec.group === "pid") {
      pidAdvanced.appendChild(row);
    } else if (ALWAYS_VISIBLE.has(spec.key)) {
      paramsBox.appendChild(row);
    } else {
      advanced.appendChild(row);
    }
  }
  paramsBox.appendChild(advanced);
  pidBox.appendChild(pidAdvanced);

  // Jog buttons (hold-to-jog).
  const labels = JOG_LABELS[ctrl.role] || JOG_LABELS.cart;
  const jogButtons = {};
  root.querySelectorAll(".jog").forEach((btn) => {
    const dir = btn.dataset.dir;
    jogButtons[dir] = btn;
    btn.textContent = labels[dir] || (dir === "1" ? "+" : "-");
    const start = (e) => { e.preventDefault(); post(name, "jog", { direction: Number(dir) }); };
    const stop = (e) => { e.preventDefault(); post(name, "jog_stop", {}); };
    btn.addEventListener("pointerdown", start);
    btn.addEventListener("pointerup", stop);
    btn.addEventListener("pointerleave", stop);
    btn.addEventListener("pointercancel", stop);
  });

  root.querySelector(".estop").addEventListener("click", () => post(name, "stop", {}));

  const pidToggle = root.querySelector(".pid-toggle");
  pidToggle.addEventListener("click", () => {
    const action = pidToggle.classList.contains("running") ? "stop" : "start";
    post(name, "pid", { action });
  });

  // Readout rows.
  const tbody = root.querySelector(".readout tbody");
  const readoutCells = {};
  for (const item of config.readout) {
    const tr = document.createElement("tr");
    const td1 = document.createElement("td");
    td1.textContent = item.label;
    const td2 = document.createElement("td");
    td2.textContent = "–";
    tr.append(td1, td2);
    tbody.appendChild(tr);
    readoutCells[item.key] = { cell: td2, fmt: item.fmt };
  }

  panelsEl.appendChild(tpl);
  panels[name] = {
    root,
    inputs,
    valEls,
    readoutCells,
    jogButtons,
    flags: {
      conn: root.querySelector(".flag-conn"),
      drive: root.querySelector(".flag-drive"),
      pid: root.querySelector(".flag-pid"),
      negLimit: root.querySelector(".flag-neg-limit"),
      posLimit: root.querySelector(".flag-pos-limit"),
    },
    pidToggle,
    errLine: root.querySelector(".err-line"),
  };
}

// --- live updates ---------------------------------------------------------

function toHex(value) {
  return "0x" + (value & 0xffff).toString(16).toUpperCase().padStart(4, "0");
}

// Decode the CiA 402 statusword (6041h) into its state-machine state name.
// Masks per the C5-E manual / DS402: the state lives in bits 0-3, 5 and 6.
function decodeStatusword(sw) {
  if ((sw & 0x4f) === 0x00) return "Not ready to switch on";
  if ((sw & 0x4f) === 0x40) return "Switch on disabled";
  if ((sw & 0x6f) === 0x21) return "Ready to switch on";
  if ((sw & 0x6f) === 0x23) return "Switched on";
  if ((sw & 0x6f) === 0x27) return "Operation enabled";
  if ((sw & 0x6f) === 0x07) return "Quick stop active";
  if ((sw & 0x4f) === 0x0f) return "Fault reaction active";
  if ((sw & 0x4f) === 0x08) return "Fault";
  return toHex(sw);
}

// Decode the CiA 402 controlword (6040h) into the command it issues.
function decodeControlword(cw) {
  if (cw & 0x80) return "Fault reset";
  if ((cw & 0x82) === 0x00) return "Disable voltage";
  if ((cw & 0x86) === 0x02) return "Quick stop";
  if ((cw & 0x8f) === 0x0f) return "Enable operation";
  if ((cw & 0x8f) === 0x07) return "Switch on";
  if ((cw & 0x87) === 0x06) return "Shutdown";
  return toHex(cw);
}

function fmtReadout(fmt, value) {
  if (value === null || value === undefined) return "–";
  if (fmt === "statusword") return `${decodeStatusword(value)} (${toHex(value)})`;
  if (fmt === "controlword") return `${decodeControlword(value)} (${toHex(value)})`;
  if (fmt === "hex" && typeof value === "number") return toHex(value);
  return String(value);
}

function updatePanel(name, data) {
  const p = panels[name];
  if (!p || !data) return;

  // Flags.
  p.flags.conn.textContent = data.connected ? "online" : "offline";
  p.flags.conn.classList.toggle("on-conn", data.connected);

  const driving = data.jog_direction !== 0 || data.drive_enabled;
  p.flags.drive.textContent = data.jog_direction !== 0
    ? (data.jog_direction > 0 ? "driving +" : "driving -")
    : (data.drive_enabled ? "enabled" : "idle");
  p.flags.drive.classList.toggle("on-drive", driving);

  p.flags.pid.textContent = data.pid_running ? "PID on" : "PID off";
  p.flags.pid.classList.toggle("on-pid", data.pid_running);
  p.pidToggle.textContent = data.pid_running ? "Stop PID" : "Start PID";
  p.pidToggle.classList.toggle("running", data.pid_running);

  // End stops (60FDh bit 0 = negative limit switch, bit 1 = positive limit
  // switch). Null (not yet read / unavailable) reads as clear, not triggered.
  const state = data.state || {};
  p.flags.negLimit.textContent = state.neg_limit ? "NEG ENDSTOP" : "neg endstop";
  p.flags.negLimit.classList.toggle("on-limit", !!state.neg_limit);
  p.flags.posLimit.textContent = state.pos_limit ? "POS ENDSTOP" : "pos endstop";
  p.flags.posLimit.classList.toggle("on-limit", !!state.pos_limit);

  // Block jogging further into a triggered end stop; the opposite
  // direction stays enabled so the cart can be driven back off it.
  if (p.jogButtons["1"]) p.jogButtons["1"].disabled = !!state.pos_limit;
  if (p.jogButtons["-1"]) p.jogButtons["-1"].disabled = !!state.neg_limit;

  // Readout.
  for (const [key, { cell, fmt }] of Object.entries(p.readoutCells)) {
    cell.textContent = fmtReadout(fmt, state[key]);
  }

  // Reflect server-side param values (e.g. clamping) without stomping an
  // input the user is currently editing.
  for (const [key, value] of Object.entries(data.params || {})) {
    const input = p.inputs[key];
    if (input && document.activeElement !== input) {
      input.value = value;
      if (p.valEls[key]) p.valEls[key].textContent = value;
    }
  }

  p.errLine.textContent = data.last_error || "";
}

async function poll() {
  try {
    const data = await api("/api/state");
    linkBadge.textContent = "connected";
    linkBadge.className = "badge live";
    for (const [name, cdata] of Object.entries(data.controllers)) {
      updatePanel(name, cdata);
    }
  } catch (err) {
    linkBadge.textContent = "disconnected";
    linkBadge.className = "badge down";
  }
}

// --- boot -----------------------------------------------------------------

async function init() {
  config = await api("/api/config");
  modeBadge.textContent = config.simulate ? "SIMULATION" : "LIVE";
  modeBadge.className = "badge " + (config.simulate ? "sim" : "live");

  if (!config.controllers.length) {
    panelsEl.innerHTML = "<p style='color:var(--muted)'>No controllers connected.</p>";
    return;
  }
  for (const ctrl of config.controllers) buildPanel(ctrl);

  await poll();
  setInterval(poll, POLL_INTERVAL_MS);
}

init().catch((err) => {
  linkBadge.textContent = "error";
  linkBadge.className = "badge down";
  console.error(err);
});
