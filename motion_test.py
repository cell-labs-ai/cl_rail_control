#!/usr/bin/env python3
"""
Connect automatically to the motor controller whose serial number ends in
TARGET_SERIAL_SUFFIX (default: "0168"), then run a PID feedback loop that
drives the motor velocity to hold the pendulum angle (read from the analog
input) at POSITION_SETPOINT.

Based on test_controllers.py: discovers the Modbus TCP bus(es), scans for
devices, adds+connects each one just long enough to read its serial number,
keeps the matching device connected and disconnects/removes the rest.

Note: connecting directly by IP (constructing a BusHardwareId with an IP as
the network specifier) is not supported by this Nanolib version/binding --
BUS_HARDWARE_ID_NETWORK only accepts interface names (e.g. "eth0", "wlan0")
as returned by listAvailableBusHardware(). Devices must be discovered via
scanDevices() on that interface; there is no way to target a single IP
directly or to filter the scan itself.

Usage (inside the project virtualenv, from the repo root):
    source .venv/bin/activate
    python motion_test.py
    python motion_test.py --monitor   # only print Controlword/Statusword/
                                       # Analog Input 1, no motor motion
"""

import argparse
import os
import sys
import threading
import time

# The nanolib package lives under nanolib_python_linux; make it importable
# regardless of the current working directory.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "nanolib_python_linux"))

from nanotec_nanolib import Nanolib


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_SERIAL_SUFFIX = "0168"

# Jerk-limited ramp (see C5-E manual, "Motion Profile Type" 6086h and
# "Profile Jerk" 60A4h). 6083h (Profile Acceleration) and 6084h (Profile
# Deceleration) are both set to PROFILE_ACCELERATION; all four 60A4h
# subindices (begin/end acceleration/deceleration jerk) are set to
# PROFILE_JERK.
PROFILE_ACCELERATION = 8000
PROFILE_JERK = 8000

# CiA 402 object dictionary entries used for the motion (see motor_functions_example.py)
OD_CONTROL_WORD = Nanolib.OdIndex(0x6040, 0x00)
OD_STATUS_WORD = Nanolib.OdIndex(0x6041, 0x00)
OD_NANOJ_CONTROL = Nanolib.OdIndex(0x2300, 0x00)
OD_MODE_OF_OPERATION = Nanolib.OdIndex(0x6060, 0x00)
OD_TARGET_VELOCITY = Nanolib.OdIndex(0x60FF, 0x00)

# Ramp / jerk-limitation object dictionary entries (C5-E manual, chapter 10).
OD_PROFILE_ACCELERATION = Nanolib.OdIndex(0x6083, 0x00)
OD_PROFILE_DECELERATION = Nanolib.OdIndex(0x6084, 0x00)
OD_MOTION_PROFILE_TYPE = Nanolib.OdIndex(0x6086, 0x00)
# 60A4h subindices: 01h Begin Acceleration Jerk, 02h Begin Deceleration Jerk,
# 03h End Acceleration Jerk, 04h End Deceleration Jerk.
OD_PROFILE_JERK = [Nanolib.OdIndex(0x60A4, sub) for sub in (0x01, 0x02, 0x03, 0x04)]

# Analog Input Digits, subindex 01h = Analog Input #1 (see C5-E manual, 3220h).
# It is a 10-bit ADC value (0-1023 digits, see manual chapter 7.2) that
# measures the PENDULUM ANGLE, not the cart's rail position -- there is no
# separate cart-position sensor on this rig. At the physical travel limits
# some installations show a wrap-around glitch where a single sample jumps
# straight from one rail to the other (e.g. 0 -> 1023) instead of
# saturating. StatePoller detects that (a sample-to-sample jump whose
# magnitude exceeds ANALOG_INPUT_JUMP_THRESHOLD) and clamps to the rail the
# reading was previously close to, instead of accepting the wrapped value.
OD_ANALOG_INPUT_1 = Nanolib.OdIndex(0x3220, 0x01)
ANALOG_INPUT_MIN = 0
ANALOG_INPUT_MAX = 1023
ANALOG_INPUT_JUMP_THRESHOLD = 512

# Poll interval for StatePoller (see below): 50 Hz.
STATE_POLL_INTERVAL_S = 0.002

