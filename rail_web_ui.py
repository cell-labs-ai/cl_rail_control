#!/usr/bin/env python3
"""
Web UI for the rail system.

Serves a single-page control panel (see the webui/ folder) plus a small JSON
API for two Nanotec motor controllers:

  * CART  -- the cart that runs along the rail        (serial ends in "0168")
  * LIFT  -- pulls the hanging payload up and down     (serial ends in "0173")

Both controllers live on the same Modbus TCP (WiFi) bus. The connection /
discovery logic mirrors test_controllers.py and motion_test.py: list the
Modbus TCP bus hardware, scan it, and keep the two devices whose serial
numbers match. There is no way to target a device by IP directly (see the
note in motion_test.py), so discovery-by-scan is the only path.

The UI provides, per controller:
  * a parameter section (jog controls), and
  * a spring-return one-axis joystick for manual drive plus a STOP.

The manual drive is a joystick: stick displacement sets the target velocity
(0 at centre, +/- the full-scale joy speed at the ends), springing back to
zero when released. The CART carries the full set -- joy max speed plus
acceleration/jerk, plus PID gain tuning (Kp/Ki/Kd) with a start/stop for the
software balance loop. The LIFT is pared down to just the joy max speed: no
jog accel/jerk, no PID, and no analog-angle readout.

The CART is fully wired up. The LIFT reuses most of the readout, and its
motion is templated (lift_up / lift_down) -- the drive is the same generic
Profile Velocity move as the cart, with TODO markers where the real lift
kinematics / travel limits / homing belong.

Usage (inside the project virtualenv, from the repo root):
    source .venv/bin/activate
    python rail_web_ui.py                 # talk to the real controllers
    python rail_web_ui.py --simulate      # no hardware; fake state for UI dev
    python rail_web_ui.py --port 8080

Then open http://<pi-address>:8080/ in a browser.

IMPORTANT: as with the other scripts, make sure no other tool is talking to
the controllers while this runs.
"""

import argparse
import json
import math
import os
import sys
import threading
import time
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# The nanolib package lives under nanolib_python_linux; make it importable
# regardless of the current working directory (same as the other scripts).
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "nanolib_python_linux"))
_WEBUI_DIR = os.path.join(_REPO_ROOT, "webui")
_CONFIG_DIR = os.path.join(_REPO_ROOT, "config")
_SETTINGS_FILE = os.path.join(_CONFIG_DIR, "settings.json")

# nanolib is only importable on the target (aarch64) device and only needed
# for real hardware; --simulate must work even where it can't be imported.
try:
    from nanotec_nanolib import Nanolib
    _NANOLIB_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - depends on platform
    Nanolib = None
    _NANOLIB_IMPORT_ERROR = exc


# ---------------------------------------------------------------------------
# Controller identity
# ---------------------------------------------------------------------------

CART_SERIAL_SUFFIX = "0168"   # cart on the rail (already used in motion_test.py)
LIFT_SERIAL_SUFFIX = "0173"   # payload lift (template)

# Poll rate for the live readout shown in the UI. Slower than motion_test.py's
# 50 Hz control poll -- this only feeds a browser display and shares the bus
# lock with the control writes, so 10 Hz keeps the UI responsive without
# starving commands.
STATE_POLL_INTERVAL_S = 0.1


# ---------------------------------------------------------------------------
# Object dictionary entries (CiA 402 -- see C5-E manual and motion_test.py)
# ---------------------------------------------------------------------------

OD_CONTROL_WORD = (0x6040, 0x00, 16)
OD_STATUS_WORD = (0x6041, 0x00, 16)
OD_NANOJ_CONTROL = (0x2300, 0x00, 32)
OD_MODE_OF_OPERATION = (0x6060, 0x00, 8)
OD_TARGET_VELOCITY = (0x60FF, 0x00, 32)
# Digital Inputs (60FDh): bit 0 = negative limit switch (NLS), bit 1 =
# positive limit switch (PLS) -- see C5-E manual, chapter 10 "60FDh Digital
# Inputs" and chapter 7.1.2 "Digital inputs".
OD_DIGITAL_INPUTS = (0x60FD, 0x00, 32)
DIGITAL_INPUT_BIT_NEG_LIMIT = 0
DIGITAL_INPUT_BIT_POS_LIMIT = 1

# Statusword (6041h) state-machine mask/pattern (see decodeStatusword() in
# app.js for the full state table).
STATUSWORD_STATE_MASK = 0x6F
STATUSWORD_QUICK_STOP_ACTIVE = 0x07
STATUSWORD_OPERATION_ENABLED = 0x27

# _ensure_operation_enabled() polls the statusword until the CiA-402 state
# machine has worked through its enable transitions (each takes a controller
# cycle), so it doesn't race ahead of the drive. Bounded by the timeout so a
# stuck drive can't hang the request thread.
ENABLE_TIMEOUT_S = 1.0
ENABLE_POLL_S = 0.01

OD_PROFILE_ACCELERATION = (0x6083, 0x00, 32)
OD_PROFILE_DECELERATION = (0x6084, 0x00, 32)
OD_MOTION_PROFILE_TYPE = (0x6086, 0x00, 16)
# 60A4h subindices: 01h/02h/03h/04h begin/end accel/decel jerk.
OD_PROFILE_JERK_SUBS = [(0x60A4, sub, 32) for sub in (0x01, 0x02, 0x03, 0x04)]

# Analog Input 1 (3220h:01h): 10-bit ADC (0..1023) measuring the pendulum
# angle. See the wrap-around glitch note in motion_test.py.
OD_ANALOG_INPUT_1 = (0x3220, 0x01, 16)
ANALOG_INPUT_MIN = 0
ANALOG_INPUT_MAX = 1023
ANALOG_INPUT_JUMP_THRESHOLD = 512

