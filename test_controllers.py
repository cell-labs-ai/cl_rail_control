#!/usr/bin/env python3
"""
Simple connectivity test for the Nanotec motor controllers over Modbus TCP (WiFi).

What it does:
  1. Lists the available bus hardware and picks the Modbus TCP bus(es).
  2. Opens each bus and scans it to DISCOVER the controllers (no IPs needed).
  3. Connects to each discovered device.
  4. Reads and prints some basic info + live data for testing.
  5. Disconnects and closes the bus cleanly.

Notes:
  - The bundled nanolib package is built for aarch64 (arm64), so this must run on
    the target device (e.g. the Raspberry Pi on the rail), not on an x86_64 PC.
  - Run inside the project virtualenv:
        source .venv/bin/activate
        python test_controllers.py
  - IMPORTANT: make sure no other tool/app is talking to the controllers while this runs.

If auto-discovery finds no Modbus TCP bus, the script falls back to the fixed
IP addresses in FALLBACK_CONTROLLER_IPS below.
"""

import os
import sys

# The nanolib package lives under nanolib_python_linux; make it importable
# regardless of the current working directory.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "nanolib_python_linux"))

from nanotec_nanolib import Nanolib


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Only used if auto-discovery finds no Modbus TCP bus hardware.
FALLBACK_CONTROLLER_IPS = [
    "192.168.0.164",
    "192.168.0.168",
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


def make_modbus_tcp_bus_id(ip_address):
    """Build a Modbus TCP bus hardware id for a controller at the given IP (fallback path)."""
    return Nanolib.BusHardwareId(
        Nanolib.BUS_HARDWARE_ID_NETWORK,              # bus hardware
        Nanolib.BUS_HARDWARE_ID_PROTOCOL_MODBUS_TCP,  # protocol
        ip_address,                                   # hardware specifier (the IP)
        f"Modbus TCP {ip_address}",                   # friendly name
    )


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


def test_bus(accessor, bus_id, scan_callback):
    """Open one bus, discover, connect, read from every device, and clean up."""
    print(f"\n=== Bus: {bus_id.getName()} "
          f"(specifier: {bus_id.getHardwareSpecifier()}) ===")

    print("  Opening bus ...")
    open_result = accessor.openBusHardwareWithProtocol(bus_id, bus_options_for(bus_id))
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
            description = (device_id.getDescription()
                           or f"id {device_id.getDeviceId()}")

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

    print("Nanotec Modbus TCP controller test\n")

    # Preferred path: discover the Modbus TCP bus hardware and scan it, so the
    # controllers are found without knowing their IP addresses in advance.
    tcp_buses = discover_modbus_tcp_buses(accessor)

    if tcp_buses:
        for bus_id in tcp_buses:
            try:
                test_bus(accessor, bus_id, scan_callback)
            except Exception as exc:
                print(f"  UNEXPECTED ERROR: {exc}")
    else:
        # Fallback: no Modbus TCP bus auto-detected, use fixed IPs instead.
        print("\nNo Modbus TCP bus auto-detected. "
              f"Falling back to fixed IPs: {', '.join(FALLBACK_CONTROLLER_IPS)}")
        for ip in FALLBACK_CONTROLLER_IPS:
            try:
                test_bus(accessor, make_modbus_tcp_bus_id(ip), scan_callback)
            except Exception as exc:
                print(f"  UNEXPECTED ERROR for {ip}: {exc}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