# Direct PID position control (see run_position_control()):
#   velocity = clamp(Kp * error + Ki * integral(error) + Kd * filtered_d(angle)/dt,
#                     -max_speed, +max_speed)
# where error = POSITION_SETPOINT - angle. Ki/Kd are off by default. These
# need retuning from scratch if the swing is unstable -- this is a plain
# direct-velocity PID loop, not an acceleration-based controller.
# Kp/Ki/Kd all share the same "hardware-direction-inverted" sign convention
# (confirmed correct for Kp on the bench): the D term deliberately uses the
# raw angle rate (not the negated error rate) so it stays sign-consistent
# with Kp/Ki -- see run_position_control() docstring.
POSITION_SETPOINT = ANALOG_INPUT_MAX / 2
POSITION_DEADZONE = 10                        # digits; |error| within this band is treated as 0
                                              # for P/I (sensor jitter at rest shouldn't cause
                                              # constant small corrections/motor buzz). The D
                                              # term stays active inside the deadzone too -- see
                                              # run_position_control().
POSITION_CONTROL_KP = -3.0                   # rpm per digit of angle error
POSITION_CONTROL_KI = -0.0                  # rpm per (digit*s) of accumulated angle error
POSITION_CONTROL_KD = -0.0                  # rpm per (digit/s) of angle rate -- conservative
                                              # starting guess, not yet confirmed on the bench
POSITION_CONTROL_DERIVATIVE_TAU_S = 0.1      # low-pass filter time constant for the angle-rate
                                              # estimate (raw digit-to-digit rate is too noisy
                                              # to use directly at 50 Hz)
POSITION_CONTROL_INTEGRAL_LIMIT = 200        # rpm; anti-windup clamp on the I-term's *contribution*
                                              # to velocity (Ki * integral), not on the raw
                                              # accumulated integral -- bounding the raw value
                                              # instead would let the I-term's actual rpm output
                                              # balloon out of proportion once Ki is scaled up
POSITION_CONTROL_INTEGRAL_LEAK_RATE = 0.1    # 1/s; slow continuous decay pulling the integral
                                              # back towards 0 (~10s time constant) so stale
                                              # accumulation bleeds off smoothly, instead of
                                              # either being stuck forever or force-reset to 0
                                              # with a hard, potentially oscillation-inducing jump
POSITION_CONTROL_MAX_SPEED_RPM = 600         # velocity output clamp
POSITION_CONTROL_INTERVAL_S = STATE_POLL_INTERVAL_S  # match the poller's 50 Hz sample rate
POSITION_CONTROL_MAX_DT_S = 5 * POSITION_CONTROL_INTERVAL_S  # clamp dt so a stalled loop
                                                              # iteration can't spike the I/D terms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ScanBusCallback(Nanolib.NlcScanBusCallback):
    """Minimal scan-progress callback (scanDevices requires one)."""

    def callback(self, info, devices_found, data):
        if info == Nanolib.BusScanInfo_Start:
            print("    scanning ", end="", flush=True)
        elif info == Nanolib.BusScanInfo_Progress:
            print(".", end="", flush=True)
        elif info == Nanolib.BusScanInfo_Finished:
            print(" done")
        return Nanolib.ResultVoid()


CONNECTION_STATES = {
    Nanolib.DeviceConnectionStateInfo_Connected: "Connected",
    Nanolib.DeviceConnectionStateInfo_Disconnected: "Disconnected",
    Nanolib.DeviceConnectionStateInfo_ConnectedBootloader: "Connected (bootloader)",
}


def bus_options_for(bus_id):
    """Return the BusHardwareOptions needed to open the given bus hardware."""
    # Modbus TCP needs no extra options; return an empty option set.
    return Nanolib.BusHardwareOptions()


def discover_modbus_tcp_buses(accessor):
    """List available bus hardware and return the Modbus TCP entries."""
    result = accessor.listAvailableBusHardware()
    if result.hasError():
        print(f"ERROR listing bus hardware: {result.getError()}")
        return []

    all_buses = result.getResult()
    print(f"Available bus hardware ({len(all_buses)}):")
    tcp_buses = []
    for bus_id in all_buses:
        protocol = bus_id.getProtocol()
        print(f"  - {bus_id.getName()} "
              f"[protocol: {protocol}, specifier: {bus_id.getHardwareSpecifier()}]")
        if protocol == Nanolib.BUS_HARDWARE_ID_PROTOCOL_MODBUS_TCP:
            tcp_buses.append(bus_id)

    return tcp_buses