# Live readout objects, shown in the UI. (key, index, sub, bits, signed, label,
# fmt) where fmt is None (plain), "hex", "statusword" or "controlword" -- the
# last two are decoded into their CiA 402 state-machine names (see app.js)
# instead of a raw value. Mirrors test_controllers.py's READ_OBJECTS plus the
# analog input.
READOUT_SPECS = [
    ("status_word", 0x6041, 0x00, 16, False, "Drive state (6041h)", "statusword"),
    ("velocity_actual", 0x606C, 0x00, 32, True, "Velocity actual value (rpm)", None),
    ("torque_actual", 0x6077, 0x00, 16, True, "Torque actual value", None),
    ("error_count", 0x1003, 0x00, 8, False, "Error count", None),
    ("analog_input_1", 0x3220, 0x01, 16, False, "Analog Input 1 (angle)", None),
    ("control_word", 0x6040, 0x00, 16, False, "Command (6040h)", "controlword"),
    ("digital_inputs", 0x60FD, 0x00, 32, False, "Digital Inputs (60FDh)", "hex"),
]

# Per-role readout. The lift has no pendulum sensor, so it drops the analog
# input row (and skips reading it on the bus). The cart keeps the full set.
READOUT_SPECS_BY_ROLE = {
    "cart": READOUT_SPECS,
    "lift": [spec for spec in READOUT_SPECS if spec[0] != "analog_input_1"],
}


def _to_signed(value, bits):
    """Reinterpret an unsigned register value as signed (from test_controllers.py)."""
    if value >= (1 << (bits - 1)):
        value -= (1 << bits)
    return value


def _quick_stop_active(status_word):
    """True if statusword (6041h) reports the CiA 402 'Quick stop active'
    state -- see STATUSWORD_STATE_MASK/STATUSWORD_QUICK_STOP_ACTIVE above."""
    if status_word is None:
        return False
    return (status_word & STATUSWORD_STATE_MASK) == STATUSWORD_QUICK_STOP_ACTIVE


def _operation_enabled(status_word):
    """True if statusword (6041h) reports the CiA 402 'Operation enabled'
    state."""
    if status_word is None:
        return False
    return (status_word & STATUSWORD_STATE_MASK) == STATUSWORD_OPERATION_ENABLED


# ---------------------------------------------------------------------------
# Parameter schema
# ---------------------------------------------------------------------------
#
# The UI renders its parameter controls generically from these schemas, so
# adding a control is a data change, not a UI rewrite. Each spec has:
#   key      : identifier used in the API
#   label    : shown in the UI
#   kind     : "select" | "number" | "slider"
#   default  : initial value
#   options  : [{value, label}, ...]           (select only)
#   min/max/step                                (number/slider)
#   software : True  -> kept in software, pushed to the drive at mode start
#   group    : "jog" | "pid" -> which set of controls it belongs to
#
# Each controller gets its own schema by role (PARAM_SPECS_BY_ROLE): the cart
# exposes the jog speed plus the full PID tuning set, the lift exposes only the
# jog speed (no PID) and with its own speed limits.

# CiA 402 mode + ramp written whenever a drive is enabled. Both are fixed now
# (the UI no longer exposes them): Profile Velocity with a jerk-limited ramp,
# matching motion_test.py.
DRIVE_MODE_PROFILE_VELOCITY = 3
MOTION_PROFILE_JERK_LIMITED = 3

# Manual (joystick) drive parameters. The manual drive is a spring-return
# one-axis joystick: stick displacement sets the target velocity directly, so
# jog_speed is the joystick's FULL-SCALE speed (velocity at the ends of travel),
# not a fixed jog speed. The cart also carries its own acceleration and jerk
# (applied to the drive when a push engages the ramp). The lift exposes only
# the full-scale speed -- with its own limit -- leaving its acceleration/jerk to
# whatever the drive is already configured with.
JOG_SPECS_CART = [
    {"key": "jog_speed", "label": "Joy max speed (rpm)", "kind": "slider", "group": "jog",
     "default": 700, "min": 50, "max": 700, "step": 10, "software": True},
    {"key": "jog_accel", "label": "Jog acceleration", "kind": "number", "group": "jog",
     "default": 1000, "min": 100, "max": 200000, "step": 100, "software": True},
    {"key": "jog_jerk", "label": "Jog jerk", "kind": "number", "group": "jog",
     "default": 12000, "min": 12000, "max": 200000, "step": 100, "software": True},
]
JOG_SPECS_LIFT = [
    {"key": "jog_speed", "label": "Joy max speed (rpm)", "kind": "slider", "group": "jog",
     "default": 400, "min": 50, "max": 500, "step": 10, "software": True},
]

# Software PID balance loop (cart only -- see run_pid_loop / motion_test.py).
# Every value is kept in software and pushed to the drive when the loop starts
# (see _apply_motion_profile). The setpoint is not exposed in the UI; it is
# fixed at PID_SETPOINT below. The gain defaults come straight from
# motion_test.py.
PID_PARAM_SPECS = [
    {"key": "kp", "label": "Kp (rpm / digit)", "kind": "number", "group": "pid",
     "default": -4.5, "min": -50, "max": 50, "step": 0.1, "software": True},
    {"key": "ki", "label": "Ki (rpm / digit*s)", "kind": "number", "group": "pid",
     "default": -0.01, "min": -10, "max": 10, "step": 0.01, "software": True},
    {"key": "kd", "label": "Kd (rpm / digit/s)", "kind": "number", "group": "pid",
     "default": -0.05, "min": -10, "max": 10, "step": 0.01, "software": True},
    {"key": "deadzone", "label": "Deadzone (digits)", "kind": "number", "group": "pid",
     "default": 15, "min": 0, "max": 200, "step": 1, "software": True},
    {"key": "max_speed", "label": "PID max speed (rpm)", "kind": "slider", "group": "pid",
     "default": 600, "min": 0, "max": 800, "step": 10, "software": True},
    {"key": "pid_accel", "label": "PID acceleration", "kind": "number", "group": "pid",
     "default": 18000, "min": 0, "max": 200000, "step": 100, "software": True},
    {"key": "pid_jerk", "label": "PID jerk", "kind": "number", "group": "pid",
     "default": 18000, "min": 0, "max": 200000, "step": 100, "software": True},
]

