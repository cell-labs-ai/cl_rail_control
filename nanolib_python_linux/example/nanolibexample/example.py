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
# @file   example.py
#
# @brief  Main function, definition of menu structure, signal handling etc.
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

import signal
import sys
import time

# Placeholder imports for required functionalities
from menu_utils import *
from sampler_example import *
from bus_functions_example import *
from device_functions_example import *
from logging_functions_example import *
from od_interface_functions_example import *
from profinet_functions_example import *
from sampler_functions_example import *
from motor_functions_example import *
from nanotec_nanolib import *
from logging_callback_example import LoggingCallbackExample
from scan_bus_callback_example import ScanBusCallbackExample
from data_transfer_callback_example import DataTransferCallbackExample

# Function to build the connect device menu
def build_connect_device_menu(ctx):
    """Set default function for dynamic connect device menu.
    
    :param ctx: menu context
    """
    connect_device_menu = Menu(DEVICE_CONNECT_MENU, [], connect_device)
    connect_device_menu.menu(ctx)

# Function to build the disconnect from device menu
def build_disconnect_device_menu(ctx):
    """Set default function for dynamic disconnect device menu.
    
    :param ctx: menu context
    """
    disconnect_device_menu = Menu(DEVICE_DISCONNECT_MENU, [], disconnect_device)
    disconnect_device_menu.menu(ctx)

# Function to build the open bus hardware menu
def build_open_bus_hw_menu(ctx):
    """Set default function for dynamic open bus hardware menu.
    
    :param ctx: menu context
    """
    open_bus_hw_menu = Menu(BUS_HARDWARE_OPEN_MI, [], open_bus_hardware)
    open_bus_hw_menu.menu(ctx)

# Function to build the close bus hardware menu
def build_close_bus_hw_menu(ctx):
    """Set default function for dynamic close bus hardware menu.
    
    :param ctx: menu context
    """
    close_bus_hw_menu = Menu(BUS_HARDWARE_CLOSE_MI, [], close_bus_hardware)
    close_bus_hw_menu.menu(ctx)

# Function to build the select active device menu
def build_select_active_device_menu(ctx):
    """Set default function for dynamic select active device menu.
    
    :param ctx: menu context
    """
    select_active_device_menu = Menu(DEVICE_SELECT_ACTIVE_MENU, [], select_active_device)
    select_active_device_menu.menu(ctx)

# Signal handler function
def signal_handler(sig, frame):
    """Set default function for dynamic connect device menu.
    
    :param sig: the signal received
    :param frame: stack frame (not used)
    """
    print(f"Interrupt signal '{sig}' received. Exiting ...")
    sys.exit(sig)