def find_target_on_bus(accessor, bus_id, scan_callback):
    """Open one bus, scan it, and connect to the device whose serial number
    ends with TARGET_SERIAL_SUFFIX. Any other discovered device is
    disconnected/removed again and the bus is closed on failure.

    Returns (device_handle, bus_id) on success, or None if not found
    (in which case the bus has already been closed).
    """
    print(f"\n=== Bus: {bus_id.getName()} "
          f"(specifier: {bus_id.getHardwareSpecifier()}) ===")

    print("  Opening bus ...")
    open_result = accessor.openBusHardwareWithProtocol(bus_id, bus_options_for(bus_id))
    if open_result.hasError():
        print(f"  ERROR opening bus: {open_result.getError()}")
        return None

    print("  Scanning for devices ...")
    scan_result = accessor.scanDevices(bus_id, scan_callback)
    if scan_result.hasError():
        print(f"  ERROR scanning devices: {scan_result.getError()}")
        accessor.closeBusHardware(bus_id)
        return None

    device_ids = scan_result.getResult()
    if not device_ids:
        print("  No devices found on this bus.")
        accessor.closeBusHardware(bus_id)
        return None

    print(f"  Found {len(device_ids)} device(s).")

    for device_id in device_ids:
        description = device_id.getDescription() or f"id {device_id.getDeviceId()}"

        add_result = accessor.addDevice(device_id)
        if add_result.hasError():
            print(f"  ERROR adding device {description}: {add_result.getError()}")
            continue
        handle = add_result.getResult()

        connect_result = accessor.connectDevice(handle)
        if connect_result.hasError():
            print(f"  ERROR connecting device {description}: {connect_result.getError()}")
            accessor.removeDevice(handle)
            continue

        serial_result = accessor.getDeviceSerialNumber(handle)
        serial = serial_result.getResult() if not serial_result.hasError() else ""
        print(f"  Device: {description}  serial='{serial}'")

        if str(serial).endswith(TARGET_SERIAL_SUFFIX):
            print(f"  --> Match: serial ends with '{TARGET_SERIAL_SUFFIX}'. Keeping connection open.")
            return handle, bus_id

        # Not our target: disconnect and free it again.
        accessor.disconnectDevice(handle)
        accessor.removeDevice(handle)

    print(f"  No device with serial ending in '{TARGET_SERIAL_SUFFIX}' found on this bus.")
    accessor.closeBusHardware(bus_id)
    return None


class StatePoller:
    """Continuously reads controlword (6040h), statusword (6041h) and analog
    input 1 (3220h:01h) in a background thread and makes the latest values
    available to other functions via get_state().

    Note: FC 101 (65h) "Read complete object dictionary" (C5-E manual,
    8.4.6) streams out the *entire* object dictionary and is not exposed by
    the Nanolib Python binding -- accessor.readNumber() per single OD index
    is the only read path available, so that is what this polls with.
    """

    def __init__(self, accessor, device_handle, interval_s=STATE_POLL_INTERVAL_S):
        self._accessor = accessor
        self._device_handle = device_handle
        self._interval_s = interval_s
        self._lock = threading.Lock()
        self._state: dict = {"control_word": None, "status_word": None, "analog_input_1": None}
        self._stop_event = threading.Event()
        self._thread = None
        self._last_analog_input_1 = None  # last accepted (post-clamp) value; owned by _run()

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def get_state(self):
        """Return a snapshot dict with keys 'control_word', 'status_word',
        'analog_input_1'. Values are None until the first successful read."""
        with self._lock:
            return dict(self._state)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def _run(self):
        while not self._stop_event.is_set():
            control_word = self._read(OD_CONTROL_WORD)
            status_word = self._read(OD_STATUS_WORD)
            analog_input_1 = self._clamp_analog_jump(self._read(OD_ANALOG_INPUT_1))

            with self._lock:
                self._state["control_word"] = control_word
                self._state["status_word"] = status_word
                self._state["analog_input_1"] = analog_input_1

            self._stop_event.wait(self._interval_s)

    def _read(self, od_index):
        result = self._accessor.readNumber(self._device_handle, od_index)
        return None if result.hasError() else result.getResult()

    def _clamp_analog_jump(self, raw):
        """Guard against the analog-input wrap-around glitch at the sensor's
        travel limits (raw jumps straight from one rail to the other, e.g.
        0 -> 1023, instead of saturating). If consecutive samples differ by
        more than ANALOG_INPUT_JUMP_THRESHOLD, the new sample is discarded
        and the value is clamped to the rail it was previously close to --
        a real drive can't cross most of the sensor's range within one
        50 Hz poll interval, so a jump that large can only be the glitch.
        """
        if raw is None:
            return self._last_analog_input_1

        if self._last_analog_input_1 is not None:
            delta = raw - self._last_analog_input_1
            if abs(delta) > ANALOG_INPUT_JUMP_THRESHOLD:
                raw = ANALOG_INPUT_MAX if delta < 0 else ANALOG_INPUT_MIN

        self._last_analog_input_1 = raw
        return raw


