#!/usr/bin/env python3
"""
Simple connectivity test for the two Nanotec motor controllers over Modbus TCP (WiFi).

What it does:
  1. Opens a Modbus TCP bus for each configured controller IP.
  2. Scans / discovers the device(s) on that bus.
  3. Connects to each discovered device.
  4. Reads and prints some basic info + live data for testing.
  5. Disconnects and closes the bus cleanly.

Notes:
  - The bundled nanolib package is built for aarch64 (arm64), so this must run on
    the target device (e.g. the arm64 SBC on the rail), not on an x86_64 PC.
  - Run inside the project virtualenv:
        source .venv/bin/activate
        python test_controllers.py
  - IMPORTANT: make sure no other tool/app is talking to the controllers while this runs.

Edit CONTROLLER_IPS below to match your two controllers.
"""

import sys

# The nanolib package lives under nanolib_python_linux; make it importable
# regardless of the current working directory.
import os
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "nanolib_python_linux"))

from nanotec_nanolib import Nanolib


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# IP addresses of the two motor controllers on the WiFi network.
# Adjust to match your setup.
CONTROLLER_IPS = [
    "192.168.0.2",
    "192.168.0.3",
]

# CiA 402 object dictionary entries to read for a quick health check.
# (index, subindex, human-readable name)
READ_OBJECTS = [
    (0x6041, 0x00, "Statusword"),
    (0x6061, 0x00, "Mode of operation (display)"),
    (0x6064, 0x00, "Position actual value"),
    (0x606C, 0x00, "Velocity actual value"),
    (0x6077, 0x00, "Torque actual value"),
    (0x1003, 0x00, "Error count"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ScanBusCallback(Nanolib.NlcScanBusCallback):
    """Minimal scan-progress callback (scanDevices requires one)."""

    def callback(self, info, devices_found, data):
        if info == Nanolib.BusScanInfo_Start:
            print("    scan started ", end="", flush=True)
        elif info == Nanolib.BusScanInfo_Progress:
            print(".", end="", flush=True)
        elif info == Nanolib.BusScanInfo_Finished:
            print(" finished")
        return Nanolib.ResultVoid()


CONNECTION_STATES = {
    Nanolib.DeviceConnectionStateInfo_Connected: "Connected",
    Nanolib.DeviceConnectionStateInfo_Disconnected: "Disconnected",
    Nanolib.DeviceConnectionStateInfo_ConnectedBootloader: "Connected (bootloader)",
}


def make_modbus_tcp_bus_id(ip_address):
    """Build a Modbus TCP bus hardware id for a controller at the given IP."""
    return Nanolib.BusHardwareId(
        Nanolib.BUS_HARDWARE_ID_NETWORK,             # bus hardware
        Nanolib.BUS_HARDWARE_ID_PROTOCOL_MODBUS_TCP,  # protocol
        ip_address,                                   # hardware specifier (the IP)
        f"Modbus TCP {ip_address}",                   # friendly name
    )


def read_and_print_device_data(accessor, device_handle, description):
    """Read a handful of values from a connected device and print them."""
    print(f"  Device: {description}")

    # --- Static device info (via dedicated accessor calls) ---
    name = accessor.getDeviceName(device_handle)
    if not name.hasError():
        print(f"    Name              : {name.getResult()}")

    product = accessor.getDeviceProductCode(device_handle)
    if not product.hasError():
        print(f"    Product code      : {product.getResult()}")

    serial = accessor.getDeviceSerialNumber(device_handle)
    if not serial.hasError():
        print(f"    Serial number     : {serial.getResult()}")

    state = accessor.getConnectionState(device_handle)
    if not state.hasError():
        print(f"    Connection state  : {CONNECTION_STATES.get(state.getResult(), 'unknown')}")

    # --- Live object dictionary values ---
    for index, subindex, label in READ_OBJECTS:
        result = accessor.readNumber(device_handle, Nanolib.OdIndex(index, subindex))
        if result.hasError():
            print(f"    {label:<18}: <read error: {result.getError()}>")
        else:
            value = result.getResult()
            print(f"    {label:<18}: {value} (0x{value & 0xFFFFFFFF:X})")


def test_controller(accessor, ip_address, scan_callback):
    """Open the bus for one controller IP, discover, connect, read, and clean up."""
    print(f"\n=== Controller @ {ip_address} ===")

    bus_id = make_modbus_tcp_bus_id(ip_address)
    bus_options = Nanolib.BusHardwareOptions()  # Modbus TCP needs no extra options

    print("  Opening bus ...")
    open_result = accessor.openBusHardwareWithProtocol(bus_id, bus_options)
    if open_result.hasError():
        print(f"  ERROR opening bus: {open_result.getError()}")
        return

    connected_handles = []
    try:
        print("  Scanning for devices ...")
        scan_result = accessor.scanDevices(bus_id, scan_callback)
        if scan_result.hasError():
            print(f"  ERROR scanning devices: {scan_result.getError()}")
            return

        device_ids = scan_result.getResult()
        if not device_ids:
            print("  No devices found on this bus.")
            return

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

            connected_handles.append(handle)
            read_and_print_device_data(accessor, handle, description)

    finally:
        # Disconnect all devices we connected on this bus.
        for handle in connected_handles:
            accessor.disconnectDevice(handle)
            accessor.removeDevice(handle)

        print("  Closing bus ...")
        close_result = accessor.closeBusHardware(bus_id)
        if close_result.hasError():
            print(f"  ERROR closing bus: {close_result.getError()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    accessor = Nanolib.getNanoLibAccessor()
    accessor.setLoggingLevel(Nanolib.LogLevel_Off)

    scan_callback = ScanBusCallback()

    print("Nanotec Modbus TCP controller test")
    print(f"Controllers to test: {', '.join(CONTROLLER_IPS)}")

    for ip in CONTROLLER_IPS:
        try:
            test_controller(accessor, ip, scan_callback)
        except Exception as exc:  # keep going for the other controller
            print(f"  UNEXPECTED ERROR for {ip}: {exc}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