# Main function
def main():
    """The Main function."""
    # Register signal handlers
    signal.signal(signal.SIGABRT, signal_handler)
    signal.signal(signal.SIGFPE, signal_handler)
    signal.signal(signal.SIGILL, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGSEGV, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # Add SIGBREAK if applicable in your environment

    context = Context()  # The menu context
    logging_callback = LoggingCallbackExample()  # Instantiate a logging callback 
    scan_bus_callback = ScanBusCallbackExample()  # Instantiate a scan bus callback 
    data_transfer_callback = DataTransferCallbackExample()  # Instantiate a data transfer callback 

    # Setup menu context
    context.current_log_level = Nanolib.LogLevel_Off  # No logging output at start
    context.logging_callback_active = False  # No logging callback active
    context.logging_callback = logging_callback  # Store pointer to logging callback object
    context.scan_bus_callback = scan_bus_callback  # Store pointer to scan bus callback object
    context.data_transfer_callback = data_transfer_callback  # Store pointer to data transfer callback object
    context.wait_for_user_confirmation = False  # Flag to stop at end of a menu function

    # Set log level to off
    context.nanolib_accessor.setLoggingLevel(Nanolib.LogLevel_Off)

    # Build the motor menu
    motor_menu = Menu(MOTOR_EXAMPLE_MENU, [
        Menu.MenuItem(MOTOR_AUTO_SETUP_MI, motor_auto_setup, False),
        Menu.MenuItem(MOTOR_VELOCITY_MI, execute_profile_velocity_mode, False),
        Menu.MenuItem(MOTOR_POSITIONING_MI, execute_positioning_mode, False)
    ])

    # Build the sampler menu
    sampler_menu = Menu(SAMPLER_EXAMPLE_MENU, [
        Menu.MenuItem(SAMPLER_NORMAL_WO_NOTIFY_MI, execute_sampler_without_notification_normal_mode, False),
        Menu.MenuItem(SAMPLER_REPETETIVE_WO_NOTIFY_MI, execute_sampler_without_notification_repetitive_mode, False),
        Menu.MenuItem(SAMPLER_CONTINUOUS_WO_NOTIFY_MI, execute_sampler_without_notification_continuous_mode, False),
        Menu.MenuItem(SAMPLER_NORMAL_WITH_NOTIFY_MI, execute_sampler_with_notification_normal_mode, False),
        Menu.MenuItem(SAMPLER_REPETETIVE_WITH_NOTIFY_MI, execute_sampler_with_notification_repetitive_mode, False),
        Menu.MenuItem(SAMPLER_CONTINUOUS_WITH_NOTIFY_MI, execute_sampler_with_notification_continuous_mode, False)
    ])

    # Build the log callback menu
    log_callback_menu = Menu(LOG_CALLBACK_MENU, [
        Menu.MenuItem(LOG_CALLBACK_CORE_MI, set_logging_callback, False),
        Menu.MenuItem(LOG_CALLBACK_CANOPEN_MI, set_logging_callback, False),
        Menu.MenuItem(LOG_CALLBACK_ETHERCAT_MI, set_logging_callback, False),
        Menu.MenuItem(LOG_CALLBACK_MODBUS_MI, set_logging_callback, False),
        Menu.MenuItem(LOG_CALLBACK_REST_MI, set_logging_callback, False),
        Menu.MenuItem(LOG_CALLBACK_USB_MI, set_logging_callback, False),
        Menu.MenuItem(LOG_CALLBACK_DEACTIVATE_MI, set_logging_callback, False)
    ])

    # Build the log level menu
    log_level_menu = Menu(LOG_LEVEL_MENU, [
        Menu.MenuItem(LOG_LEVEL_TRACE_MI, set_log_level, False),
        Menu.MenuItem(LOG_LEVEL_DEBUG_MI, set_log_level, False),
        Menu.MenuItem(LOG_LEVEL_INFO_MI, set_log_level, False),
        Menu.MenuItem(LOG_LEVEL_WARN_MI, set_log_level, False),
        Menu.MenuItem(LOG_LEVEL_ERROR_MI, set_log_level, False),
        Menu.MenuItem(LOG_LEVEL_CRITICAL_MI, set_log_level, False),
        Menu.MenuItem(LOG_LEVEL_OFF_MI, set_log_level, False)
    ])

    # Build the logging menu
    logging_menu = Menu(LOGGING_MENU, [
        Menu.MenuItem(LOGGING_SET_LOG_LEVEL_MI, log_level_menu, True),
        Menu.MenuItem(LOGGING_SET_LOG_CALLBACK_MI, log_callback_menu, True)
    ])

    # Build the OD access menu
    od_access_menu = Menu(OD_INTERFACE_MENU, [
        Menu.MenuItem(OD_ASSIGN_OD_MI, assign_object_dictionary, False),
        Menu.MenuItem(OD_READ_NUMBER_MI, read_number, False),
        Menu.MenuItem(OD_READ_NUMBER_VIA_OD_MI, read_number_via_dictionary_interface, False),
        Menu.MenuItem(OD_WRITE_NUMBER_MI, write_number, False),
        Menu.MenuItem(OD_WRITE_NUMBER_VIA_OD_MI, write_number_via_dictionary_interface, False),
        Menu.MenuItem(OD_READ_STRING_MI, read_string, False),
        Menu.MenuItem(OD_READ_BYTES_MI, read_array, False)
    ])

    # Build the device info menu
    device_info_menu = Menu(DEVICE_INFORMATION_MENU, [
        Menu.MenuItem(DEVICE_GET_VENDOR_ID_MI, get_device_vendor_id, False),
        Menu.MenuItem(DEVICE_GET_PRODUCT_CODE_MI, get_device_product_code, False),
        Menu.MenuItem(DEVICE_GET_DEVICE_NAME_MI, get_device_name, False),
        Menu.MenuItem(DEVICE_GET_HW_VERSION_MI, get_device_hardware_version, False),
        Menu.MenuItem(DEVICE_GET_FW_BUILD_ID_MI, get_device_firmware_build_id, False),
        Menu.MenuItem(DEVICE_GET_BL_BUILD_ID_MI, get_device_bootloader_build_id, False),
        Menu.MenuItem(DEVICE_GET_SERIAL_NUMBER_MI, get_device_serial_number, False),
        Menu.MenuItem(DEVICE_GET_UNIQUE_ID_MI, get_device_uid, False),
        Menu.MenuItem(DEVICE_GET_BL_VERSION_MI, get_device_bootloader_version, False),
        Menu.MenuItem(DEVICE_GET_HW_GROUP_MI, get_device_hardware_group, False),
        Menu.MenuItem(DEVICE_GET_CON_STATE_MI, get_connection_state, False)
    ])

    # Build the device menu
    device_menu = Menu(DEVICE_MENU, [
        Menu.MenuItem(DEVICE_SCAN_MI, scan_devices, False),
        Menu.MenuItem(DEVICE_CONNECT_MENU, build_connect_device_menu, False),
        Menu.MenuItem(DEVICE_DISCONNECT_MENU, build_disconnect_device_menu, False),
        Menu.MenuItem(DEVICE_SELECT_ACTIVE_MENU, build_select_active_device_menu, False),
        Menu.MenuItem(DEVICE_REBOOT_MI, reboot_device, False),
        Menu.MenuItem(DEVICE_INFORMATION_MENU, device_info_menu, False),
        Menu.MenuItem(DEVICE_UPDATE_FW_MI, update_firmware, False),
        Menu.MenuItem(DEVICE_UPDATE_BL_MI, update_bootloader, False),
        Menu.MenuItem(DEVICE_UPLOAD_NANOJ_MI, upload_nanoj, False),
        Menu.MenuItem(DEVICE_RUN_NANOJ_MI, run_nanoj, False),
        Menu.MenuItem(DEVICE_STOP_NANOJ_MI, stop_nanoj, False),
        Menu.MenuItem(DEVICE_GET_ERROR_FIELD_MI, get_error_fields, False),
        Menu.MenuItem(DEVICE_RESTORE_ALL_DEFAULT_PARAMS_MI, restore_defaults, False)
    ])

    # Build the bus hardware menu
    bus_hw_menu = Menu(BUS_HARDWARE_MENU, [
        Menu.MenuItem(BUS_HARDWARE_SCAN_MI, scan_bus_hardware, True),
        Menu.MenuItem(BUS_HARDWARE_OPEN_MI, build_open_bus_hw_menu, False),
        Menu.MenuItem(BUS_HARDWARE_CLOSE_MI, build_close_bus_hw_menu, False),
        Menu.MenuItem(BUS_HARDWARE_CLOSE_ALL_MI, close_all_bus_hardware, False)
    ])

    # Build the main menu
    main_menu = Menu(MAIN_MENU, [
        Menu.MenuItem(BUS_HARDWARE_MENU, bus_hw_menu, True),
        Menu.MenuItem(DEVICE_MENU, device_menu, False),
        Menu.MenuItem(OD_INTERFACE_MENU, od_access_menu, False),
        Menu.MenuItem(LOGGING_MENU, logging_menu, True),
        Menu.MenuItem(SAMPLER_EXAMPLE_MENU, sampler_menu, False),
        Menu.MenuItem(MOTOR_EXAMPLE_MENU, motor_menu, False),
        Menu.MenuItem(PROFINET_EXAMPLE_MI, profinet_dcp_example, False)
    ])

    # Start the main menu
    main_menu.menu(context)

    # Close all opened bus hardware
    close_all_bus_hardware(context)

    # Exit main program
    return 0

if __name__ == "__main__":
    main()