def format_state_line(state, elapsed_s):
    cw = state["control_word"]
    sw = state["status_word"]
    ai = state["analog_input_1"]
    cw_str = f"0x{cw:04X}" if cw is not None else "?"
    sw_str = f"0x{sw:04X}" if sw is not None else "?"
    return f"    [{elapsed_s:5.1f}s] Controlword={cw_str} Statusword={sw_str} AnalogInput1={ai}"


def run_state_monitor(poller, log_interval_s=0.5):
    """Continuously print poller.get_state() (Controlword/Statusword/Analog
    Input 1) without moving the motor, until interrupted with Ctrl+C.
    """
    print("  Monitoring Controlword/Statusword/Analog Input 1 (Ctrl+C to stop) ...")
    start = time.monotonic()
    try:
        while True:
            elapsed = time.monotonic() - start
            print(format_state_line(poller.get_state(), elapsed))
            time.sleep(log_interval_s)
    except KeyboardInterrupt:
        print("\n  Monitoring stopped (Ctrl+C).")


def set_profile_jerk(accessor, device_handle, jerk):
    """Write all four 60A4h (Profile Jerk) subindices to `jerk`."""
    for jerk_index in OD_PROFILE_JERK:
        result = accessor.writeNumber(device_handle, jerk, jerk_index, 32)
        if result.hasError():
            print(f"  ERROR setting profile jerk (subindex {jerk_index.getSubIndex():02X}h): "
                  f"{result.getError()}")
            return False
    return True


def set_profile_acceleration(accessor, device_handle, acceleration):
    """Write 6083h (Profile Acceleration) and 6084h (Profile Deceleration)
    to the same `acceleration` value."""
    result = accessor.writeNumber(device_handle, acceleration, OD_PROFILE_ACCELERATION, 32)
    if result.hasError():
        print(f"  ERROR setting profile acceleration: {result.getError()}")
        return False

    result = accessor.writeNumber(device_handle, acceleration, OD_PROFILE_DECELERATION, 32)
    if result.hasError():
        print(f"  ERROR setting profile deceleration: {result.getError()}")
        return False

    return True


def start_profile_velocity_mode(accessor, device_handle, speed_rpm=0,
                                 acceleration=PROFILE_ACCELERATION, jerk=PROFILE_JERK):
    """Configure and start CiA 402 Profile Velocity mode at speed_rpm, then
    return -- the caller decides how long to let it run and calls
    stop_motor() when done.

    Uses a jerk-limited ramp (6086h = 3) with 6083h/6084h (Profile
    Acceleration/Deceleration) both set to `acceleration` and all four
    60A4h subindices set to `jerk`.
    """
    print(f"\nStarting Profile Velocity mode: {speed_rpm} rpm ...")

    # Stop a possibly running NanoJ program
    result = accessor.writeNumber(device_handle, 0x00, OD_NANOJ_CONTROL, 32)
    if result.hasError():
        print(f"  ERROR stopping NanoJ program: {result.getError()}")
        return False

    # Choose Profile Velocity mode
    result = accessor.writeNumber(device_handle, 0x03, OD_MODE_OF_OPERATION, 8)
    if result.hasError():
        print(f"  ERROR setting mode of operation: {result.getError()}")
        return False

    # Jerk-limited ramp (0 = trapezoidal, 3 = jerk limited)
    result = accessor.writeNumber(device_handle, 3, OD_MOTION_PROFILE_TYPE, 16)
    if result.hasError():
        print(f"  ERROR setting motion profile type: {result.getError()}")
        return False

    if not set_profile_acceleration(accessor, device_handle, acceleration):
        return False

    if not set_profile_jerk(accessor, device_handle, jerk):
        return False

    if not set_target_velocity(accessor, device_handle, speed_rpm):
        return False

    # Switch the state machine to "operation enabled"
    for command in [0x06, 0x07, 0x0F]:
        result = accessor.writeNumber(device_handle, command, OD_CONTROL_WORD, 16)
        if result.hasError():
            print(f"  ERROR writing control word 0x{command:02X}: {result.getError()}")
            return False

    print(f"  Motor running at {speed_rpm} rpm ...")
    return True


