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
# @file   device_functions_example.py
#
# @brief  Definition of device specific functions
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

import time
from menu_utils import *
from nanotec_nanolib import *

def scan_devices(ctx: Context):
    """Scans for valid devices on all opened bus hardware.

    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False
    found = False
    ctx.scanned_device_ids.clear()

    # no bus hardware
    if len(ctx.open_bus_hardware_ids) == 0:
        handle_error_message(ctx, "No bus hardware available. Please scan and select a bus hardware first.")
        return

    # scan for every opened bus hardware
    for open_bus_hardware_id in ctx.open_bus_hardware_ids:
        print(f"Scan devices for {open_bus_hardware_id.getProtocol()} ({open_bus_hardware_id.getName()})")
        result_device_ids: Nanolib.ResultDeviceIds = ctx.nanolib_accessor.scanDevices(open_bus_hardware_id, ctx.scan_bus_callback)
        
        if result_device_ids.hasError():
            handle_error_message(ctx, "Error during device scan: ", result_device_ids.getError())
            continue

        if result_device_ids.getResult():
            found = True
            ctx.scanned_device_ids.extend(result_device_ids.getResult())

    if not found:
        handle_error_message(ctx, "No devices found. Please check your cabling, driver(s) and/or device(s).")
        return

    # update ctx.connectableDeviceIds
    ctx.connectable_device_ids = Menu.get_connectable_device_ids(ctx)

def connect_device(ctx: Context):
    """Adds device and connects to the selected device (ctx.selectedOption) within Nanolib.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False

    if not ctx.connectable_device_ids:
        handle_error_message(ctx, "No device available. Please scan for devices first.")
        return

    # check if selected device is already connected
    index = ctx.selected_option
    selected_device_id = ctx.connectable_device_ids[index - 1]

    device_handle_result: Nanolib.ResultDeviceHandle = ctx.nanolib_accessor.addDevice(selected_device_id)
    if device_handle_result.hasError():
        handle_error_message(ctx, "Error during connectDevice (addDevice): ", device_handle_result.getError())
        return

    device_handle = device_handle_result.getResult()
    
    result_void: Nanolib.ResultVoid = ctx.nanolib_accessor.connectDevice(device_handle)
    if result_void.hasError():
        handle_error_message(ctx, "Error during connectDevice: ", result_void.getError())
        ctx.nanolib_accessor.removeDevice(device_handle)
        return

    # store handle
    ctx.connected_device_handles.append(device_handle)

    # update availableDeviceIds
    ctx.connectable_device_ids = Menu.get_connectable_device_ids(ctx)

    # update ctx.activeDevice to new connection
    ctx.active_device = device_handle

def disconnect_device(ctx: Context):
    """Disconnect device and removes to the selected device (ctx.selectedOption) within Nanolib.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False
    index = ctx.selected_option

    if not ctx.connected_device_handles:
        handle_error_message(ctx, "No device connected.")
        return

    # get selected device handle
    close_device_handle = ctx.connected_device_handles[index - 1]

    # disconnect device in nanolib
    result_void: Nanolib.ResultVoid = ctx.nanolib_accessor.disconnectDevice(close_device_handle)
    if result_void.hasError():
        handle_error_message(ctx, "Error during disconnectDevice: ", result_void.getError())
        return

    # remove device from nanolib
    result_void: Nanolib.ResultVoid = ctx.nanolib_accessor.removeDevice(close_device_handle)
    if result_void.hasError():
        handle_error_message(ctx, "Error during disconnectDevice (removeDevice): ", result_void.getError())
        return

    # update ctx.connectedDeviceHandles
    ctx.connected_device_handles.remove(close_device_handle)

    # update ctx.connectableDeviceIds
    ctx.connectable_device_ids = Menu.get_connectable_device_ids(ctx)

    # clear ctx.activeDevice
    ctx.active_device = None

def select_active_device(ctx: Context):
    """Select the device to use for all device-specific functions in Nanolib.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False

    index = ctx.selected_option

    if not ctx.connected_device_handles:
        handle_error_message(ctx, "No connected devices. Connect a device first.")
        return

    ctx.active_device = ctx.connected_device_handles[index - 1]

