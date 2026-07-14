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
  * a parameter section (dropdowns, number entries and sliders),
  * PID gain tuning (Kp/Ki/Kd) with a start/stop for the software balance
    loop, and
  * manual "hold to jog" drive buttons plus a STOP.

The CART is fully wired up. The LIFT reuses the exact same readout, and its
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

# Limit Switch Error Option Code (3701h) and Quick Stop Option Code (605Ah):
# both involved in recovering from a limit-switch-triggered Quick stop
# active -- see RailController._recover_from_endstop() for why.
OD_LIMIT_SWITCH_OPTION = (0x3701, 0x00, 16)
LIMIT_SWITCH_OPTION_DISCARD = -2   # "no reaction, discard the limit switch position"
OD_QUICK_STOP_OPTION = (0x605A, 0x00, 16)
QUICK_STOP_OPTION_STAY_ENABLED = 6  # "quick stop ramp, stay energized in Quick stop active"

# Statusword (6041h) state-machine mask/pattern (see decodeStatusword() in
# app.js for the full state table).
STATUSWORD_STATE_MASK = 0x6F
STATUSWORD_QUICK_STOP_ACTIVE = 0x07
STATUSWORD_OPERATION_ENABLED = 0x27

# How many times _ensure_operation_enabled() retries the endstop recovery
# sequence before falling back to enable_drive() -- see that method.
ENDSTOP_RECOVERY_ATTEMPTS = 8

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
# The UI renders its parameter controls generically from this schema, so
# adding a control -- or the lift's future parameters -- is a data change, not
# a UI rewrite. Each spec has:
#   key      : identifier used in the API
#   label    : shown in the UI
#   kind     : "select" | "number" | "slider"
#   default  : initial value
#   options  : [{value, label}, ...]           (select only)
#   min/max/step                                (number/slider)
#   od       : (index, sub, bits) written to the drive when changed, or
#   od_jerk  : True  -> written to all four 60A4h subindices, or
#   software : True  -> kept in software, pushed to the drive at mode start
#   group    : "jog" | "pid" -> which set of controls it belongs to

# CiA 402 mode + ramp written whenever a drive is enabled. Both are fixed now
# (the UI no longer exposes them): Profile Velocity with a jerk-limited ramp,
# matching motion_test.py.
DRIVE_MODE_PROFILE_VELOCITY = 3
MOTION_PROFILE_JERK_LIMITED = 3

