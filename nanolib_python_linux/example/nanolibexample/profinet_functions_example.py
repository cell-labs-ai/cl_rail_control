##
# Nanotec Nanolib example
# Copyright (C) Nanotec GmbH & Co. KG - All Rights Reserved
#
# This product includes software developed by the
# Nanotec GmbH & Co. KG (http://www.nanotec.com/).
#
# The Nanolib interface headers and the examples source code provided are 
# licensed under the Creative Commons Attribution 4.0 Internaltional License. 
# To view a copy of this license, 
# visit https://creativecommons.org/licenses/by/4.0/ or send a letter to 
# Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
# The parts of the library provided in binary format are licensed under 
# the Creative Commons Attribution-NoDerivatives 4.0 International License. 
# To view a copy of this license, 
# visit http://creativecommons.org/licenses/by-nd/4.0/ or send a letter to 
# Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
#
# @file   profinet_functions_example.py
#
# @brief  Definition of Profinet specific functions
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

from nanotec_nanolib import *
from menu_utils import *

def profinet_dcp_example(ctx: 'Context'):
    """
    Function to demonstrate how to connect and blink Profinet device(s).

    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if not ctx.open_bus_hardware_ids:
        handle_error_message(ctx, "No hardware bus available. Open a proper hardware bus first.")
        return

    found_profinet_device = False

    # Check service availability - Npcap/WinPcap driver required
    profinet_dcp: Nanolib.ProfinetDCP = ctx.nanolib_accessor.getProfinetDCP()

    # Search for Profinet on every open bus hardware
    for open_bus_hw_id in ctx.open_bus_hardware_ids:
        service_result: Nanolib.ResultVoid = profinet_dcp.isServiceAvailable(open_bus_hw_id)
        if service_result.hasError():
            # Ignore
            continue

        # Service available - scan for Profinet devices
        print(f"Scanning {open_bus_hw_id.getName()} for Profinet devices...")
        result_profinet_devices: Nanolib.ResultProfinetDevices = profinet_dcp.scanProfinetDevices(open_bus_hw_id)

        if result_profinet_devices.hasError() and result_profinet_devices.getErrorCode() != Nanolib.NlcErrorCode_TimeoutError:
            print(f"Error during profinetDCPExample: {result_profinet_devices.getError()}")
            continue

        profinet_devices: list[Nanolib.ProfinetDevice] = result_profinet_devices.getResult()
        number_of_profinet_devices = len(profinet_devices)

        if number_of_profinet_devices < 1:
            continue

        found_profinet_device = True
        print(f"{number_of_profinet_devices} Profinet device(s) found: ")
        for profinet_device in profinet_devices:
            ip_address = profinet_device.ipAddress
            print(f"IP: {((ip_address >> 24) & 0x000000FF)}."
                  f"{((ip_address >> 16) & 0x000000FF)}."
                  f"{((ip_address >> 8) & 0x000000FF)}."
                  f"{(ip_address & 0x000000FF)}\tName: {profinet_device.deviceName}")

            # Checking the IP address against the context of the current network configuration
            result_valid: Nanolib.ResultVoid = profinet_dcp.validateProfinetDeviceIp(open_bus_hw_id, profinet_device)
            print(f"\tDevice IP is {'not ' if result_valid.hasError() else ''}valid in the current network.")

            # Trying to blink the device
            result_blink: Nanolib.ResultVoid = profinet_dcp.blinkProfinetDevice(open_bus_hw_id, profinet_device)
            print("\tBlink the device ", end="")
            if result_blink.has_error():
                print(f"failed with error: {result_blink.getError()}")
            else:
                print("succeeded.")
            print()

    if not found_profinet_device:
        handle_error_message(ctx, "No Profinet devices found.")