def reboot_device(ctx: Context):
    """Reboots the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    reboot_result: Nanolib.ResultVoid = ctx.nanolib_accessor.rebootDevice(ctx.active_device)
    if reboot_result.hasError():
        handle_error_message(ctx, "Error during rebootDevice: ", reboot_result.getError())

def update_firmware(ctx: Context):
    """Update the firmware of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    input_path = None
    device_name_result: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceName(ctx.active_device)
    device_name = device_name_result.getResult()
    firmware_build_id_result: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceFirmwareBuildId(ctx.active_device)
    firmware_build_id = firmware_build_id_result.getResult()

    prompt = []
    prompt.append(f"Current firmware Build Id: {firmware_build_id}\n")
    prompt.append("Please enter the full path to the firmware file (e.g. {}-FIR-vXXXX-BXXXXXXX.fw): ".format(device_name))
    
    while input_path is None:
        input_path = get_string_with_prompt(''.join(prompt))

    print("Do not interrupt the data connection or switch off the power until the update process has been finished!")
    upload_result: Nanolib.ResultVoid = ctx.nanolib_accessor.uploadFirmwareFromFile(ctx.active_device, input_path, ctx.data_transfer_callback)
    
    if upload_result.hasError():
        handle_error_message(ctx, "Error during updateFirmware: ", upload_result.getError())
        return

def update_bootloader(ctx: Context):
    """Update the bootloader of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    input_path = None
    # device_name_result: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceName(ctx.active_device)
    # device_name = device_name_result.getResult()
    bootloader_build_id_result: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceBootloaderBuildId(ctx.active_device)
    bootloader_build_id = bootloader_build_id_result.getResult()
    bootloader_version_result: Nanolib.ResultInt = ctx.nanolib_accessor.getDeviceBootloaderVersion(ctx.active_device)
    bootloader_version = str(bootloader_version_result.getResult() >> 16)

    prompt = []
    prompt.append(f"Current bootloader Build Id: {bootloader_build_id}\n")
    prompt.append(f"Bootloader version: {bootloader_version}\n")
    prompt.append("Please enter the full path to the bootloader file: ")

    while input_path is None:
        input_path = get_string_with_prompt(''.join(prompt))

    print("Do not interrupt the data connection or switch off the power until the update process has been finished!")
    upload_result: Nanolib.ResultVoid = ctx.nanolib_accessor.uploadBootloaderFromFile(ctx.active_device, input_path, ctx.data_transfer_callback)

    if upload_result.hasError():
        handle_error_message(ctx, "Error during updateBootloader: ", upload_result.getError())
        return

def upload_nanoj(ctx: Context):
    """Upload a compiled NanoJ binary to the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    input_path = None
    prompt = []
    prompt.append("Please enter the full path to the NanoJ file (e.g. vmmcode.usr): ")

    while input_path is None:
        input_path = get_string_with_prompt(''.join(prompt))

    print("Do not interrupt the data connection or switch off the power until the update process has been finished!")
    upload_result: Nanolib.ResultVoid = ctx.nanolib_accessor.uploadNanoJFromFile(ctx.active_device, input_path, ctx.data_transfer_callback)

    if upload_result.hasError():
        handle_error_message(ctx, "Error during uploadNanoJ: ", upload_result.getError())
        return

    print("Use runNanoJ menu option to re-start the uploaded NanoJ program.")

def run_nanoj(ctx: Context):
    """Executes the NanoJ program on the current active device if available.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    # check for errors
    error_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odNanoJError)
    if error_result.hasError():
        handle_error_message(ctx, "Error during runNanoJ: ", error_result.getError())
        return

    if error_result.getResult() != 0:
        handle_error_message(ctx, "Failed to start NanoJ program - NanoJ error code is set: ", str(error_result.getResult()))
        return

    # write start to NanoJ control object (0x2300)
    writeNumber_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x1, OdIndex.odNanoJControl, 32)
    if writeNumber_result.hasError():
        handle_error_message(ctx, "Error during runNanoJ: ", writeNumber_result.getError())
        return

    # start might take some time (up to 200ms)
    time.sleep(0.25)

    # check if running and no error
    error_result = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odNanoJError)
    if error_result.hasError():
        handle_error_message(ctx, "Error during runNanoJ: ", error_result.getError())
        return

    if error_result.getResult() != 0:
        handle_error_message(ctx, "Error during runNanoJ - program exited with error: ", str(error_result.getResult()))
        return

    # check if program is still running, stopped or has error
    read_number_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odNanoJStatus)
    if read_number_result.hasError():
        handle_error_message(ctx, "Error during runNanoJ: ", read_number_result.getError())
        return

    status = read_number_result.getResult()
    if status == 0:
        print("NanoJ program stopped ...")
    elif status == 1:
        print("NanoJ program running ...")
    else:
        print("NanoJ program exited with error.")

def stop_nanoj(ctx: Context):
    """Stops the NanoJ program on the current active device if available.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    writeNumber_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x00, OdIndex.odNanoJControl, 32)
    if writeNumber_result.hasError():
        handle_error_message(ctx, "Error during stopNanoJ: ", writeNumber_result.getError())
        return

    # stop might take some time
    time.sleep(0.05)

    read_number_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odNanoJStatus)
    if read_number_result.hasError():
        handle_error_message(ctx, "Error during stopNanoJ: ", read_number_result.getError())
        return

    status = read_number_result.getResult()
    if status == 0:
        print("NanoJ program stopped ...")
    elif status == 1:
        print("NanoJ program still running ...")
    else:
        error_code_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odNanoJError)
        error_code = error_code_result.getResult()
        print(f"NanoJ program exited with error: {error_code}")

