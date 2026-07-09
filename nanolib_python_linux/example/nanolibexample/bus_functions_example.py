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
# @file   bus_functions_example.py
#
# @brief  Definition of bus hardware specific functions
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

from menu_utils import *

def scan_bus_hardware(ctx: 'Context'):
    """
    Retrieve list of available bus hardware and store to ctx.openableBusHardwareIds.

    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False
    result: Nanolib.ResultBusHwIds = ctx.nanolib_accessor.listAvailableBusHardware()

    if result.hasError():
        handle_error_message(ctx, "Error during bus scan: ", result.getError())
        return

    ctx.scanned_bus_hardware_ids = result.getResult()

    if not ctx.scanned_bus_hardware_ids:
        handle_error_message(ctx, "No bus hardware found. Please check your cabling, driver and/or devices.")
        return

    ctx.openable_bus_hardware_ids = Menu.get_openable_bus_hw_ids(ctx)


def open_bus_hardware(ctx: 'Context'):
    """
    Open the selected bus hardware (ctx.selectedOption).

    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False

    if not ctx.openable_bus_hardware_ids:
        handle_error_message(ctx, "No bus hardware available. Please do a scan first.")
        return

    index = ctx.selected_option
    bus_hw_id: Nanolib.BusHardwareId = ctx.openable_bus_hardware_ids[index - 1]

    for open_bus_hw_id in ctx.open_bus_hardware_ids:
        if open_bus_hw_id.equals(bus_hw_id):
            handle_error_message(ctx, f"Bus hardware {bus_hw_id.getName()} already open.")
            return

    bus_hw_options = create_bus_hardware_options(bus_hw_id)
    result_void: Nanolib.ResultVoid = ctx.nanolib_accessor.openBusHardwareWithProtocol(bus_hw_id, bus_hw_options)

    if result_void.hasError():
        handle_error_message(ctx, "Error during openBusHardware: ", result_void.getError())
        return

    ctx.open_bus_hardware_ids.append(bus_hw_id)
    ctx.openable_bus_hardware_ids = Menu.get_openable_bus_hw_ids(ctx)


def close_bus_hardware(ctx: 'Context'):
    """
    Close the selected bus hardware (ctx.selectedOption).

    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False
    index = ctx.selected_option

    if not ctx.open_bus_hardware_ids:
        handle_error_message(ctx, "No open bus hardware found.")
        return

    close_bus_hardware_id: Nanolib.BusHardwareId = ctx.open_bus_hardware_ids[index - 1]

    # Remove connected device handles
    new_connected_device_handles: list[Nanolib.DeviceHandle] = []
    for e in ctx.connected_device_handles:
        device_id_result: Nanolib.ResultDeviceId = ctx.nanolib_accessor.getDeviceId(e)
        device_id: Nanolib.DeviceId = device_id_result.getResult()
        bus_hardware_id = device_id.getBusHardwareId()
        if not close_bus_hardware_id.equals(bus_hardware_id):
            new_connected_device_handles.append(e)
    ctx.connected_device_handles = new_connected_device_handles
    
    # Clear active device if necessary
    if ctx.active_device is not None:
        device_id_result = ctx.nanolib_accessor.getDeviceId(ctx.active_device)
        device_id: Nanolib.DeviceId = device_id_result.getResult()
        bus_hardware_id: Nanolib.BusHardwareId = device_id.getBusHardwareId()
        if bus_hardware_id.equals(close_all_bus_hardware):
            ctx.active_device = None

    # Remove matching device IDs from connectable and scanned device IDs
    ctx.connectable_device_ids = [
        e for e in ctx.connectable_device_ids
        if not close_bus_hardware_id.equals(e.getBusHardwareId())
    ]

    ctx.scanned_device_ids = [
        e for e in ctx.scanned_device_ids
        if not close_bus_hardware_id.equals(e.getBusHardwareId())
    ]

    result_void: Nanolib.ResultVoid = ctx.nanolib_accessor.closeBusHardware(close_bus_hardware_id)

    if result_void.hasError():
        handle_error_message(ctx, "Error during closeBusHardware: ", result_void.getError())
        return

    ctx.open_bus_hardware_ids.remove(close_bus_hardware_id)

    if not ctx.open_bus_hardware_ids:
        ctx.scanned_device_ids.clear()
        ctx.active_device = None

    ctx.openable_bus_hardware_ids = Menu.get_openable_bus_hw_ids(ctx)


def close_all_bus_hardware(ctx: 'Context'):
    """
    Close all open bus hardware.

    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False
    error_messages = []

    if not ctx.open_bus_hardware_ids:
        handle_error_message(ctx, "No open bus hardware found.")
        return

    for open_bus_hardware_id in ctx.open_bus_hardware_ids:

        result_void: Nanolib.ResultVoid = ctx.nanolib_accessor.closeBusHardware(open_bus_hardware_id)

        if result_void.hasError():
            error_messages.append(f"Error during closeBusHardware: {result_void.getError()}")

    ctx.error_text = "\n".join(error_messages)
    ctx.open_bus_hardware_ids.clear()
    ctx.scanned_device_ids.clear()
    ctx.connected_device_handles.clear()
    ctx.connectable_device_ids.clear()
    ctx.openable_bus_hardware_ids = Menu.get_openable_bus_hw_ids(ctx)
    ctx.active_device = None