# Shared parameter schema. The manual (jog) drive and the PID loop each carry
# their OWN speed / acceleration / jerk, so tuning one never disturbs the
# other. Every value is kept in software and pushed to the drive at the moment
# that mode starts (see _apply_motion_profile). The PID gain defaults come
# straight from motion_test.py.
PARAM_SPECS = [
    # --- Manual (hold-to-jog) drive ---
    {"key": "jog_speed", "label": "Jog speed (rpm)", "kind": "slider", "group": "jog",
     "default": 500, "min": 0, "max": 800, "step": 10, "software": True},
    {"key": "jog_accel", "label": "Jog acceleration", "kind": "number", "group": "jog",
     "default": 600, "min": 0, "max": 200000, "step": 100, "software": True},
    {"key": "jog_jerk", "label": "Jog jerk", "kind": "number", "group": "jog",
     "default": 4000, "min": 0, "max": 200000, "step": 100, "software": True},

    # --- Software PID balance loop (see run_pid_loop / motion_test.py) ---
    # The setpoint is not exposed in the UI; it is fixed at PID_SETPOINT below.
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
     "default": 20000, "min": 0, "max": 200000, "step": 100, "software": True},
    {"key": "pid_jerk", "label": "PID jerk", "kind": "number", "group": "pid",
     "default": 20000, "min": 0, "max": 200000, "step": 100, "software": True},
]

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

        # Live parameter values, seeded from the schema defaults.
        self.params = {spec["key"]: spec["default"] for spec in PARAM_SPECS}
        self._params_lock = threading.Lock()

        # Latest readout snapshot (updated by the poller).
        self._state = {key: None for (key, *_rest) in READOUT_SPECS}
        self._state["neg_limit"] = None
        self._state["pos_limit"] = None
        self._state_lock = threading.Lock()
        self._last_analog = None
        # 3701h value saved while temporarily overridden to -2 during end
        # stop recovery (see _recover_from_endstop()); None means no
        # override is active. Restored by _read_state() as soon as the
        # limit switch physically clears.
        self._limit_switch_option_saved = None
        # True once 605Ah has been confirmed set to
        # QUICK_STOP_OPTION_STAY_ENABLED this session (see
        # _recover_from_endstop()); avoids re-writing it on every recovery.
        self._quick_stop_option_configured = False

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
        for key, index, sub, bits, signed, _label, _fmt in READOUT_SPECS:
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

        # Once both switches read definitively clear (not just unknown -- a
        # failed read must not be mistaken for "released"), restore the
        # option code _recover_from_endstop() overrode to -2, re-arming end
        # stop protection for the axis.
        if (self._limit_switch_option_saved is not None
                and snapshot["neg_limit"] is False and snapshot["pos_limit"] is False):
            if self._write(OD_LIMIT_SWITCH_OPTION, self._limit_switch_option_saved):
                self._limit_switch_option_saved = None
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
        spec = next((s for s in PARAM_SPECS if s["key"] == key), None)
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
        Called at the start of a jog or the PID loop so the manual drive and
        the PID loop each ramp with their OWN acceleration/jerk."""
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
        """Bring the drive from 'Quick stop active' (forced by a triggered
        limit switch, see C5-E manual chapter 5.4) back to 'Operation
        enabled', per the manual's recipe under 3701h ("Discarding the
        limit switch position"):

        1. Fix 605Ah (Quick Stop Option Code) to
           QUICK_STOP_OPTION_STAY_ENABLED first. Its default (2, "brake
           then Switch on disabled") governs what a controlword quick-stop
           command does -- and step 2 below issues exactly that -- so
           without this fix, step 2 doesn't just manufacture a harmless
           edge, it re-triggers a real switch-off on top of whatever the
           limit switch already did.
        2. A 0 -> 1 edge on controlword bit 2 (quick stop): the manual is
           explicit that this bit is left untouched when a limit switch
           triggers the state change, so the normal enable sequence
           (0x06 -> 0x07 -> 0x0F, all of which already have bit 2 set) has
           no effect. Force it low (0x02) then request Enable Operation
           (0x0F), whose bit 2 now rises.
        3. Discard the noted limit-switch position (3701h = -2), or the
           drive re-applies its configured reaction against the
           still-triggered switch and trips straight back down. The device
           rejects this write while still literally in Quick stop active,
           hence it comes after the edge, not before -- which leaves a
           race the caller (_ensure_operation_enabled()) retries.

        Target velocity is held at 0 throughout, so nothing moves until the
        caller (jog(), already restricted to the direction away from the
        triggered switch) commands it. _read_state() restores the saved
        3701h value once both switches read clear.
        """
        if self._simulate:
            self.drive_enabled = True
            return True

        if not self._quick_stop_option_configured:
            if self._write(OD_QUICK_STOP_OPTION, QUICK_STOP_OPTION_STAY_ENABLED):
                self._quick_stop_option_configured = True

        self._write(OD_TARGET_VELOCITY, 0)

        if not self._write(OD_CONTROL_WORD, 0x02):   # force quick-stop bit low
            return False
        if not self._write(OD_CONTROL_WORD, 0x0F):   # rising edge -> operation enabled
            return False

        if self._limit_switch_option_saved is None:
            saved = self._read(OD_LIMIT_SWITCH_OPTION)
            # Fall back to 6 (this axis's evident config) on a failed read,
            # so there's still a sane value to restore once clear.
            self._limit_switch_option_saved = 6 if saved is None else saved
        if not self._write(OD_LIMIT_SWITCH_OPTION, LIMIT_SWITCH_OPTION_DISCARD):
            return False
        return True

    def _ensure_operation_enabled(self):
        """Make sure the drive is in 'Operation enabled' before jogging or
        starting the PID loop, recovering from a limit-switch-triggered
        'Quick stop active' if necessary.

        Always checks a *fresh* statusword read, never the poller's
        up-to-STATE_POLL_INTERVAL_S-old snapshot: _recover_from_endstop()'s
        edge races the drive's own re-evaluation of the still-triggered
        switch and doesn't reliably land in Operation enabled on the first
        try (it can bounce to Switch on disabled, or its 3701h write can be
        rejected outright -- see that method). So this retries it up to
        ENDSTOP_RECOVERY_ATTEMPTS times while still stuck in Quick stop
        active, then falls through to the plain enable_drive() sequence,
        which reliably works from wherever the drive settled once it's no
        longer literally in that state.
        """
        if self._simulate:
            self.drive_enabled = True
            return True

        status_word = self._read(OD_STATUS_WORD)
        if _operation_enabled(status_word):
            self.last_error = None
            self.drive_enabled = True
            return True

        if _quick_stop_active(status_word):
            for _attempt in range(ENDSTOP_RECOVERY_ATTEMPTS):
                self._recover_from_endstop()
                status_word = self._read(OD_STATUS_WORD)
                if not _quick_stop_active(status_word):
                    break

        if not _operation_enabled(status_word):
            if not self.enable_drive():
                return False
            status_word = self._read(OD_STATUS_WORD)

        if not _operation_enabled(status_word):
            self.last_error = "drive did not reach Operation enabled"
            self.drive_enabled = False
            return False

        # A losing retry attempt above may have left a transient SDO error
        # (e.g. the expected-and-retried 3701h rejection) in last_error even
        # though we ultimately got here; don't leave that stale message
        # displayed once we're actually back in Operation enabled.
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
        self._apply_motion_profile(p["jog_accel"], p["jog_jerk"])
        if not self.set_target_velocity(direction * p["jog_speed"]):
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
    POST /api/<name>/jog_stop
    POST /api/<name>/stop
    POST /api/<name>/enable
    POST /api/<name>/pid         -> {action: "start"|"stop"}
    POST /api/<name>/lift        -> {direction: "up"|"down"|"stop"}  (lift only)
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
                "params": PARAM_SPECS,
                "readout": [
                    {"key": k, "label": lbl, "fmt": fmt}
                    for (k, _i, _s, _b, _sg, lbl, fmt) in READOUT_SPECS
                ],
                "controllers": [
                    {"name": name, "suffix": ctrl.serial_suffix, "role": ctrl.role}
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
    run_server(manager, args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