def get_device_vendor_id(ctx: Context):
    """Read and output the device vendor id of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return 

    result_int: Nanolib.ResultInt = ctx.nanolib_accessor.getDeviceVendorId(ctx.active_device)

    if result_int.hasError():
        handle_error_message(ctx, "Error during getDeviceVendorId: ", result_int.getError())
        return

    print(f"Device vendor id = '{result_int.getResult()}'")

def get_device_product_code(ctx: Context):
    """Read and output the product code of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_int: Nanolib.ResultInt = ctx.nanolib_accessor.getDeviceProductCode(ctx.active_device)

    if result_int.hasError():
        handle_error_message(ctx, "Error during getDeviceProductCode: ", result_int.getError())
        return

    print(f"Device product code = '{result_int.getResult()}'")

def get_device_name(ctx: Context):
    """Read and output the device name of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_string: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceName(ctx.active_device)

    if result_string.hasError():
        handle_error_message(ctx, "Error during getDeviceName: ", result_string.getError())
        return

    print(f"Device name = '{result_string.getResult()}'")

def get_device_hardware_version(ctx: Context):
    """Read and output the hardware version of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_string: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceHardwareVersion(ctx.active_device)

    if result_string.hasError():
        handle_error_message(ctx, "Error during getDeviceHardwareVersion: ", result_string.getError())
        return

    print(f"Device hardware version = '{result_string.getResult()}'")

def get_device_firmware_build_id(ctx: Context):
    """Read and output the firmware build id of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_string: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceFirmwareBuildId(ctx.active_device)

    if result_string.hasError():
        handle_error_message(ctx, "Error during getDeviceFirmwareBuildId: ", result_string.getError())
        return

    print(f"Device firmware build id = '{result_string.getResult()}'")

def get_device_bootloader_build_id(ctx: Context):
    """Read and output the bootloader build id of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_string: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceBootloaderBuildId(ctx.active_device)

    if result_string.hasError():
        handle_error_message(ctx, "Error during getDeviceBootloaderBuildId: ", result_string.getError())
        return

    print(f"Device bootloader build id = '{result_string.getResult()}'")

