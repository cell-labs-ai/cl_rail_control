"use strict";

// Web UI logic for the rail control panel. Panels are built generically from
// /api/config, so adding a parameter server-side needs no changes here.

const POLL_INTERVAL_MS = 250;

// Parameters with group "pid" go in the PID card; the rest go in the
// Parameters card. Within that card only these keys stay visible -- everything
// else is tucked into a collapsed "More parameters" disclosure. The manual
// drive is a joystick now, so the (full-scale) joy speed lives in there too and
// nothing stays pinned open.
const ALWAYS_VISIBLE = new Set();

// End labels for the manual-drive joystick per controller role. The joystick
// axis follows the physical one: the cart drives horizontally (left/right),
// the lift vertically (down/up).
const JOG_LABELS = {
  cart: { "-1": "◀ Left", "1": "Right ▶" },
  lift: { "-1": "Down ▼", "1": "▲ Up" },
};
const JOY_AXIS = { cart: "x", lift: "y" };

// The cart's positive-velocity convention (rail_web_ui.py) drives it opposite
// to what "right" looks like on screen -- multiply by this when converting
// screen position to a command (rpm sent, rpm displayed), but NOT when
// positioning the handle, so the stick still visually follows the pointer.
const AXIS_SIGN = { cart: -1, lift: 1 };

// Below this fraction of full travel the stick reads as centred (0). Keeps a
// resting hand from creeping the drive.
const JOY_DEADZONE = 0.06;

// How often a HELD joystick re-posts its current velocity (ms). This is not
// just throttling: the repeat is a deadman heartbeat. The server holds a manual
// drive command for JOG_DEADMAN_TIMEOUT_S (rail_web_ui.py) and stops the axis
// once the repeats stop, so a release that never arrives -- lost POST, pointerup
// that never fired, browser tab or WiFi gone -- stops the drive anyway. Keep
// this at roughly a third of that timeout so a couple of dropped posts on the
// shared WiFi bus don't nuisance-stop a drive that is still being steered.
const JOY_HOLD_INTERVAL_MS = 100;

// Identifies this page load in every joystick post. The server orders commands
// by a counter that restarts at 1 whenever the page reloads, so it needs to know
// when a counter belongs to a new session rather than being a stale straggler --
// otherwise a browser refresh would leave the joystick dead, every command
// rejected against the previous session's high-water mark. See _accept_jog_order
// in rail_web_ui.py.
const JOY_EPOCH = Math.random().toString(36).slice(2) + "-" + Date.now();

const panelsEl = document.getElementById("panels");
const linkBadge = document.getElementById("link-badge");
const modeBadge = document.getElementById("mode-badge");
const modeSwitchEl = document.getElementById("mode-switch");

// --- operating-mode switcher ------------------------------------------------

// key -> button, built from /api/config (modes) so a mode added server-side
// shows up here with no changes.
const modeButtons = {};

// Latest known system-wide operating mode; kept current by
// updateModeSwitch() (config load, mode posts, every poll). Panels read it,
// e.g. to show the lift's walk re-arm button only in Walking mode.
let currentMode = null;

function buildModeSwitch(modes) {
  for (const mode of modes) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mode-btn";
    btn.textContent = mode.label;
    btn.addEventListener("click", () => setOperatingMode(mode.key));
    modeSwitchEl.appendChild(btn);
    modeButtons[mode.key] = btn;
  }
}

function updateModeSwitch(mode) {
  currentMode = mode;
  for (const [key, btn] of Object.entries(modeButtons)) {
    btn.classList.toggle("active", key === mode);
  }
}