# Per-role parameter schema. The cart carries the PID tuning set; the lift is
# jog-speed-only.
PARAM_SPECS_BY_ROLE = {
    "cart": JOG_SPECS_CART + PID_PARAM_SPECS,
    "lift": JOG_SPECS_LIFT,
}

# PID loop constants that are not exposed as tunable params (from motion_test.py).
# Angle the PID loop holds the pendulum at -- the middle of the analog range
# (rail centre), matching POSITION_SETPOINT in motion_test.py.
PID_SETPOINT = round(ANALOG_INPUT_MAX / 2)
PID_DERIVATIVE_TAU_S = 0.1
PID_INTEGRAL_LIMIT = 200
PID_INTEGRAL_LEAK_RATE = 0.1
PID_INTERVAL_S = 0.02          # 50 Hz, matches motion_test.py
PID_MAX_DT_S = 5 * PID_INTERVAL_S


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class RailController:
    """One Nanotec motor controller (cart or lift).

    Wraps the connection handle plus a background readout poller, the live
    parameter set, hold-to-jog manual drive and the optional software PID
    balance loop. Every nanolib call goes through the shared bus lock, so the
    poller and the request-thread commands never touch the accessor at once.

    In simulate mode there is no accessor/handle: reads return values from a
    small internal physics stub instead, so the UI is fully exercisable
    without hardware.
    """

    def __init__(self, name, serial_suffix, accessor, handle, bus_lock,
                 simulate=False, role="cart"):
        self.name = name                    # "cart" | "lift"
        self.serial_suffix = serial_suffix
        self.role = role
        self._accessor = accessor
        self._handle = handle
        self._lock = bus_lock               # shared across all controllers on the bus
        self._simulate = simulate
        self.connected = simulate or handle is not None

        # Role-specific schemas (cart carries PID; lift is jog-speed-only and
        # has no analog-angle readout).
        self.param_specs = PARAM_SPECS_BY_ROLE[role]
        self.readout_specs = READOUT_SPECS_BY_ROLE[role]

        # Live parameter values, seeded from the schema defaults.
        self.params = {spec["key"]: spec["default"] for spec in self.param_specs}
        self._params_lock = threading.Lock()

        # Latest readout snapshot (updated by the poller).
        self._state = {key: None for (key, *_rest) in self.readout_specs}
        self._state["neg_limit"] = None
        self._state["pos_limit"] = None
        self._state_lock = threading.Lock()
        self._last_analog = None

        # Drive / status flags surfaced to the UI.
        self.drive_enabled = False          # Profile Velocity mode + operation enabled
        self.jog_direction = 0              # -1, 0, +1
        self.pid_running = False
        self.last_error = None

        # Threads.
        self._stop_event = threading.Event()
        self._poll_thread = None
        self._pid_thread = None
        self._pid_stop = threading.Event()

        # Simulation state (only used when self._simulate).
        self._sim_velocity = 0.0
        self._sim_position = 0.0
        self._sim_angle = ANALOG_INPUT_MAX / 2
        self._sim_target_velocity = 0.0
        self._sim_last = time.monotonic()

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        self._stop_event.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self):
        self.stop_pid()
        if self.connected and not self._simulate:
            try:
                self.stop_motor()
            except Exception:
                pass
        self._stop_event.set()
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2)
            self._poll_thread = None

    # -- low-level bus access ---------------------------------------------

    def _read(self, od):
        """Read a single OD index, returning None on error. Bus-locked."""
        index, sub, _bits = od
        with self._lock:
            result = self._accessor.readNumber(
                self._handle, Nanolib.OdIndex(index, sub))
        return None if result.hasError() else result.getResult()

    def _write(self, od, value):
        """Write a single OD index, returning True on success. Bus-locked."""
        index, sub, bits = od
        with self._lock:
            result = self._accessor.writeNumber(
                self._handle, int(value), Nanolib.OdIndex(index, sub), bits)
        if result.hasError():
            self.last_error = f"write {index:#06x}:{sub:02x} failed: {result.getError()}"
            return False
        return True

    # -- readout poller ----------------------------------------------------

    def _poll_loop(self):
        while not self._stop_event.is_set():
            if self._simulate:
                snapshot = self._simulate_state()
            else:
                snapshot = self._read_state()
            with self._state_lock:
                self._state = snapshot
            self._stop_event.wait(STATE_POLL_INTERVAL_S)

    def _read_state(self):
        snapshot = {}
        for key, index, sub, bits, signed, _label, _fmt in self.readout_specs:
            raw = self._read((index, sub, bits))
            if raw is None:
                snapshot[key] = None
                continue
            raw &= (1 << bits) - 1
            if key == "analog_input_1":
                raw = self._clamp_analog_jump(raw)
            snapshot[key] = _to_signed(raw, bits) if signed else raw

        digital_inputs = snapshot.get("digital_inputs")
        if digital_inputs is None:
            snapshot["neg_limit"] = None
            snapshot["pos_limit"] = None
        else:
            snapshot["neg_limit"] = bool(digital_inputs & (1 << DIGITAL_INPUT_BIT_NEG_LIMIT))
            snapshot["pos_limit"] = bool(digital_inputs & (1 << DIGITAL_INPUT_BIT_POS_LIMIT))

        return snapshot

    def _clamp_analog_jump(self, raw):
        """Guard against the analog wrap-around glitch (see motion_test.py)."""
        if raw is None:
            return self._last_analog
        if self._last_analog is not None:
            delta = raw - self._last_analog
            if abs(delta) > ANALOG_INPUT_JUMP_THRESHOLD:
                raw = ANALOG_INPUT_MAX if delta < 0 else ANALOG_INPUT_MIN
        self._last_analog = raw
        return raw

    def get_state(self):
        with self._state_lock:
            return dict(self._state)

    # -- parameters --------------------------------------------------------

    def get_params(self):
        with self._params_lock:
            return dict(self.params)

    def set_param(self, key, value):
        """Validate + store a parameter. All params are software: the value is
        pushed to the drive when its mode starts (jog / PID apply their own
        speed / accel / jerk). Returns (ok, message)."""
        spec = next((s for s in self.param_specs if s["key"] == key), None)
        if spec is None:
            return False, f"unknown parameter '{key}'"

        # Coerce to the appropriate type (only the PID gains are floats).
        try:
            value = float(value) if key in ("kp", "ki", "kd") else int(round(float(value)))
        except (TypeError, ValueError):
            return False, f"invalid value for '{key}': {value!r}"

        # Range check.
        if "min" in spec and value < spec["min"]:
            value = spec["min"]
        if "max" in spec and value > spec["max"]:
            value = spec["max"]

        with self._params_lock:
            self.params[key] = value
        return True, "ok"

    # -- drive: shared Profile Velocity primitives (from motion_test.py) ---

    def _apply_motion_profile(self, accel, jerk):
        """Write 6083h/6084h (accel/decel) and all four 60A4h (jerk) subindices.
        Called at the start of a cart jog or the PID loop so each ramps with
        its OWN acceleration/jerk. The lift jog has no accel/jerk params, so it
        skips this and leaves the drive's configured ramp untouched."""
        if self._simulate:
            return True
        self._write(OD_PROFILE_ACCELERATION, accel)
        self._write(OD_PROFILE_DECELERATION, accel)
        for jerk_od in OD_PROFILE_JERK_SUBS:
            self._write(jerk_od, jerk)
        return True

    def enable_drive(self):
        """Select Profile Velocity mode with a jerk-limited ramp and switch the
        CiA 402 state machine to 'operation enabled'. The accel/jerk ramp is
        applied by the caller (jog / PID), since each has its own values."""
        if self._simulate:
            self.drive_enabled = True
            return True
        # Stop any running NanoJ program.
        self._write(OD_NANOJ_CONTROL, 0)
        self._write(OD_MODE_OF_OPERATION, DRIVE_MODE_PROFILE_VELOCITY)
        self._write(OD_MOTION_PROFILE_TYPE, MOTION_PROFILE_JERK_LIMITED)
        self._write(OD_TARGET_VELOCITY, 0)
        # State machine: shutdown -> switch on -> operation enabled.
        for command in (0x06, 0x07, 0x0F):
            if not self._write(OD_CONTROL_WORD, command):
                return False
        self.drive_enabled = True
        return True

    def _recover_from_endstop(self):
        """Return the drive from 'Quick stop active' (forced by a triggered
        limit switch) to 'Operation enabled' without commanding motion, per
        the C5-E manual chapter 5.4. Returns the last statusword read.

        Recovery is a 0 -> 1 edge on controlword bit 2 (quick stop): a
        triggered limit switch leaves this bit untouched (it's still high from
        normal operation), so force it low (0x02) then request Enable Operation
        (0x0F), whose bit 2 rises -- CiA-402 transition 16. Bit 4 stays 0 and
        target velocity is held at 0, so nothing moves.

        The edge is re-issued until the drive actually reports Operation
        enabled (bounded by ENABLE_TIMEOUT_S), because the drive finishes its
        quick-stop deceleration ramp before accepting the transition: a single
        edge issued while the cart is still braking is consumed without a state
        change, and once it coasts to standstill bit 2 is already high again,
        so there is no fresh edge -- it stays stuck in Quick stop active. That
        is what made the first jog after an endstop fail; re-issuing the edge
        lands the transition on the first cycle after standstill.

        Assumes 605Ah (Quick Stop Option Code) is already configured on the
        drive to keep the motor energized in Quick stop active, so forcing
        bit 2 low doesn't switch it off.
        """
        if self._simulate:
            self.drive_enabled = True
            return STATUSWORD_OPERATION_ENABLED

        self._write(OD_TARGET_VELOCITY, 0)

        deadline = time.monotonic() + ENABLE_TIMEOUT_S
        while True:
            self._write(OD_CONTROL_WORD, 0x02)   # force quick-stop bit low
            self._write(OD_CONTROL_WORD, 0x0F)   # rising edge -> operation enabled
            status_word = self._read(OD_STATUS_WORD)
            if _operation_enabled(status_word) or time.monotonic() >= deadline:
                return status_word
            time.sleep(ENABLE_POLL_S)

    def _wait_for_operation_enabled(self):
        """Poll statusword (6041h) until the drive reports 'Operation enabled',
        giving the CiA-402 state machine time to work through its shutdown ->
        switch on -> enable operation transitions (each takes a controller
        cycle). Returns the last statusword read; gives up after
        ENABLE_TIMEOUT_S so a stuck read can't hang the request thread."""
        deadline = time.monotonic() + ENABLE_TIMEOUT_S
        while True:
            status_word = self._read(OD_STATUS_WORD)
            if _operation_enabled(status_word) or time.monotonic() >= deadline:
                return status_word
            time.sleep(ENABLE_POLL_S)

    def _ensure_operation_enabled(self):
        """Make sure the drive is in 'Operation enabled' before jogging or
        starting the PID loop. Recovers from a limit-switch-triggered 'Quick
        stop active' via _recover_from_endstop(); otherwise runs the normal
        enable_drive() sequence and waits for it to land. Both paths wait for
        the state machine to actually reach Operation enabled rather than
        racing a single read ahead of the drive (that race is why jog used to
        need two clicks). Uses fresh statusword reads, never the poller's
        up-to-STATE_POLL_INTERVAL_S-old snapshot."""
        if self._simulate:
            self.drive_enabled = True
            return True

        status_word = self._read(OD_STATUS_WORD)

        if _quick_stop_active(status_word):
            status_word = self._recover_from_endstop()
        elif not _operation_enabled(status_word):
            if not self.enable_drive():
                return False
            status_word = self._wait_for_operation_enabled()

        if not _operation_enabled(status_word):
            self.last_error = "drive did not reach Operation enabled"
            self.drive_enabled = False
            return False

        self.last_error = None
        self.drive_enabled = True
        return True

    def set_target_velocity(self, rpm):
        if self._simulate:
            self._sim_target_velocity = float(rpm)
            return True
        return self._write(OD_TARGET_VELOCITY, int(rpm))

    def stop_motor(self):
        """Command zero velocity and drop back to 'switched on' (controlword 0x06)."""
        self.jog_direction = 0
        if self._simulate:
            self._sim_target_velocity = 0.0
            self.drive_enabled = False
            return True
        self._write(OD_TARGET_VELOCITY, 0)
        ok = self._write(OD_CONTROL_WORD, 0x06)
        self.drive_enabled = False
        return ok

    # -- manual jog (hold-to-jog) -----------------------------------------

    def jog(self, direction):
        """Start jogging: direction is -1, 0 or +1. Enables the drive on
        demand and sets target velocity to +/- the jog_speed param.

        For the LIFT this is the same generic Profile Velocity move; the
        direction is interpreted as up (+1) / down (-1) by the UI. Real lift
        travel limits / homing would gate this -- see lift_up/lift_down.

        End stops: a triggered limit switch only blocks the direction that
        drove into it (positive limit switch -> positive direction, and
        vice versa, matching the C5-E's own NLS/PLS naming) -- the opposite
        direction always stays available so the cart can be driven back off
        the switch. Commanding that opposite direction also recovers the
        drive out of the 'Quick stop active' state the limit switch forced
        it into (see _recover_from_endstop()), so normal operation resumes
        as soon as it's commanded.
        """
        direction = max(-1, min(1, int(direction)))
        if direction == 0:
            return self.jog_stop()
        if self.pid_running:
            return False, "stop the PID loop before jogging"

        state = self.get_state()
        if direction > 0 and state.get("pos_limit"):
            self.last_error = "positive end stop triggered -- only negative direction allowed"
            return False, self.last_error
        if direction < 0 and state.get("neg_limit"):
            self.last_error = "negative end stop triggered -- only positive direction allowed"
            return False, self.last_error

        if not self._ensure_operation_enabled():
            return False, self.last_error or "failed to enable drive"
        p = self.get_params()
        # The cart ramps with its own jog accel/jerk; the lift has none of
        # those params and leaves the drive's configured ramp untouched.
        if "jog_accel" in p and "jog_jerk" in p:
            self._apply_motion_profile(p["jog_accel"], p["jog_jerk"])
        if not self.set_target_velocity(direction * p["jog_speed"]):
            return False, self.last_error or "failed to set velocity"
        self.jog_direction = direction
        return True, "ok"

    def jog_velocity(self, velocity):
        """Joystick drive: command an arbitrary signed target velocity (rpm),
        whose magnitude is how far the stick is pushed. 0 releases the stick
        (ramp to zero, stay enabled) so the next push responds immediately.

        The magnitude is clamped to the configured full-scale joy speed
        (jog_speed). End-stop and PID gating match jog(): a triggered limit
        switch only blocks the direction that drove into it.

        Engagement is lazy: the CiA-402 enable + motion-profile writes only run
        when starting from rest or reversing across zero, so the stream of
        small updates a dragged stick produces is just a target-velocity write
        each -- not a full re-enable every time."""
        try:
            velocity = int(round(float(velocity)))
        except (TypeError, ValueError):
            return False, f"invalid velocity {velocity!r}"
        if self.pid_running:
            return False, "stop the PID loop before jogging"

        # Clamp magnitude to the full-scale joy speed so the stick can never
        # command more than the configured maximum.
        limit = int(self.get_params().get("jog_speed", 0))
        velocity = max(-limit, min(limit, velocity))

        direction = (velocity > 0) - (velocity < 0)
        if direction == 0:
            return self.jog_stop()

        state = self.get_state()
        if direction > 0 and state.get("pos_limit"):
            self.last_error = "positive end stop triggered -- only negative direction allowed"
            return False, self.last_error
        if direction < 0 and state.get("neg_limit"):
            self.last_error = "negative end stop triggered -- only positive direction allowed"
            return False, self.last_error

        # Only run the (heavy) enable + ramp setup when engaging from rest or
        # reversing direction; a same-direction update is just a velocity write.
        if self.jog_direction != direction:
            if not self._ensure_operation_enabled():
                return False, self.last_error or "failed to enable drive"
            p = self.get_params()
            if "jog_accel" in p and "jog_jerk" in p:
                self._apply_motion_profile(p["jog_accel"], p["jog_jerk"])

        if not self.set_target_velocity(velocity):
            return False, self.last_error or "failed to set velocity"
        self.jog_direction = direction
        return True, "ok"

    def jog_stop(self):
        """Release jog: ramp to zero but stay in operation enabled so the next
        press responds immediately."""
        self.jog_direction = 0
        if not self.set_target_velocity(0):
            return False, self.last_error or "failed to stop jog"
        return True, "ok"

    # -- lift-specific template -------------------------------------------
    # The readout above already works for the lift unchanged. These wrappers
    # give the payload winch its own up/down semantics. For now they are the
    # generic jog; fill in the real behaviour later.

    def lift_up(self):
        # TODO(lift): enforce upper travel limit / max payload height, and
        # any load-holding brake release sequence before moving up.
        return self.jog(+1)

    def lift_down(self):
        # TODO(lift): enforce lower travel limit and controlled-descent /
        # brake behaviour so the payload can't free-fall.
        return self.jog(-1)

    # -- software PID balance loop (from motion_test.run_position_control) --

    def start_pid(self):
        if not any(spec["group"] == "pid" for spec in self.param_specs):
            return False, f"PID not available for the {self.name}"
        if self.pid_running:
            return True, "already running"
        if not self._ensure_operation_enabled():
            return False, self.last_error or "failed to enable drive"
        p = self.get_params()
        self._apply_motion_profile(p["pid_accel"], p["pid_jerk"])
        self._pid_stop.clear()
        self._pid_thread = threading.Thread(target=self.run_pid_loop, daemon=True)
        self._pid_thread.start()
        self.pid_running = True
        return True, "ok"

    def stop_pid(self):
        if not self.pid_running:
            return True, "not running"
        self._pid_stop.set()
        if self._pid_thread is not None:
            self._pid_thread.join(timeout=2)
            self._pid_thread = None
        self.pid_running = False
        self.set_target_velocity(0)
        return True, "ok"

    def run_pid_loop(self):
        """Direct velocity PID on the analog angle -> hold it at PID_SETPOINT.

        Faithful to motion_test.run_position_control(): D term on the raw
        angle (not the deadzoned error), anti-windup + slow integral leak,
        output clamped to +/- max_speed. The gains are read live from params
        every iteration, so the UI retunes it on the fly; the setpoint is
        fixed (PID_SETPOINT) and no longer part of the UI.

        End stops: unlike jog(), the PID output can swing into a limit
        switch mid-run rather than only when a fixed direction is first
        commanded, so this checks on every iteration instead of only at
        start_pid(). Uses the poller's cached state (cheap, no bus round
        trip) to clamp velocity away from a triggered switch and to detect
        Quick stop active; _ensure_operation_enabled() -- with its own
        fresh read -- is only actually invoked (bus round trip(s)) when
        that cached state suggests it's needed.
        """
        integral = 0.0
        filtered_rate = 0.0
        last_angle = None
        last_time = None

        while not self._pid_stop.is_set():
            state = self.get_state()
            angle = state.get("analog_input_1")
            p = self.get_params()
            now = time.monotonic()

            if angle is not None:
                error = PID_SETPOINT - angle
                if abs(error) <= p["deadzone"]:
                    error = 0

                if last_angle is not None and last_time is not None:
                    dt = min(now - last_time, PID_MAX_DT_S)
                    if dt > 0:
                        raw_rate = (angle - last_angle) / dt
                        alpha = dt / (PID_DERIVATIVE_TAU_S + dt)
                        filtered_rate += alpha * (raw_rate - filtered_rate)
                        if p["ki"] != 0:
                            candidate = integral + error * dt
                            if abs(p["ki"] * candidate) <= PID_INTEGRAL_LIMIT:
                                integral = candidate
                            integral -= integral * min(1.0, PID_INTEGRAL_LEAK_RATE * dt)

                last_angle = angle
                last_time = now

                velocity = (p["kp"] * error
                            + p["ki"] * integral
                            + p["kd"] * filtered_rate)
                velocity = max(-p["max_speed"], min(p["max_speed"], velocity))
                if state.get("pos_limit") and velocity > 0:
                    velocity = 0
                if state.get("neg_limit") and velocity < 0:
                    velocity = 0

                if _quick_stop_active(state.get("status_word")):
                    self._ensure_operation_enabled()

                self.set_target_velocity(round(velocity))

            self._pid_stop.wait(PID_INTERVAL_S)

        self.set_target_velocity(0)

    # -- simulation --------------------------------------------------------

    def _simulate_state(self):
        """Cheap physics stub so the UI works with no hardware."""
        now = time.monotonic()
        dt = min(now - self._sim_last, 0.5)
        self._sim_last = now

        # First-order velocity ramp toward the commanded target.
        self._sim_velocity += (self._sim_target_velocity - self._sim_velocity) * min(1.0, dt * 5)

        # Pendulum-ish angle: driven by velocity, plus a slow idle sway.
        self._sim_angle += -self._sim_velocity * dt * 0.05
        self._sim_angle += math.sin(now * 0.7) * 2.0 * dt
        self._sim_angle = max(ANALOG_INPUT_MIN, min(ANALOG_INPUT_MAX, self._sim_angle))

        # 6041h: operation-enabled (0x0637) vs switch-on-disabled (0x0640).
        status_word = 0x0637 if self.drive_enabled else 0x0640
        # No physical limit switches to simulate; report both clear.
        return {
            "status_word": status_word,
            "velocity_actual": int(self._sim_velocity),
            "torque_actual": int(self._sim_velocity * 0.1),
            "error_count": 0,
            "analog_input_1": int(self._sim_angle),
            "control_word": 0x000F if self.drive_enabled else 0x0006,
            "digital_inputs": 0,
            "neg_limit": False,
            "pos_limit": False,
        }