def get_device_serial_number(ctx: Context):
    """Read and output the serial number of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_string: Nanolib.ResultString = ctx.nanolib_accessor.getDeviceSerialNumber(ctx.active_device)

    if result_string.hasError():
        handle_error_message(ctx, "Error during getDeviceSerialNumber: ", result_string.getError())
        return

    print(f"Device serial number = '{result_string.getResult()}'")

def get_device_uid(ctx: Context):
    """Read and output the device unique id of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True
    
    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    array_byte_result: Nanolib.ResultArrayByte = ctx.nanolib_accessor.getDeviceUid(ctx.active_device)

    if array_byte_result.hasError():
        handle_error_message(ctx, f"Error during get_device_uid : {array_byte_result.getError()}")
        return

    # Convert byte array to hex string
    hex_chars = "0123456789ABCDEF"
    s = []

    for c in array_byte_result.getResult():
        s.append(hex_chars[c // 16])
        s.append(hex_chars[c % 16])

    device_uid = ''.join(s)
    print(f"Device unique id = '{device_uid}'")

def get_device_bootloader_version(ctx: Context):
    """Read and output the bootloader version of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_int: Nanolib.ResultInt = ctx.nanolib_accessor.getDeviceBootloaderVersion(ctx.active_device)

    if result_int.hasError():
        handle_error_message(ctx, "Error during getDeviceBootloaderVersion: ", result_int.getError())
        return

    print(f"Device bootloader version = '{result_int.getResult() >> 16}'")

def get_device_hardware_group(ctx: Context):
    """Read and output the hardware group of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_int: Nanolib.ResultInt = ctx.nanolib_accessor.getDeviceHardwareGroup(ctx.active_device)

    if result_int.hasError():
        handle_error_message(ctx, "Error during getDeviceHardwareGroup: ", result_int.getError())
        return

    print(f"Device hardware group = '{result_int.getResult()}'")

def get_connection_state(ctx: Context):
    """Read and output connection state of the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_con_state: Nanolib.ResultConnectionState = ctx.nanolib_accessor.getConnectionState(ctx.active_device)

    if result_con_state.hasError():
        handle_error_message(ctx, "Error during getConnectionState: ", result_con_state.getError())
        return

    connection_state_map = {
        Nanolib.DeviceConnectionStateInfo_Connected: "Connected",
        Nanolib.DeviceConnectionStateInfo_Disconnected: "Disconnected",
        Nanolib.DeviceConnectionStateInfo_ConnectedBootloader: "Connected to bootloader",
    }

    connection_state = connection_state_map.get(result_con_state.getResult(), "unknown")
    print(f"Device connection state = '{connection_state}'")

def get_error_fields(ctx: Context):
    """Read and output error-stack.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    error_number_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odErrorCount)
    if error_number_result.hasError():
        handle_error_message(ctx, "Error during getErrorField: ", error_number_result.getError())
        return

    if error_number_result.getResult() == 0:
        print("Currently there are no errors.")
        return

    number_of_errors = error_number_result.getResult()
    print(f"Currently there are {number_of_errors} errors.")

    for i in range(1, number_of_errors + 1):
        error_number_result = ctx.nanolib_accessor.readNumber(ctx.active_device, Nanolib.OdIndex(OdIndex.odErrorStackIndex, i))

        if error_number_result.hasError():
            handle_error_message(ctx, "Error during getErrorField: ", error_number_result.getError())
            return

        # Decode error field
        print(f"- Error Number [{i}] = {get_error_number_string(error_number_result.getResult())}")
        print(f"- Error Class  [{i}] = {get_error_class_string(error_number_result.getResult())}")
        print(f"- Error Code   [{i}] = {get_error_code_string(error_number_result.getResult())}")

def restore_defaults(ctx: Context):
    """Reset encoder resolution interfaces, reset drive mode selection and restore all default parameters.
    
    :param ctx: menu context
    """
    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    # Read position encoder resolution interfaces
    pos_encoder_res_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odPosEncoderIncrementsInterface1)
    if not pos_encoder_res_result.hasError():
        print(f"Position encoder resolution - encoder increments feedback interface #1 = {pos_encoder_res_result.getResult()}")
    pos_encoder_res_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odPosEncoderIncrementsInterface2)
    if not pos_encoder_res_result.hasError():
        print(f"Position encoder resolution - encoder increments feedback interface #2 = {pos_encoder_res_result.getResult()}")
    pos_encoder_res_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odPosEncoderIncrementsInterface3)
    if not pos_encoder_res_result.hasError():
        print(f"Position encoder resolution - encoder increments feedback interface #3 = {pos_encoder_res_result.getResult()}")

    # Set interface values to zero
    ctx.nanolib_accessor.writeNumber(ctx.active_device, 0, OdIndex.odPosEncoderIncrementsInterface1, 32)
    ctx.nanolib_accessor.writeNumber(ctx.active_device, 0, OdIndex.odPosEncoderIncrementsInterface2, 32)
    ctx.nanolib_accessor.writeNumber(ctx.active_device, 0, OdIndex.odPosEncoderIncrementsInterface3, 32)

    sub_mode_select_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odMotorDriveSubmodeSelect)
    print(f"Motor drive submode select = {sub_mode_select_result.getResult()}")

    # Set motor drive submode select to zero
    ctx.nanolib_accessor.writeNumber(ctx.active_device, 0, OdIndex.odMotorDriveSubmodeSelect, 32)

    # Save all parameters to non-volatile memory
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 1702257011, OdIndex.odStoreAllParams, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during restoreDefaults: ", write_result.getError())
        return

    # Wait until write has completed
    while True:
        store_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odStoreAllParams)
        if store_result.getResult() == 1:
            break

    # Reboot current active device
    print("Rebooting ...")
    reboot_result: Nanolib.ResultVoid = ctx.nanolib_accessor.rebootDevice(ctx.active_device)
    if reboot_result.hasError():
        handle_error_message(ctx, "Error during restoreDefaults: ", reboot_result.getError())

    # Restore all default parameters
    print("Restoring all default parameters ...")
    write_result = ctx.nanolib_accessor.writeNumber(ctx.active_device, 1684107116, OdIndex.odRestoreAllDefParams, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during restoreDefaults: ", write_result.getError())
        return

    # Restore tuning default parameters
    print("Restoring tuning default parameters ...")
    write_result = ctx.nanolib_accessor.writeNumber(ctx.active_device, 1684107116, OdIndex.odRestoreTuningDefParams, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during restoreDefaults: ", write_result.getError())
        return

    # Reboot current active device
    print("Rebooting ...")
    reboot_result = ctx.nanolib_accessor.rebootDevice(ctx.active_device)
    if reboot_result.hasError():
        handle_error_message(ctx, "Error during restoreDefaults: ", reboot_result.getError())

    print("All done. Check for errors.")