def set_target_velocity(accessor, device_handle, speed_rpm, quiet=False):
    """Change the target velocity (60FFh) on the fly.

    Valid while the drive is already in Profile Velocity mode and operation
    enabled: no mode-of-operation/ramp reconfiguration or state-machine
    transition is needed, the drive just ramps to the new speed_rpm using
    its current 6083h/6084h/60A4h (acceleration/deceleration/jerk) settings.

    quiet=True suppresses the per-call log line (for use in fast control
    loops such as run_position_control(), which log the state themselves).
    """
    result = accessor.writeNumber(device_handle, speed_rpm, OD_TARGET_VELOCITY, 32)
    if result.hasError():
        print(f"  ERROR setting target velocity: {result.getError()}")
        return False

    if not quiet:
        print(f"  Target velocity: {speed_rpm} rpm")
    return True


def stop_motor(accessor, device_handle):
    """Stop the motor (controlword 'shutdown', 0x06 -> back to 'switched on')."""
    result = accessor.writeNumber(device_handle, 0x06, OD_CONTROL_WORD, 16)
    if result.hasError():
        print(f"  ERROR stopping motor: {result.getError()}")
        return False

    print("  Motor stopped.")
    return True


def run_position_control(accessor, device_handle, poller):
    """Direct PID position control: drives the motor velocity so the analog
    input (pendulum angle, from `poller` -- already clamped against the
    sensor's wrap-around glitch) settles at POSITION_SETPOINT.

        velocity = clamp(Kp * error + Ki * integral(error) + Kd * filtered_d(angle)/dt,
                          -max_speed, +max_speed)

    The D term is computed on the raw angle measurement, not on `error` --
    error gets zeroed by POSITION_DEADZONE below, and differentiating that
    would inject a spurious kick every time the deadzone boundary is
    crossed. For the same reason the D term stays active *inside* the
    deadzone too (P and I don't): it's what damps any residual motion
    there, whereas zeroing it would let momentum coast unopposed. Its sign
    is deliberately not negated (d(angle)/dt, not d(error)/dt = -d(angle)/dt)
    so Kd stays sign-consistent with Kp/Ki -- see the config comment.

    The integral has two safeguards: anti-windup (the accumulator only
    grows if doing so wouldn't push its rpm contribution past
    POSITION_CONTROL_INTEGRAL_LIMIT) and a slow continuous leak back
    towards 0, so a stale accumulation bleeds off gradually instead of
    being stuck forever or needing a hard, discontinuous reset.

    Runs until interrupted with Ctrl+C (which also commands zero velocity
    before returning). The caller is responsible for starting Profile
    Velocity mode beforehand (start_profile_velocity_mode()) and stopping
    the motor afterwards (stop_motor()).
    """
    print(f"\nPID position control: setpoint={POSITION_SETPOINT:.0f}, "
          f"Kp={POSITION_CONTROL_KP}, Ki={POSITION_CONTROL_KI}, Kd={POSITION_CONTROL_KD}, "
          f"max. speed={POSITION_CONTROL_MAX_SPEED_RPM} rpm (Ctrl+C to stop) ...")

    integral = 0.0
    filtered_rate = 0.0
    last_angle = None
    last_time = None

    try:
        while True:
            angle = poller.get_state()["analog_input_1"]
            now = time.monotonic()

            if angle is not None:
                error = POSITION_SETPOINT - angle
                if abs(error) <= POSITION_DEADZONE:
                    error = 0

                if last_angle is not None and last_time is not None:
                    dt = min(now - last_time, POSITION_CONTROL_MAX_DT_S)
                    if dt > 0:
                        raw_rate = (angle - last_angle) / dt
                        alpha = dt / (POSITION_CONTROL_DERIVATIVE_TAU_S + dt)
                        filtered_rate += alpha * (raw_rate - filtered_rate)

                        if POSITION_CONTROL_KI != 0:
                            candidate_integral = integral + error * dt
                            # Anti-windup: only accept the new integral if it
                            # wouldn't push the I-term's rpm contribution past
                            # its clamp -- freezing here (rather than clamping
                            # the raw integral afterwards) stops it from
                            # uselessly overshooting the limit while the error
                            # stays the same sign, which would otherwise make
                            # it slow to unwind once error reverses.
                            if abs(POSITION_CONTROL_KI * candidate_integral) <= POSITION_CONTROL_INTEGRAL_LIMIT:
                                integral = candidate_integral
                            integral -= integral * min(1.0, POSITION_CONTROL_INTEGRAL_LEAK_RATE * dt)

                last_angle = angle
                last_time = now

                i_term = POSITION_CONTROL_KI * integral
                d_term = POSITION_CONTROL_KD * filtered_rate
                velocity = POSITION_CONTROL_KP * error + i_term + d_term
                velocity = max(-POSITION_CONTROL_MAX_SPEED_RPM,
                                min(POSITION_CONTROL_MAX_SPEED_RPM, velocity))

                set_target_velocity(accessor, device_handle, round(velocity), quiet=True)
                print(f"    Angle={angle} Error={error:+.0f} Integral={integral:+.1f} "
                      f"I-term={i_term:+.1f} Rate={filtered_rate:+.0f}/s D-term={d_term:+.1f} "
                      f"Velocity={velocity:+.0f} rpm")

            time.sleep(POSITION_CONTROL_INTERVAL_S)
    except KeyboardInterrupt:
        set_target_velocity(accessor, device_handle, 0, quiet=True)
        print("\n  PID control stopped (Ctrl+C).")