# ---------------------------------------------------------------------------
# Controller manager (discovery + connection of both controllers)
# ---------------------------------------------------------------------------

class ScanBusCallback(Nanolib.NlcScanBusCallback if Nanolib else object):
    """Minimal scan-progress callback (scanDevices requires one)."""

    def callback(self, info, devices_found, data):  # pragma: no cover - hw path
        if info == Nanolib.BusScanInfo_Start:
            print("    scanning ", end="", flush=True)
        elif info == Nanolib.BusScanInfo_Progress:
            print(".", end="", flush=True)
        elif info == Nanolib.BusScanInfo_Finished:
            print(" done")
        return Nanolib.ResultVoid()


class ControllerManager:
    """Discovers the Modbus TCP bus, connects to the cart and lift controllers
    (by serial suffix) and owns them. All bus access is serialised through a
    single lock shared by both controllers.
    """

    TARGETS = [
        ("cart", CART_SERIAL_SUFFIX, "cart"),
        ("lift", LIFT_SERIAL_SUFFIX, "lift"),
    ]

    def __init__(self, simulate=False):
        self.simulate = simulate
        self._accessor = None
        self._bus_id = None
        self._bus_lock = threading.RLock()
        self.controllers = {}   # name -> RailController

    def connect(self):
        if self.simulate:
            print("Simulate mode: no hardware, using fake controllers.")
            for name, suffix, role in self.TARGETS:
                ctrl = RailController(name, suffix, None, None, self._bus_lock,
                                      simulate=True, role=role)
                ctrl.start()
                self.controllers[name] = ctrl
            return

        if Nanolib is None:
            raise RuntimeError(
                f"nanolib could not be imported ({_NANOLIB_IMPORT_ERROR}); "
                "run on the target device or use --simulate.")

        self._accessor = Nanolib.getNanoLibAccessor()
        self._accessor.setLoggingLevel(Nanolib.LogLevel_Off)
        scan_callback = ScanBusCallback()

        print("Discovering Modbus TCP bus hardware ...")
        buses = self._discover_modbus_tcp_buses()
        wanted = {suffix: (name, role) for name, suffix, role in self.TARGETS}
        found = {}

        for bus_id in buses:
            print(f"\n=== Bus: {bus_id.getName()} ===")
            open_result = self._accessor.openBusHardwareWithProtocol(
                bus_id, Nanolib.BusHardwareOptions())
            if open_result.hasError():
                print(f"  ERROR opening bus: {open_result.getError()}")
                continue

            scan_result = self._accessor.scanDevices(bus_id, scan_callback)
            if scan_result.hasError():
                print(f"  ERROR scanning devices: {scan_result.getError()}")
                self._accessor.closeBusHardware(bus_id)
                continue

            device_ids = scan_result.getResult() or []
            print(f"  Found {len(device_ids)} device(s).")
            self._bus_id = bus_id

            for device_id in device_ids:
                description = device_id.getDescription() or f"id {device_id.getDeviceId()}"
                add_result = self._accessor.addDevice(device_id)
                if add_result.hasError():
                    print(f"  ERROR adding {description}: {add_result.getError()}")
                    continue
                handle = add_result.getResult()
                connect_result = self._accessor.connectDevice(handle)
                if connect_result.hasError():
                    print(f"  ERROR connecting {description}: {connect_result.getError()}")
                    self._accessor.removeDevice(handle)
                    continue

                serial_result = self._accessor.getDeviceSerialNumber(handle)
                serial = str(serial_result.getResult()) if not serial_result.hasError() else ""

                matched = next((suf for suf in wanted if serial.endswith(suf)), None)
                if matched and matched not in found:
                    name, role = wanted[matched]
                    print(f"  --> {name.upper()}: serial '{serial}' matches ...{matched}")
                    ctrl = RailController(name, matched, self._accessor, handle,
                                          self._bus_lock, simulate=False, role=role)
                    ctrl.start()
                    self.controllers[name] = ctrl
                    found[matched] = handle
                else:
                    # Not one of ours (or a duplicate): release it again.
                    self._accessor.disconnectDevice(handle)
                    self._accessor.removeDevice(handle)

            # Keep the bus open if we bound any controller on it.
            if not any(h for suf, h in found.items()):
                self._accessor.closeBusHardware(bus_id)
                self._bus_id = None
            if len(found) == len(wanted):
                break

        for name, suffix, _role in self.TARGETS:
            if name not in self.controllers:
                print(f"WARNING: {name} controller (serial ...{suffix}) not found.")

    def _discover_modbus_tcp_buses(self):
        result = self._accessor.listAvailableBusHardware()
        if result.hasError():
            raise RuntimeError(f"listing bus hardware failed: {result.getError()}")
        tcp = []
        for bus_id in result.getResult():
            if bus_id.getProtocol() == Nanolib.BUS_HARDWARE_ID_PROTOCOL_MODBUS_TCP:
                tcp.append(bus_id)
        return tcp

    def get(self, name):
        return self.controllers.get(name)

    # -- settings persistence (config/settings.json) -----------------------

    def save_settings(self):
        """Write every controller's current params to _SETTINGS_FILE,
        creating config/ if it doesn't exist yet. Written via a temp file +
        os.replace so a crash mid-write can't leave a truncated/corrupt file
        behind for load_settings() to trip over."""
        data = {name: ctrl.get_params() for name, ctrl in self.controllers.items()}
        try:
            os.makedirs(_CONFIG_DIR, exist_ok=True)
            tmp_path = _SETTINGS_FILE + ".tmp"
            with open(tmp_path, "w") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
            os.replace(tmp_path, _SETTINGS_FILE)
        except OSError as exc:
            return False, f"failed to save settings: {exc}"
        return True, f"settings saved to {_SETTINGS_FILE}"

    def load_settings(self):
        """Load _SETTINGS_FILE (if present) onto the live controllers. Falls
        back to whatever defaults are already in place (from the role schema) if
        the file is missing or malformed -- this must never raise, since it
        also runs unattended at startup."""
        if not os.path.isfile(_SETTINGS_FILE):
            return False, "no settings file present; using defaults"
        try:
            with open(_SETTINGS_FILE) as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            return False, f"could not read settings file, using defaults: {exc}"
        if not isinstance(data, dict):
            return False, "settings file malformed, using defaults"

        applied = 0
        for name, params in data.items():
            ctrl = self.controllers.get(name)
            if ctrl is None or not isinstance(params, dict):
                continue
            for key, value in params.items():
                ok, _message = ctrl.set_param(key, value)
                if ok:
                    applied += 1
        return True, f"loaded {applied} parameter(s) from {_SETTINGS_FILE}"

    def shutdown(self):
        for ctrl in self.controllers.values():
            try:
                ctrl.stop()
            except Exception as exc:
                print(f"  error stopping {ctrl.name}: {exc}")
        if not self.simulate and self._accessor is not None:
            for ctrl in self.controllers.values():
                if ctrl._handle is not None:
                    try:
                        self._accessor.disconnectDevice(ctrl._handle)
                        self._accessor.removeDevice(ctrl._handle)
                    except Exception:
                        pass
            if self._bus_id is not None:
                try:
                    self._accessor.closeBusHardware(self._bus_id)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