async function setOperatingMode(mode) {
  try {
    const res = await api("/api/system/mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    if (res.mode) updateModeSwitch(res.mode);
    if (!res.ok) flashSettingsStatus(false, res.message || "mode switch failed");
  } catch (err) {
    flashSettingsStatus(false, String(err));
  }
}

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

// --- settings save / load ---------------------------------------------------

const settingsStatus = document.getElementById("settings-status");
let settingsStatusTimer = null;

function flashSettingsStatus(ok, message) {
  clearTimeout(settingsStatusTimer);
  settingsStatus.textContent = message;
  settingsStatus.className = "badge " + (ok ? "live" : "down");
  settingsStatus.hidden = false;
  settingsStatusTimer = setTimeout(() => { settingsStatus.hidden = true; }, 4000);
}

async function settingsAction(action) {
  try {
    const res = await api(`/api/settings/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    flashSettingsStatus(res.ok, res.message || (res.ok ? "ok" : "failed"));
    if (res.ok) await poll();   // reflect any loaded values immediately
  } catch (err) {
    flashSettingsStatus(false, String(err));
  }
}

document.getElementById("settings-save").addEventListener("click", () => settingsAction("save"));
document.getElementById("settings-load").addEventListener("click", () => settingsAction("load"));

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

// A param edit that fails silently (e.g. a dropped connection mid-request)
// looks identical to one that was never made -- the input just sits there
// showing the value the operator typed. Flash the field red with the reason
// so a lost request is visible instead of indistinguishable from success.
function flashFieldError(input, message) {
  clearTimeout(input._errTimer);
  input.classList.add("field-error");
  input.title = message || "update failed";
  input._errTimer = setTimeout(() => {
    input.classList.remove("field-error");
    input.title = "";
  }, 4000);
}

async function postParam(name, input, key, value) {
  const res = await post(name, "param", { key, value });
  if (!res.ok) flashFieldError(input, res.message);
  return res;
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
      postParam(name, select, spec.key, Number(select.value)));
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
      postParam(name, input, spec.key, Number(input.value)));
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
    postParam(name, input, spec.key, Number(input.value)));
  row.append(head, input);
  return { row, input, valEl: val };
}

// Sender for joystick velocity updates.
//
// A held stick is REPEATED at JOY_HOLD_INTERVAL_MS rather than posted only when
// the value changes: that stream is the deadman heartbeat the server needs to
// keep the drive running (see JOY_HOLD_INTERVAL_MS). hold() therefore starts a
// ticker that keeps posting whatever the stick currently reads; release() stops
// the ticker and posts one 0. The post rate is a flat 10/s while held instead of
// the old up-to-12.5/s burst on every pointermove, so bus load is predictable;
// the cost is up to one interval of latency on a mid-drag change, which is well
// under the drive's own acceleration ramp.
//
// Every post carries an incrementing seq plus JOY_EPOCH. Posts are
// fire-and-forget over WiFi and the server handles them on independent threads,
// so an update issued just before the release can arrive after it; the server
// drops anything whose seq it has already passed, which stops that straggler
// from reinstating a velocity the operator has let go of. The epoch scopes the
// counter to this page load -- see _accept_jog_order in rail_web_ui.py.
function makeVelocitySender(name) {
  let timer = null;
  let current = 0;
  let lastSent = null;
  let seq = 0;

  function send(v) {
    lastSent = v;
    post(name, "jog_velocity", { velocity: v, seq: ++seq, epoch: JOY_EPOCH });
  }

  // Repeat tick. A zero is sent once and then goes quiet: with nothing moving
  // there is no lease to renew, and repeating it would put a Modbus write on the
  // shared WiFi bus every interval while the stick simply rests in the deadzone.
  // If that one zero is lost, the deadman stops the axis anyway.
  function tick() {
    if (current !== 0 || lastSent !== 0) send(current);
  }

  return {
    // Latest stick value while held; starts the repeat ticker on first call.
    hold(v) {
      current = v;
      if (timer === null) {
        send(current);
        timer = setInterval(tick, JOY_HOLD_INTERVAL_MS);
      }
    },
    // Stop repeating and command zero. Idempotent: safe to call from every
    // path that can end a hold, including several for the same release.
    release() {
      if (timer !== null) { clearInterval(timer); timer = null; }
      current = 0;
      send(0);
    },
  };
}

// One-axis spring-return joystick that replaces the hold-to-jog buttons.
// Displacement from centre maps linearly to target velocity (0 at centre,
// +/- fullScale at the ends); releasing springs the handle back to centre and
// posts velocity 0. Returns a handle the panel keeps for live updates
// (fullScale from the joy-speed param, and end-stop gating).
function makeJoystick(name, role) {
  const axis = JOY_AXIS[role] || "x";
  const labels = JOG_LABELS[role] || JOG_LABELS.cart;
  const sender = makeVelocitySender(name);

  const wrap = document.createElement("div");
  wrap.className = "joystick";
  wrap.dataset.axis = axis;

  const endNeg = document.createElement("span");
  endNeg.className = "joy-end joy-end-neg";
  endNeg.textContent = labels["-1"];
  const endPos = document.createElement("span");
  endPos.className = "joy-end joy-end-pos";
  endPos.textContent = labels["1"];

  const track = document.createElement("div");
  track.className = "joy-track";
  const handle = document.createElement("div");
  handle.className = "joy-handle";
  track.appendChild(handle);

  const value = document.createElement("div");
  value.className = "joy-value";

  wrap.append(endNeg, track, endPos, value);

  const joy = {
    wrap,
    fullScale: 0,
    limits: { pos: false, neg: false },
    dragging: false,
    pointerId: null,   // the pointer that owns the current hold
  };

  function render(pos) {
    handle.style.setProperty("--pos", pos);
    const rpm = Math.round(pos * AXIS_SIGN[role] * joy.fullScale);
    value.textContent = rpm === 0 ? "0 rpm" : `${rpm > 0 ? "+" : ""}${rpm} rpm`;
    value.classList.toggle("active", rpm !== 0);
  }

  // Fraction of full travel (clamped to [-1, 1]) for a pointer event, after
  // deadzone and end-stop gating. This is screen position (right/up = +),
  // used for the handle's visual placement -- see AXIS_SIGN for the command
  // this turns into.
  function posFromEvent(e) {
    const r = track.getBoundingClientRect();
    let p = axis === "y"
      ? (r.top + r.height / 2 - e.clientY) / (r.height / 2)   // up = +
      : (e.clientX - (r.left + r.width / 2)) / (r.width / 2);  // right = +
    p = Math.max(-1, Math.min(1, p));
    // limits.pos/neg gate the actual command direction, not screen position.
    const cmdSign = AXIS_SIGN[role] * p;
    if (cmdSign > 0 && joy.limits.pos) p = 0;   // blocked by a triggered end stop
    if (cmdSign < 0 && joy.limits.neg) p = 0;
    if (Math.abs(p) < JOY_DEADZONE) p = 0;
    return p;
  }

  function onMove(e) {
    if (!joy.dragging || e.pointerId !== joy.pointerId) return;
    e.preventDefault();
    const p = posFromEvent(e);
    render(p);
    sender.hold(Math.round(p * AXIS_SIGN[role] * joy.fullScale));
  }

  // Spring back to centre and stop. Every way a hold can end funnels through
  // here, and it takes no event, so it can also be called from the
  // focus/visibility handlers below where there is no pointer event at all.
  function release() {
    if (!joy.dragging) return;
    joy.dragging = false;
    joy.pointerId = null;
    track.classList.remove("dragging");
    render(0);
    sender.release();
  }

  function onUp(e) {
    if (!joy.dragging || e.pointerId !== joy.pointerId) return;
    try { track.releasePointerCapture(e.pointerId); } catch (_) { /* not captured */ }
    release();
  }

  track.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    joy.dragging = true;
    joy.pointerId = e.pointerId;
    track.classList.add("dragging");
    try { track.setPointerCapture(e.pointerId); } catch (_) { /* older browsers */ }
    onMove(e);
  });

  // Pointer events go on WINDOW, not the track: setPointerCapture can fail (the
  // try/catch above) or be revoked, and then the pointerup lands on whatever
  // element is under the cursor -- leaving the stick logically held with a
  // velocity standing on the drive. lostpointercapture covers revocation
  // (browser gestures, a long-press context menu) explicitly.
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointercancel", onUp);
  track.addEventListener("lostpointercapture", release);

  // Nothing guarantees a pointer event at all when the page stops being the
  // thing the operator is looking at: alt-tab, a tab switch, a phone screen
  // lock, dev tools taking focus. Treat all of them as letting go. (The
  // server-side deadman is the real backstop -- these just make the stop
  // immediate instead of JOG_DEADMAN_TIMEOUT_S later.)
  window.addEventListener("blur", release);
  window.addEventListener("pagehide", release);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) release();
  });

  render(0);
  return joy;
}

// Lock a flag's min-width to its widest possible label so that later text
// changes (e.g. "enabled" -> "driving +") never resize the flag and reflow
// the row it sits in. Must run after the element is attached to the
// document, since it measures rendered width.
function lockFlagWidth(el, candidates) {
  if (!el) return;
  const original = el.textContent;
  let widest = 0;
  for (const text of candidates) {
    el.textContent = text;
    widest = Math.max(widest, el.getBoundingClientRect().width);
  }
  el.textContent = original;
  el.style.minWidth = `${Math.ceil(widest)}px`;
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

  const params = ctrl.params || [];
  const readout = ctrl.readout || [];

  // The lift has no PID: drop the PID card and its status flag entirely.
  const hasPid = params.some((spec) => spec.group === "pid");
  if (!hasPid) {
    root.querySelector(".pid-card").remove();
    root.querySelector(".flag-pid").remove();
  }

  // Homing status and the Walking-mode auto-lower are lift-only concerns;
  // the cart has neither, so drop their flags.
  if (ctrl.role !== "lift") {
    root.querySelector(".flag-homing").remove();
    root.querySelector(".flag-walk").remove();
  }

  // Soft lower travel limit (LIFT_DOWN_POSITION_LIMIT) is lift-only and only
  // shown when actually configured server-side (None disables it).
  const downLimit = ctrl.down_limit;
  const hasDownLimit = ctrl.role === "lift" && downLimit !== null && downLimit !== undefined;
  if (!hasDownLimit) {
    root.querySelector(".flag-down-limit").remove();
  }

  // Split params between the PID card and the general Parameters card. In the
  // Parameters card, only jog speed stays visible; the rest collapse into a
  // "More parameters" disclosure that is closed by default.
  const paramsBox = root.querySelector(".params");
  const pidBox = root.querySelector(".pid-params");   // null when there is no PID card

  // Both cards keep their settings collapsed behind a disclosure. In the
  // Parameters card jog speed stays visible; the PID card hides all its tuning
  // behind the disclosure, leaving only Start/Stop.
  const advanced = makeDisclosure("More parameters");
  const pidAdvanced = pidBox ? makeDisclosure("PID settings") : null;

  for (const spec of params) {
    const { row, input, valEl } = makeParamRow(name, spec);
    inputs[spec.key] = input;
    if (valEl) valEls[spec.key] = valEl;
    if (spec.group === "pid") {
      if (pidAdvanced) pidAdvanced.appendChild(row);
    } else if (ALWAYS_VISIBLE.has(spec.key)) {
      paramsBox.appendChild(row);
    } else {
      advanced.appendChild(row);
    }
  }
  // Only show the "More parameters" disclosure if it actually holds a row
  // (a summary is its only child otherwise).
  if (advanced.children.length > 1) paramsBox.appendChild(advanced);
  if (pidBox && pidAdvanced) pidBox.appendChild(pidAdvanced);

  // Manual drive: a spring-return one-axis joystick (replaces the hold-to-jog
  // buttons). Its full-scale velocity is the joy-speed param.
  const joystick = makeJoystick(name, ctrl.role);
  root.querySelector(".joy-mount").appendChild(joystick.wrap);
  const jogSpec = params.find((spec) => spec.key === "jog_speed");
  joystick.fullScale = jogSpec ? Number(jogSpec.default) : 0;

  root.querySelector(".estop").addEventListener("click", () => post(name, "stop", {}));

  // Walking-mode re-arm (lift only): restart the walk sequence once the
  // robot has recovered. Kept visible (but disabled) throughout Walking mode
  // so the operator knows the option exists; hidden entirely in Basic.
  let walkRearm = root.querySelector(".walk-rearm");
  if (ctrl.role !== "lift") {
    walkRearm.remove();
    walkRearm = null;
  } else {
    walkRearm.addEventListener("click", () => post(name, "walk_rearm", {}));
  }

  const pidToggle = root.querySelector(".pid-toggle");   // null when there is no PID card
  if (pidToggle) {
    pidToggle.addEventListener("click", () => {
      const action = pidToggle.classList.contains("running") ? "stop" : "start";
      post(name, "pid", { action });
    });
  }

  // Readout rows.
  const tbody = root.querySelector(".readout tbody");
  const readoutCells = {};
  for (const item of readout) {
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

  const flagConn = root.querySelector(".flag-conn");
  const flagDrive = root.querySelector(".flag-drive");
  const flagPid = root.querySelector(".flag-pid");
  const flagHoming = root.querySelector(".flag-homing");
  const flagWalk = root.querySelector(".flag-walk");
  const flagDownLimit = hasDownLimit ? root.querySelector(".flag-down-limit") : null;
  const flagNegLimit = root.querySelector(".flag-neg-limit");
  const flagPosLimit = root.querySelector(".flag-pos-limit");
  lockFlagWidth(flagConn, ["online", "offline"]);
  lockFlagWidth(flagDrive, ["driving +", "driving -", "enabled", "idle"]);
  lockFlagWidth(flagPid, ["PID on", "PID off"]);
  lockFlagWidth(flagHoming, ["homed", "homing…", "not homed ↑", "homing ?"]);
  if (flagWalk) {
    // Starts hidden (only shown while the Walking-mode sequence is active);
    // unhide briefly so lockFlagWidth measures real widths.
    flagWalk.hidden = false;
    lockFlagWidth(flagWalk, ["lowering ▼", "tension ▲", "grounded", "CAUGHT", "walk failed"]);
    flagWalk.hidden = true;
  }
  lockFlagWidth(flagDownLimit, ["down limit set", "AT DOWN LIMIT"]);
  lockFlagWidth(flagNegLimit, ["neg endstop", "NEG ENDSTOP"]);
  lockFlagWidth(flagPosLimit, ["pos endstop", "POS ENDSTOP"]);
  if (flagDownLimit) {
    flagDownLimit.title = `soft lower travel limit configured: position ≤ ${downLimit}`;
  }

  panels[name] = {
    root,
    inputs,
    valEls,
    readoutCells,
    joystick,
    flags: {
      conn: flagConn,
      drive: flagDrive,
      pid: flagPid,
      homing: flagHoming,
      walk: flagWalk,
      downLimit: flagDownLimit,
      negLimit: flagNegLimit,
      posLimit: flagPosLimit,
    },
    pidToggle,
    pidDebug: root.querySelector(".pid-debug"),   // null when there is no PID card
    walkRearm,
    errLine: root.querySelector(".err-line"),
  };
}

// PID debug is a live per-tick breakdown of what the loop just computed --
// see pid_debug in rail_web_ui.py. null while PID isn't running.
function renderPidDebug(el, debug) {
  if (!el) return;
  if (!debug) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.textContent =
    `angle ${debug.angle}   error ${debug.error}\n` +
    `P ${debug.p_term}   I ${debug.i_term}   D ${debug.d_term}   ` +
    `→ ${debug.velocity} rpm\n` +
    `kp ${debug.kp}   ki ${debug.ki}   kd ${debug.kd}`;
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
  // Brake output (60FEh:01h bit 0): "1" = brake activated/closed, "0" = released.
  if (fmt === "brake" && typeof value === "number") {
    return (value & 1) ? "CLOSED (1)" : "released (0)";
  }
  // Digital inputs (60FDh) as endstops: bit 0 = negative limit switch, bit 1 =
  // positive limit switch. Show which (if any) are triggered.
  if (fmt === "endstops" && typeof value === "number") {
    const triggered = [];
    if (value & 0x1) triggered.push("NEG");
    if (value & 0x2) triggered.push("POS");
    return triggered.length ? triggered.join(" + ") + " triggered" : "clear";
  }
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

  if (p.flags.pid) {
    p.flags.pid.textContent = data.pid_running ? "PID on" : "PID off";
    p.flags.pid.classList.toggle("on-pid", data.pid_running);
  }
  if (p.pidToggle) {
    p.pidToggle.textContent = data.pid_running ? "Stop PID" : "Start PID";
    p.pidToggle.classList.toggle("running", data.pid_running);
  }
  renderPidDebug(p.pidDebug, data.pid_debug);

  // Homing status (lift only). Until homed, the lift is UP-only: drive it up
  // into the top end stop to home (method 35). true = homed, in-progress =
  // homing running, false = not homed (down disabled), null = unknown.
  if (p.flags.homing) {
    const homed = data.homing_complete === true;
    if (homed) {
      p.flags.homing.textContent = "homed";
    } else if (data.homing_in_progress) {
      p.flags.homing.textContent = "homing…";
    } else if (data.homing_complete === false) {
      p.flags.homing.textContent = "not homed ↑";
    } else {
      p.flags.homing.textContent = "homing ?";
    }
    p.flags.homing.classList.toggle("on-conn", homed);
    p.flags.homing.classList.toggle("on-pid", !homed && !!data.homing_in_progress);
    p.flags.homing.classList.toggle("on-limit", data.homing_complete === false && !data.homing_in_progress);
  }

  // Walking-mode sequence status (lift only). Hidden while inactive;
  // "lowering ▼" during the descent, "tension ▲" while reeling in slack at
  // limited current after touchdown, "grounded" once stalled taut with the
  // current zeroed (fall watch armed), "CAUGHT" after the fall catch has
  // restored torque, "walk failed" on an abort (reason in the error line).
  if (p.flags.walk) {
    const ws = data.walk_status;
    p.flags.walk.hidden = !ws;
    if (ws === "lowering") {
      p.flags.walk.textContent = "lowering ▼";
    } else if (ws === "tensioning") {
      p.flags.walk.textContent = "tension ▲";
    } else if (ws === "grounded") {
      p.flags.walk.textContent = "grounded";
    } else if (ws === "caught") {
      p.flags.walk.textContent = "CAUGHT";
    } else if (ws) {
      p.flags.walk.textContent = "walk failed";
    }
    p.flags.walk.classList.toggle("on-pid", ws === "lowering");
    p.flags.walk.classList.toggle("on-drive", ws === "tensioning");
    p.flags.walk.classList.toggle("on-conn", ws === "grounded");
    p.flags.walk.classList.toggle("on-limit", ws === "aborted" || ws === "caught");
  }

  // Walk re-arm button (lift only): visible throughout Walking mode so the
  // option is discoverable, but only clickable when no sequence phase is
  // actively running (caught / aborted / idle after an override).
  if (p.walkRearm) {
    const busy = ["lowering", "tensioning", "grounded"].includes(data.walk_status);
    p.walkRearm.hidden = currentMode !== "walking";
    p.walkRearm.disabled = busy;
  }

  // Soft lower travel limit (lift only, only present when LIFT_DOWN_POSITION_LIMIT
  // is configured server-side). down_limit_active mirrors the poller's own
  // _down_position_blocked() check, so this lights up exactly when the drive
  // would be/was stopped by it.
  if (p.flags.downLimit) {
    const atLimit = !!data.down_limit_active;
    p.flags.downLimit.textContent = atLimit ? "AT DOWN LIMIT" : "down limit set";
    p.flags.downLimit.classList.toggle("on-limit", atLimit);
  }

  // End stops (60FDh bit 0 = negative limit switch, bit 1 = positive limit
  // switch). Null (not yet read / unavailable) reads as clear, not triggered.
  const state = data.state || {};
  p.flags.negLimit.textContent = state.neg_limit ? "NEG ENDSTOP" : "neg endstop";
  p.flags.negLimit.classList.toggle("on-limit", !!state.neg_limit);
  p.flags.posLimit.textContent = state.pos_limit ? "POS ENDSTOP" : "pos endstop";
  p.flags.posLimit.classList.toggle("on-limit", !!state.pos_limit);

  // Block driving further into a triggered end stop; the opposite direction
  // stays available so the cart can be driven back off it. The joystick reads
  // these to snap the blocked side to centre while dragging.
  if (p.joystick) {
    p.joystick.limits.pos = !!state.pos_limit;
    p.joystick.limits.neg = !!state.neg_limit;
    // Lift, not yet homed: lock out downward drive (down = negative axis) so the
    // stick can only push up toward the top end stop. p.flags.homing exists on
    // the lift only, so this never touches the cart.
    if (p.flags.homing && data.homing_complete !== true) {
      p.joystick.limits.neg = true;
    }
  }

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

  // Keep the joystick's full-scale in step with the joy-speed param (tuned in
  // "More parameters" or applied by a settings load).
  if (p.joystick && data.params && data.params.jog_speed != null) {
    p.joystick.fullScale = Number(data.params.jog_speed);
  }

  p.errLine.textContent = data.last_error || "";
}

async function poll() {
  try {
    const data = await api("/api/state");
    linkBadge.textContent = "connected";
    linkBadge.className = "badge live";
    updateModeSwitch(data.mode);
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
  buildModeSwitch(config.modes || []);
  updateModeSwitch(config.mode);

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