def print_device_info(accessor, device_handle):
    name = accessor.getDeviceName(device_handle)
    if not name.hasError():
        print(f"    {'Name':<28}: {name.getResult()}")

    product = accessor.getDeviceProductCode(device_handle)
    if not product.hasError():
        print(f"    {'Product code':<28}: {product.getResult()}")

    serial = accessor.getDeviceSerialNumber(device_handle)
    if not serial.hasError():
        print(f"    {'Serial number':<28}: {serial.getResult()}")

    state = accessor.getConnectionState(device_handle)
    if not state.hasError():
        print(f"    {'Connection state':<28}: {CONNECTION_STATES.get(state.getResult(), 'unknown')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monitor", action="store_true",
                         help="Only connect and continuously print Controlword/Statusword/"
                              "Analog Input 1 (50 Hz poll); does not move the motor. "
                              "Stop with Ctrl+C.")
    return parser.parse_args()


def main():
    args = parse_args()

    accessor = Nanolib.getNanoLibAccessor()
    accessor.setLoggingLevel(Nanolib.LogLevel_Off)

    scan_callback = ScanBusCallback()

    print(f"Searching for motor controller with serial number ending in '{TARGET_SERIAL_SUFFIX}' ...\n")

    tcp_buses = discover_modbus_tcp_buses(accessor)

    found = None
    for bus_id in tcp_buses:
        try:
            found = find_target_on_bus(accessor, bus_id, scan_callback)
        except Exception as exc:
            print(f"  UNEXPECTED ERROR: {exc}")
            found = None
        if found:
            break

    if not found:
        print(f"\nNo controller with serial number ending in '...{TARGET_SERIAL_SUFFIX}' found.")
        return 1

    device_handle, bus_id = found
    print(f"\nConnected to controller (serial number ends with '{TARGET_SERIAL_SUFFIX}'):")
    print_device_info(accessor, device_handle)

    try:
        with StatePoller(accessor, device_handle) as poller:
            if args.monitor:
                run_state_monitor(poller)
            else:
                start_profile_velocity_mode(accessor, device_handle)
                try:
                    run_position_control(accessor, device_handle, poller)
                finally:
                    stop_motor(accessor, device_handle)
    finally:
        print("\nDisconnecting and closing bus ...")
        accessor.disconnectDevice(device_handle)
        accessor.removeDevice(device_handle)
        accessor.closeBusHardware(bus_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