class RailRequestHandler(BaseHTTPRequestHandler):
    """Serves the single-page UI and the JSON control API.

    GET  /                       -> webui/index.html
    GET  /style.css, /app.js     -> static assets
    GET  /api/config             -> parameter schema + controller list
    GET  /api/state              -> live readout + params + flags for both
    POST /api/<name>/param       -> {key, value}
    POST /api/<name>/jog         -> {direction: -1|0|1}
    POST /api/<name>/jog_velocity-> {velocity: signed rpm}  (joystick drive)
    POST /api/<name>/jog_stop
    POST /api/<name>/stop
    POST /api/<name>/enable
    POST /api/<name>/pid         -> {action: "start"|"stop"}
    POST /api/<name>/lift        -> {direction: "up"|"down"|"stop"}  (lift only)
    POST /api/settings/save      -> writes current params of all controllers
                                     to config/settings.json
    POST /api/settings/load      -> re-reads config/settings.json and applies
                                     it to the live controllers
    """

    manager = None  # set by run_server()

    def log_message(self, fmt, *args):  # quieter logging
        pass

    # -- helpers -----------------------------------------------------------

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, rel_path):
        # Prevent path traversal; only serve from the webui/ folder.
        safe = os.path.normpath(rel_path).lstrip("/\\")
        full = os.path.join(_WEBUI_DIR, safe)
        if not full.startswith(_WEBUI_DIR) or not os.path.isfile(full):
            self.send_error(404, "Not found")
            return
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", _STATIC_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def _snapshot(self):
        controllers = {}
        for name, ctrl in self.manager.controllers.items():
            controllers[name] = {
                "connected": ctrl.connected,
                "drive_enabled": ctrl.drive_enabled,
                "jog_direction": ctrl.jog_direction,
                "pid_running": ctrl.pid_running,
                "last_error": ctrl.last_error,
                "state": ctrl.get_state(),
                "params": ctrl.get_params(),
            }
        return controllers

    # -- routes ------------------------------------------------------------

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._send_static("index.html")
        if path == "/api/config":
            return self._send_json({
                "controllers": [
                    {
                        "name": name,
                        "suffix": ctrl.serial_suffix,
                        "role": ctrl.role,
                        "params": ctrl.param_specs,
                        "readout": [
                            {"key": k, "label": lbl, "fmt": fmt}
                            for (k, _i, _s, _b, _sg, lbl, fmt) in ctrl.readout_specs
                        ],
                    }
                    for name, ctrl in self.manager.controllers.items()
                ],
                "simulate": self.manager.simulate,
            })
        if path == "/api/state":
            return self._send_json({"controllers": self._snapshot()})
        if path.startswith("/api/"):
            return self.send_error(404, "Unknown API endpoint")
        # Static asset (style.css, app.js, ...).
        return self._send_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "api":
            return self.send_error(404, "Unknown API endpoint")
        _api, name, action = parts

        if name == "settings":
            if action == "save":
                ok, message = self.manager.save_settings()
            elif action == "load":
                ok, message = self.manager.load_settings()
            else:
                ok, message = False, f"unknown settings action '{action}'"
            return self._send_json({"ok": ok, "message": message,
                                    "controllers": self._snapshot()},
                                   200 if ok else 400)

        ctrl = self.manager.get(name)
        if ctrl is None:
            return self._send_json({"ok": False, "error": f"no '{name}' controller"}, 404)

        body = self._read_body()
        try:
            ok, message = self._dispatch(ctrl, action, body)
        except Exception as exc:  # never 500 the control panel
            ok, message = False, f"{type(exc).__name__}: {exc}"

        status = 200 if ok else 400
        return self._send_json({"ok": ok, "message": message,
                                "controller": self._snapshot().get(name)}, status)

    def _dispatch(self, ctrl, action, body):
        if action == "param":
            return ctrl.set_param(body.get("key"), body.get("value"))
        if action == "jog":
            return ctrl.jog(body.get("direction", 0))
        if action == "jog_velocity":
            return ctrl.jog_velocity(body.get("velocity", 0))
        if action == "jog_stop":
            return ctrl.jog_stop()
        if action == "stop":
            return (ctrl.stop_motor(), "stopped")
        if action == "enable":
            return (ctrl.enable_drive(), "drive enabled")
        if action == "pid":
            if body.get("action") == "start":
                return ctrl.start_pid()
            return ctrl.stop_pid()
        if action == "lift":
            direction = body.get("direction")
            if direction == "up":
                return ctrl.lift_up()
            if direction == "down":
                return ctrl.lift_down()
            return ctrl.jog_stop()
        return False, f"unknown action '{action}'"


def run_server(manager, host, port):
    handler = partial(RailRequestHandler)
    RailRequestHandler.manager = manager
    httpd = ThreadingHTTPServer((host, port), handler)
    where = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}/"
    print(f"\nRail web UI serving at {where}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down ...")
    finally:
        httpd.shutdown()
        manager.shutdown()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--simulate", action="store_true",
                        help="Run with fake controllers (no hardware). Useful for UI work.")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Interface to bind (default: 0.0.0.0, all interfaces).")
    parser.add_argument("--port", type=int, default=8080,
                        help="TCP port to serve on (default: 8080).")
    return parser.parse_args()


def main():
    args = parse_args()
    manager = ControllerManager(simulate=args.simulate)
    manager.connect()
    if not manager.controllers:
        print("No controllers available. Exiting.")
        return 1
    _ok, message = manager.load_settings()
    print(message)
    run_server(manager, args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
