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
# @file   menu_utils.py
#
# @brief  Definition of CLI menu specific classes
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

import os, sys
from typing import Callable, List, Optional, TypeVar, Any, Union
from menu_color import MenuColor, ColorModifier
from nanotec_nanolib import Nanolib 

# Constants for Object Dictionary (OD) Indices
class OdIndex:
    """ Od index class for often used od indices."""
    def __init__(self, index: int, subindex: int):
        self.index = index
        self.subindex = subindex

    odSIUnitPosition = Nanolib.OdIndex(0x60A8, 0x00)
    odControlWord = Nanolib.OdIndex(0x6040, 0x00)
    odStatusWord = Nanolib.OdIndex(0x6041, 0x00)
    odHomePage = Nanolib.OdIndex(0x6505, 0x00)
    odNanoJControl = Nanolib.OdIndex(0x2300, 0x00)
    odNanoJStatus = Nanolib.OdIndex(0x2301, 0x00)
    odNanoJError = Nanolib.OdIndex(0x2302, 0x00)
    odModeOfOperation = Nanolib.OdIndex(0x6060, 0x00)
    odTargetVelocity = Nanolib.OdIndex(0x60FF, 0x00)
    odProfileVelocity = Nanolib.OdIndex(0x6081, 0x00)
    odTargetPosition = Nanolib.OdIndex(0x607A, 0x00)
    odErrorStackIndex = 0x1003
    odErrorCount = Nanolib.OdIndex(0x1003, 0x00)
    odPosEncoderIncrementsInterface1 = Nanolib.OdIndex(0x60E6, 0x1)
    odPosEncoderIncrementsInterface2 = Nanolib.OdIndex(0x60E6, 0x2)
    odPosEncoderIncrementsInterface3 = Nanolib.OdIndex(0x60E6, 0x3)
    odMotorDriveSubmodeSelect = Nanolib.OdIndex(0x3202, 0x00)
    odStoreAllParams = Nanolib.OdIndex(0x1010, 0x01)
    odRestoreAllDefParams = Nanolib.OdIndex(0x1011, 0x01)
    odRestoreTuningDefParams = Nanolib.OdIndex(0x1011, 0x06)
    odModeOfOperationDisplay = Nanolib.OdIndex(0x6061, 0x00)

# Menu texts
BUS_HARDWARE_MENU = "Bus Hardware Menu"
BUS_HARDWARE_OPEN_MI = "Open Bus Hardware"
BUS_HARDWARE_CLOSE_MI = "Close bus hardware"
BUS_HARDWARE_SCAN_MI = "Scan for Bus hardware"
BUS_HARDWARE_CLOSE_ALL_MI = "Close all bus hardware"

DEVICE_MENU = "Device Menu"
DEVICE_SCAN_MI = "Scan for Devices"
DEVICE_CONNECT_MENU = "Connect to device Menu"
DEVICE_DISCONNECT_MENU = "Disconnect from device Menu"
DEVICE_SELECT_ACTIVE_MENU = "Select active device"
DEVICE_REBOOT_MI = "Reboot device"
DEVICE_UPDATE_FW_MI = "Update firmware"
DEVICE_UPDATE_BL_MI = "Update bootloader"
DEVICE_UPLOAD_NANOJ_MI = "Upload NanoJ program"
DEVICE_RUN_NANOJ_MI = "Run NanoJ program"
DEVICE_STOP_NANOJ_MI = "Stop NanoJ program"

DEVICE_INFORMATION_MENU = "Device information Menu"
DEVICE_GET_VENDOR_ID_MI = "Read vendor Id"
DEVICE_GET_PRODUCT_CODE_MI = "Read product code"
DEVICE_GET_DEVICE_NAME_MI = "Read device name"
DEVICE_GET_HW_VERSION_MI = "Read device hardware version"
DEVICE_GET_FW_BUILD_ID_MI = "Read device firmware build id"
DEVICE_GET_BL_BUILD_ID_MI = "Read device bootloader build id"
DEVICE_GET_SERIAL_NUMBER_MI = "Read device serial number"
DEVICE_GET_UNIQUE_ID_MI = "Read device unique id"
DEVICE_GET_BL_VERSION_MI = "Read device bootloader version"
DEVICE_GET_HW_GROUP_MI = "Read device hardware group"
DEVICE_GET_CON_STATE_MI = "Read device connection state"
DEVICE_GET_ERROR_FIELD_MI = "Read device error field"
DEVICE_RESTORE_ALL_DEFAULT_PARAMS_MI = "Restore all default parameters"

OD_INTERFACE_MENU = "Object Dictionary Interface Menu"
OD_ASSIGN_OD_MI = "Assign an object dictionary to active device (e.g. od.xml)"
OD_READ_NUMBER_MI = "readNumber (raw, untyped)"
OD_READ_STRING_MI = "readString"
OD_READ_BYTES_MI = "readBytes (raw, untyped)"
OD_WRITE_NUMBER_MI = "writeNumber (data bitlength needed)"
OD_READ_NUMBER_VIA_OD_MI = "readNumber (via OD interface, get type information)"
OD_WRITE_NUMBER_VIA_OD_MI = "writeNumber (via OD interface, no data bitlength needed)"

LOGGING_MENU = "Logging Menu"
LOGGING_SET_LOG_LEVEL_MI = "Set log level"
LOGGING_SET_LOG_CALLBACK_MI = "Set logging callback"

LOG_LEVEL_MENU = "Log level Menu"
LOG_LEVEL_TRACE_MI = "Set log level to 'Trace'"
LOG_LEVEL_DEBUG_MI = "Set log level to 'Debug'"
LOG_LEVEL_INFO_MI = "Set log level to 'Info'"
LOG_LEVEL_WARN_MI = "Set log level to 'Warning'"
LOG_LEVEL_ERROR_MI = "Set log level to 'Error'"
LOG_LEVEL_CRITICAL_MI = "Set log level to 'Critical'"
LOG_LEVEL_OFF_MI = "Set log level to 'Off'"

LOG_CALLBACK_MENU = "Logging Callback Menu"
LOG_CALLBACK_CORE_MI = "Activate log callback for Nanolib Core"
LOG_CALLBACK_CANOPEN_MI = "Activate log callback for CANopen module"
LOG_CALLBACK_ETHERCAT_MI = "Activate log callback for EtherCAT module"
LOG_CALLBACK_MODBUS_MI = "Activate log callback for Modbus module"
LOG_CALLBACK_REST_MI = "Activate log callback for REST module"
LOG_CALLBACK_USB_MI = "Activate log callback for USB/MSC module"
LOG_CALLBACK_DEACTIVATE_MI = "Deactivate current log callback"

SAMPLER_EXAMPLE_MENU = "Sampler Example Menu"
SAMPLER_NORMAL_WO_NOTIFY_MI = "Sampler w/o Notification - Normal Mode"
SAMPLER_REPETETIVE_WO_NOTIFY_MI = "Sampler w/o Notification - Repetetive Mode"
SAMPLER_CONTINUOUS_WO_NOTIFY_MI = "Sampler w/o Notification - Continuous Mode"
SAMPLER_NORMAL_WITH_NOTIFY_MI = "Sampler with Notification - Normal Mode"
SAMPLER_REPETETIVE_WITH_NOTIFY_MI = "Sampler with Notification - Repetetive Mode"
SAMPLER_CONTINUOUS_WITH_NOTIFY_MI = "Sampler with Notification - Continuous Mode"

MOTOR_EXAMPLE_MENU = "Motor Example Menu"
MOTOR_AUTO_SETUP_MI = "Initial commissioning - motor auto setup"
MOTOR_VELOCITY_MI = "Run a motor in profile velocity mode"
MOTOR_POSITIONING_MI = "Run a motor in positioning mode"

PROFINET_EXAMPLE_MI = "ProfinetDCP example"
MAIN_MENU = "Nanolib Example Main"

# Context structure
class Context:
    """Container class for menu context informations."""
    def __init__(self):
        self.selected_option: int = 0
        self.error_text: str = ""
        self.current_log_level: Optional[int] = None
        self.nanolib_accessor: Nanolib.NanoLibAccessor = Nanolib.getNanoLibAccessor()
        self.scanned_bus_hardware_ids: List[Nanolib.BusHardwareId] = []
        self.openable_bus_hardware_ids: List[Nanolib.BusHardwareId] = []
        self.open_bus_hardware_ids: List[Nanolib.BusHardwareId] = []
        self.scanned_device_ids: List[Nanolib.DeviceId] = []
        self.connectable_device_ids: List[Nanolib.DeviceId] = []
        self.connected_device_handles: List[Nanolib.DeviceHandle] = []
        self.active_device: Optional[Nanolib.DeviceHandle] = None
        self.current_log_module: Optional[int] = None
        self.logging_callback_active: bool = False
        self.wait_for_user_confirmation: bool = False
        self.logging_callback: Optional[Nanolib.NlcLoggingCallback] = None
        self.scan_bus_callback: Optional[Nanolib.NlcScanBusCallback] = None
        self.data_transfer_callback: Optional[Nanolib.NlcDataTransferCallback] = None
        self.red: str = ColorModifier(MenuColor.FG_RED).__str__()  # ANSI escape codes for colors
        self.green: str =  ColorModifier(MenuColor.FG_GREEN).__str__()
        self.blue: str = ColorModifier(MenuColor.FG_BLUE).__str__()
        self.yellow: str = ColorModifier(MenuColor.FG_YELLOW).__str__()
        self.light_red: str = ColorModifier(MenuColor.FG_LIGHT_RED).__str__()
        self.light_green: str = ColorModifier(MenuColor.FG_LIGHT_GREEN).__str__()
        self.light_blue: str = ColorModifier(MenuColor.FG_LIGHT_BLUE).__str__()
        self.light_yellow: str = ColorModifier(MenuColor.FG_LIGHT_YELLOW).__str__()
        self.dark_gray: str = ColorModifier(MenuColor.FG_DARK_GRAY).__str__()
        self.def_color: str = ColorModifier(MenuColor.FG_DEFAULT).__str__()
        self.reset_all: str = ColorModifier(MenuColor.RESET).__str__()

# Helper functions
def get_error_number_string(number: int) -> str:
    """Get error class string based on the highest byte.
    
    :param number: the 32-bit error, containing error number, error class and error code
    :return: The error number as a human readable string
    """
    byte_value = (number >> 24) & 0xFF
    error_messages = {
        0: "    0: Watchdog Reset",
        1: "    1: Input voltage (+Ub) too high",
        2: "    2: Output current too high",
        3: "    3: Input voltage (+Ub) too low",
        4: "    4: Error at fieldbus",
        6: "    6: CANopen only: NMT master takes too long to send Nodeguarding request",
        7: "    7: Sensor 1 (see 3204h): Error through electrical fault or defective hardware",
        8: "    8: Sensor 2 (see 3204h): Error through electrical fault or defective hardware",
        9: "    9: Sensor 3 (see 3204h): Error through electrical fault or defective hardware",
        10: "   10: Positive limit switch exceeded",
        11: "   11: Negative limit switch exceeded",
        12: "   12: Overtemperature error",
        13: "   13: The values of object 6065h and 6066h were exceeded; a fault was triggered.",
        14: "   14: Watchdog failure",
        15: "   15: Electronic gearbox deviation too high",
        16: "   16: Command error (no user command provided)",
        17: "   17: Device state error (no mode of operation selected)",
        18: "   18: General error (not further specified)",
        19: "   19: Device fault",
        20: "   20: Encoder fault",
        21: "   21: Internal fault",
        22: "   22: Communication fault",
        23: "   23: Position fault",
        24: "   24: Reference search failed",
        25: "   25: Home error",
        26: "   26: Feedback fault",
        27: "   27: Configuration error",
        28: "   28: IO configuration fault",
        29: "   29: Current sensor fault",
        30: "   30: Mode of operation error",
        31: "   31: Overcurrent fault",
        32: "   32: Memory fault",
        33: "   33: Flash error",
        34: "   34: Short-circuit error",
        35: "   35: Hardware error",
        36: "   36: STO Changeover: STO was requested but not via both STO inputs.",
        37: "   37: STO Active: STO is active, it generates no torque or holding torque.",
        38: "   38: STO Self-Test: Error during self-test of the firmware. Contact Nanotec.",
        39: "   39: Error in the ballast configuration: Invalid/unrealistic parameters entered.",
        40: "   40: Ballast resistor thermally overloaded.",
        41: "   41: Only EtherCAT: Sync Manager Watchdog: The controller has not received any PDO data for an excessively long period of time.",
        46: "   46: Only EtherCAT: Sync Manager Length: The controller has received a PDO with an incorrect length.",
        48: "   48: Only CANopen: NMT status has been set to stopped.",   
    }
    return error_messages.get(byte_value, f"Unknown error number: {byte_value}")

def get_error_class_string(number):
    """Get error class string based on the second highest byte.

    :param number: the 32-bit error, containing error number, error class and error code
    :return: The error class as a human readable string
    """
    bit_mask = 0xff0000
    byte_value = (number & bit_mask) >> 16
    result_string = ""

    if byte_value == 1:
        result_string = "    1: General error, always set in the event of an error."
    elif byte_value == 2:
        result_string = "    2: Current."
    elif byte_value == 4:
        result_string = "    4: Voltage."
    elif byte_value == 8:
        result_string = "    8: Temperature."
    elif byte_value == 16:
        result_string = "   16: Communication."
    elif byte_value == 32:
        result_string = "   32: Relates to the device profile."
    elif byte_value == 64:
        result_string = "   64: Reserved, always 0."
    elif byte_value == 128:
        result_string = "  128: Manufacturer-specific."
    else:
        result_string = f"  {byte_value}: Unknown error class."

    return result_string

def get_error_code_string(number):
    """Get error code string based on the lower 16 bits.

    :param number: the 32-bit error, containing error number, error class and error code
    :return: The error code as a human readable string
    """
    bit_mask = 0xffff
    word_value = number & bit_mask
    result_string = ""

    error_codes = {
        0x1000: "0x1000: General error.",
        0x2300: "0x2300: Current at the controller output too large.",
        0x3100: "0x3100: Overvoltage/undervoltage at controller input.",
        0x4200: "0x4200: Temperature error within the controller.",
        0x5440: "0x5440: Interlock error: Bit 3 in 60FDh is set to 0, the motor may not start.",
        0x6010: "0x6010: Software reset (watchdog).",
        0x6100: "0x6100: Internal software error, generic.",
        0x6320: "0x6320: Rated current must be set (203Bh:01h/6075h).",
        0x7110: "0x7110: Error in the ballast configuration: Invalid/unrealistic parameters entered.",
        0x7113: "0x7113: Warning: Ballast resistor thermally overloaded.",
        0x7121: "0x7121: Motor blocked.",
        0x7200: "0x7200: Internal error: Correction factor for reference voltage missing in the OTP.",
        0x7305: "0x7305: Sensor 1 (see 3204h) faulty.",
        0x7306: "0x7306: Sensor 2 (see 3204h) faulty.",
        0x7307: "0x7307: Sensor n (see 3204h), where n is greater than 2.",
        0x7600: "0x7600: Warning: Nonvolatile memory full or corrupt; restart the controller for cleanup work.",
        0x8100: "0x8100: Error during fieldbus monitoring.",
        0x8130: "0x8130: CANopen only: Life Guard error or Heartbeat error.",
        0x8200: "0x8200: CANopen only: Slave took too long to send PDO messages.",
        0x8210: "0x8210: CANopen only: PDO was not processed due to a length error.",
        0x8220: "0x8220: CANopen only: PDO length exceeded.",
        0x8240: "0x8240: CANopen only: unexpected sync length.",
        0x8400: "0x8400: Error in speed monitoring: slippage error too large.",
        0x8611: "0x8611: Position monitoring error: Following error too large.",
        0x8612: "0x8612: Position monitoring error: Limit switch exceeded."
    }

    if word_value in error_codes:
        result_string = error_codes[word_value]
    else:
        result_string = f"{word_value}: Unknown error code."

    return result_string

def create_bus_hardware_options(bus_hardware_id: Nanolib.BusHardwareId):
    """Helper function to create bus hardware options.

    :param bus_hardware_id: The bus hardware id to use
    :return: Nanolib.BusHardwareOptions for bus hardware id
    """
    # Create new bus hardware options
    bus_hw_options: Nanolib.BusHardwareOptions = Nanolib.BusHardwareOptions()

    # Add options necessary for opening the bus hardware based on the protocol
    if bus_hardware_id.getProtocol() == Nanolib.BUS_HARDWARE_ID_PROTOCOL_CANOPEN:
        # For CAN bus, add the baud rate option
        bus_hw_options.addOption(
            Nanolib.CanBus().BAUD_RATE_OPTIONS_NAME,
            Nanolib.CanBaudRate().BAUD_RATE_1000K
        )

        if bus_hardware_id.getBusHardware() == Nanolib.BUS_HARDWARE_ID_IXXAT:
            # For HMS IXXAT, add the bus number option
            bus_hw_options.addOption(
                Nanolib.Ixxat().ADAPTER_BUS_NUMBER_OPTIONS_NAME,
                Nanolib.IxxatAdapterBusNumber().BUS_NUMBER_0_DEFAULT
            )

        if bus_hardware_id.getBusHardware() == Nanolib.BUS_HARDWARE_ID_PEAK:
            # For Peak PCAN, add the bus number option
            bus_hw_options.addOption(
                Nanolib.Peak().ADAPTER_BUS_NUMBER_OPTIONS_NAME,
                Nanolib.PeakAdapterBusNumber().BUS_NUMBER_1_DEFAULT
            )
    elif bus_hardware_id.getProtocol() == Nanolib.BUS_HARDWARE_ID_PROTOCOL_MODBUS_RTU:
        # For Modbus RTU, add the serial baud rate option
        bus_hw_options.addOption(
            Nanolib.Serial().BAUD_RATE_OPTIONS_NAME,
            Nanolib.SerialBaudRate().BAUD_RATE_19200
        )
        # Add the serial parity option
        bus_hw_options.addOption(
            Nanolib.Serial().PARITY_OPTIONS_NAME,
            Nanolib.SerialParity().EVEN
        )

    return bus_hw_options

def get_num(prompt: str = "", nmin = 0, nmax = 0) -> Optional[int]:
    """ Function to obtain a number from the console

    :param str: optional prompt string
    :param str: minimum option number to enter (optional)
    :param str: maximum option number to enter (optional)
    :return: entered number if valid or sys.maxsize in case of error
    """
    while True:
        try:
            prompt = prompt + " ("+ str(nmin) + " - " + str(nmax) +"): "
            choice = int(input(prompt))
            if nmin <= choice <= nmax:
                return choice
            else:
                # invalid input
                return sys.maxsize
        except ValueError:
            # invalid input
            return sys.maxsize

def get_string_with_prompt(prompt: str = "") -> str:
    """Function to obtain a char from the console

    :param str: optional prompt string
    :return: entered string if valid or None in case of error
    """
    try:
        line = str(input(prompt))
        if (len(line) == 0):
            return None
        else:
            return line
    except ValueError:
        #invalid input
        return None
        
def handle_error_message(ctx: 'Context', error_string: str, error_reason_string: str = "") -> str:
    """Function to handle error messages

    :param ctx: the menu context
    :param error_string: error string will be colored light yellow
    :param error_string: error reason string will be colored light red
    :return: error message as colored string
    """
    error_message = f"{ctx.light_yellow}{error_string}{ctx.light_red}{error_reason_string}{ctx.def_color}" 
    ctx.error_text = error_message
    if ctx.wait_for_user_confirmation:
        try:
            print(error_message)
        except UnicodeEncodeError:
            # the error message contains non-utf8 characters
            # try to convert it, some characters may be lost
            error_reason_string = error_reason_string.encode('utf-8', 'replace').decode()
            error_message = f"{ctx.light_yellow}{error_string}{ctx.light_red}{error_reason_string}{ctx.def_color}" 
            ctx.error_text = error_message
            print(error_message)
    return error_message

# Define a type for the function pointer (void function taking a Context)
f_type = Callable[['Context'], None]

class Menu:
    """The menu class.
    
    A menu contains a name, a list of menu items (optional) and a default function pointer (optional)
    """
    # MenuItem contains a name and a pointer to a menu or a function
    class MenuItem:
        """The menu item class.
        
        A menu item contains a name, a pointer to a menu or a function and an active flag (optional)
        """
        def __init__(self, name: str, func: Union[f_type, 'Menu'], is_active: bool = True):
            self.name = name
            self.func = func
            self.is_active = is_active

    def __init__(self, title="", menu_items=None, default_func=None):
        self.title = title
        if menu_items is None:
            self.menu_items = []
        else:
            self.menu_items = menu_items
        self.default_func = default_func

    def get_title(self) -> str:
        """Get the menu title
        
        :return: the menu title as str
        """
        return self.title

    def set_title(self, title: str) -> None:
        """Set the menu title

        :param title: title as str
        """
        self.title = title

    def get_default_function(self) -> Optional[f_type]:
        """Get the default function for dynamic menus

        :return: Default function as f_type or None
        """
        return self.default_func

    def menu(self, ctx: 'Context') -> None:
        """Show a menu
        
        :param ctx: the menu context
        """
        self.run(ctx)

    def erase_menu_item(self, index):
        """Erase a menu item from menu item list

        :param index: The index of menu item in the menu item list
        """
        if index < len(self.menu_items):
            del self.menu_items[index]
            return True
        return False

    def erase_all_menu_items(self):
        """Erase all menu items from menu item list"""
        self.menu_items.clear()
        return True

    def append_menu_item(self, menu_item):
        """Add a menu item to the menu item list

        :param menu_item: The menu item to add
        """
        self.menu_items.append(menu_item)
        return True

    def insert_menu_item(self, index, menu_item):
        """Add a menu item to menu item list at index

        :param index: The index of menu item in the menu item list
        :param menu_item: The menu item to add
        """
        if index < len(self.menu_items):
            self.menu_items.insert(index, menu_item)
            return True
        return False
    
    @staticmethod
    def busHardwareIdEquals(busHwId: Nanolib.BusHardwareId, otherBusHwId: Nanolib.BusHardwareId):
        """Helper function to compare two bus hardware ids with eachother

        :param busHwId: First bus hardware id
        :param otherBusHwId: Second bus hardware id
        :return: True if equal, False if not equal
        """
        if ((busHwId.getBusHardware() == otherBusHwId.getBusHardware()) and 
            (busHwId.getExtraHardwareSpecifier() == otherBusHwId.getExtraHardwareSpecifier()) and 
            (busHwId.getHardwareSpecifier() == otherBusHwId.getHardwareSpecifier()) and 
            (busHwId.getName() == otherBusHwId.getName()) and 
            (busHwId.getProtocol() == otherBusHwId.getProtocol())):
            return True
        return False
    
    @staticmethod
    def deviceIdEquals(deviceId: 'Nanolib.DeviceId', otherDeviceId: 'Nanolib.DeviceId'):
        """Helper function to compare two device ids with eachother

        :param deviceId: First device id
        :param otherDeviceId: Second device id
        :return: True if equal, False if not equal
        """
        if ((Menu.busHardwareIdEquals(deviceId.getBusHardwareId(), otherDeviceId.getBusHardwareId())) and 
            (deviceId.getDescription() == otherDeviceId.getDescription()) and 
            (deviceId.getDeviceId() == otherDeviceId.getDeviceId()) and
            (deviceId.getExtraStringId() == otherDeviceId.getExtraStringId())):
            return True
        return False

    @staticmethod
    def get_connectable_device_ids(ctx: 'Context'):
        """Helper function to list available devices not yet connected

        :param ctx: The menu context
        :return: list of connectable device ids
        """
        result: list[Nanolib.DeviceId] = []
        for scanned_device_id in ctx.scanned_device_ids:
            already_connected = False
            for handle in ctx.connected_device_handles:
                device_id_result: Nanolib.ResultDeviceId = ctx.nanolib_accessor.getDeviceId(handle)
                if Menu.deviceIdEquals(device_id_result.getResult(), scanned_device_id):
                    already_connected = True
                    break
            if not already_connected:
                result.append(scanned_device_id)
        return result

    @staticmethod
    def get_openable_bus_hw_ids(ctx: 'Context'):
        """Helper function to list available bus hardware ids not yet opened

        :param ctx: The menu context
        :return: list of openable bus hardware ids
        """
        result: list[Nanolib.BusHardwareId] = []
        for scanned_bus_hw in ctx.scanned_bus_hardware_ids:
            already_opened = any(Menu.busHardwareIdEquals(open_hw_id, scanned_bus_hw) for open_hw_id in ctx.open_bus_hardware_ids)
            if not already_opened:
                result.append(scanned_bus_hw)
        return result

    @staticmethod
    def set_menu_items(menu: 'Menu', ctx: 'Context'):
        """Helper function to enable or disable menu items 

        :param ctx: The menu context
        """
        if menu.get_title() == MAIN_MENU:
            # Check main menu items
            for mi in menu.menu_items:
                if mi.name == BUS_HARDWARE_MENU:
                    # Always true since first possible action
                    mi.is_active = True
                elif mi.name == DEVICE_MENU:
                    # Active if bus hardware opened
                    mi.is_active = len(ctx.open_bus_hardware_ids) > 0
                elif mi.name in {OD_INTERFACE_MENU, SAMPLER_EXAMPLE_MENU, MOTOR_EXAMPLE_MENU, PROFINET_EXAMPLE_MI}:
                    # Active if active device is set
                    mi.is_active = ctx.active_device != None
                elif mi.name == LOGGING_MENU:
                    # Always true, always possible
                    mi.is_active = True
                else:
                    # Do nothing
                    pass

        elif menu.get_title() == BUS_HARDWARE_MENU:
            for mi in menu.menu_items:
                if mi.name == BUS_HARDWARE_SCAN_MI:
                    # Always active
                    mi.is_active = True
                elif mi.name == BUS_HARDWARE_OPEN_MI:
                    # Active if we have bus hardware to open
                    mi.is_active = len(ctx.openable_bus_hardware_ids) > 0
                elif mi.name in {BUS_HARDWARE_CLOSE_MI, BUS_HARDWARE_CLOSE_ALL_MI}:
                    # Active if we have opened bus hardware before
                    mi.is_active = len(ctx.open_bus_hardware_ids) > 0
                else:
                    # Do nothing
                    pass

        elif menu.get_title() == DEVICE_MENU:
            for mi in menu.menu_items:
                if mi.name == DEVICE_SCAN_MI:
                    # Activate if bus hardware is open
                    mi.is_active = len(ctx.open_bus_hardware_ids) > 0
                elif mi.name == DEVICE_CONNECT_MENU:
                    # Activate if devices are available after scan
                    mi.is_active = len(ctx.connectable_device_ids) > 0 and len(ctx.open_bus_hardware_ids) > 0
                elif mi.name == DEVICE_DISCONNECT_MENU:
                    # Activate if device is connected
                    mi.is_active = len(ctx.connected_device_handles) > 0
                elif mi.name == DEVICE_SELECT_ACTIVE_MENU:
                    # Activate if device is connected
                    mi.is_active = len(ctx.connected_device_handles) > 0 and len(ctx.open_bus_hardware_ids) > 0
                elif mi.name in {DEVICE_INFORMATION_MENU, DEVICE_REBOOT_MI, DEVICE_UPDATE_FW_MI,
                                DEVICE_UPDATE_BL_MI, DEVICE_UPLOAD_NANOJ_MI, DEVICE_RUN_NANOJ_MI,
                                DEVICE_STOP_NANOJ_MI, DEVICE_GET_ERROR_FIELD_MI, DEVICE_RESTORE_ALL_DEFAULT_PARAMS_MI}:
                    # Activate if active device is set
                    mi.is_active = ctx.active_device != None
                else:
                    # Do nothing
                    pass

        elif menu.get_title() in {DEVICE_INFORMATION_MENU, OD_INTERFACE_MENU, SAMPLER_EXAMPLE_MENU, MOTOR_EXAMPLE_MENU}:
            for mi in menu.menu_items:
                # Activate all menu entries if active device is selected
                mi.is_active = ctx.active_device != None

        elif menu.get_title() in {LOG_LEVEL_MENU, LOGGING_MENU, LOG_CALLBACK_MENU}:
            for mi in menu.menu_items:
                # Always active
                mi.is_active = True

        elif menu.get_title() == BUS_HARDWARE_OPEN_MI:
            # Dynamic menu
            menu.erase_all_menu_items()
            openable_bus_hardware_ids: list[Nanolib.BusHardwareId] = Menu.get_openable_bus_hw_ids(ctx)

            # Re-build menu items depending on found bus hardware
            for openable_bus_hw_id in openable_bus_hardware_ids:
                mi = Menu.MenuItem(f"{openable_bus_hw_id.getProtocol()} ({openable_bus_hw_id.getName()})", menu.get_default_function(), True)
                menu.append_menu_item(mi)

        elif menu.get_title() == BUS_HARDWARE_CLOSE_MI:
            # Dynamic menu
            menu.erase_all_menu_items()
            open_bus_hw_ids: list[Nanolib.BusHardwareId] = ctx.open_bus_hardware_ids

            for open_bus_hw_id in open_bus_hw_ids:
                mi = Menu.MenuItem(f"{open_bus_hw_id.getProtocol()} ({open_bus_hw_id.getBusHardware()})", menu.get_default_function(), True)
                menu.append_menu_item(mi)

        elif menu.get_title() == DEVICE_CONNECT_MENU:
            # Dynamic menu
            menu.erase_all_menu_items()
            connectable_device_ids: list[Nanolib.DeviceId] = Menu.get_connectable_device_ids(ctx)

            for connectable_device_id in connectable_device_ids:
                bus_hardware_id: Nanolib.BusHardwareId = connectable_device_id.getBusHardwareId()
                mi = Menu.MenuItem(f"{connectable_device_id.getDescription()} [id: {connectable_device_id.getDeviceId()}, protocol: {bus_hardware_id.getProtocol()}, hw: {bus_hardware_id.getName()}]", menu.get_default_function(), True)
                menu.append_menu_item(mi)

        elif menu.get_title() == DEVICE_DISCONNECT_MENU:
            # Dynamic menu
            menu.erase_all_menu_items()
            open_device_ids: list[Nanolib.DeviceId] = []

            for open_device_handle in ctx.connected_device_handles:
                open_device_id_result: Nanolib.ResultDeviceId = ctx.nanolib_accessor.getDeviceId(open_device_handle)
                if not open_device_id_result.hasError():
                    open_device_ids.append(open_device_id_result.getResult())

            for device_id in open_device_ids:
                bus_hardware_id: Nanolib.BusHardwareId = device_id.getBusHardwareId()
                mi = Menu.MenuItem(f"{device_id.getDescription()} [id: {device_id.getDeviceId()}, protocol: {bus_hardware_id.getProtocol()}, hw: {bus_hardware_id.getName()}]", menu.get_default_function(), True)
                menu.append_menu_item(mi)

        elif menu.get_title() == DEVICE_SELECT_ACTIVE_MENU:
            # Dynamic menu
            menu.erase_all_menu_items()

            for connected_device_handle in ctx.connected_device_handles:
                device_id_result: Nanolib.ResultDeviceId = ctx.nanolib_accessor.getDeviceId(connected_device_handle)
                if not device_id_result.hasError():
                    device_id: Nanolib.DeviceId = device_id_result.getResult()
                    bus_hardware_id: Nanolib.BusHardwareId = device_id.getBusHardwareId()
                    mi = Menu.MenuItem(f"{device_id.getDescription()} [id: {device_id.getDeviceId()}, protocol: {bus_hardware_id.getProtocol()}, hw: {bus_hardware_id.getName()}]", menu.get_default_function(), True)
                    menu.append_menu_item(mi)

        else:
            # Do nothing
            pass


    @staticmethod
    def get_active_device_string(ctx: 'Context'):
        """Build the active device string for print_info

        :param ctx: The menu context
        :return: a string of the active device
        """
        result = f"Active device    : {ctx.dark_gray}None{ctx.def_color}\n"

        if ctx.active_device == None:
            return result
        
        active_device_result: Nanolib.ResultDeviceId = ctx.nanolib_accessor.getDeviceId(ctx.active_device)
        active_device: Nanolib.DeviceId = active_device_result.getResult()
        bus_hardware_id: Nanolib.BusHardwareId = active_device.getBusHardwareId()
        return (f"Active device    : {ctx.light_green}{active_device.getDescription()} [id: {active_device.getDeviceId()}, "
                f"protocol: {bus_hardware_id.getProtocol()}, "
                f"hw: {bus_hardware_id.getName()}]{ctx.def_color}\n")

    def get_found_bus_hw_string(self, ctx: 'Context'):
        """ Build the number of found bus hardware for print_info

        :param ctx: The menu context
        :return: the number as string for the found bushardware
        """
        result = f"Bus HW found     : {ctx.dark_gray}None (not scanned?){ctx.def_color}\n"
        
        if not ctx.scanned_bus_hardware_ids:
            return result
        
        return f"Bus HW found     : {ctx.light_green}{len(ctx.scanned_bus_hardware_ids)}{ctx.def_color}\n"

    def get_opened_bus_hw_id_string(self, ctx: 'Context'):
        """ Build the opened bus hardware string for print_info

        :param ctx: The menu context
        :return: a string of opened bus hardware
        """
        result = f"Open Bus HW      : {ctx.dark_gray}None{ctx.def_color}\n"

        if not ctx.open_bus_hardware_ids:
            return result

        opened_hw_list = [f"{ctx.light_green}{hw.getProtocol()} ({hw.getName()}){ctx.def_color}"
                          for hw in ctx.open_bus_hardware_ids]
        
        return f"Open Bus HW      : {', '.join(opened_hw_list)}\n"

    def get_scanned_device_ids_string(self, ctx: 'Context'):
        """ Build the number of found devices print_info

        :param ctx: The menu context
        :return: a string of the found devices
        """
        result = f"Device(s) found  : {ctx.dark_gray}None (not scanned?){ctx.def_color}\n"
        
        if not ctx.scanned_device_ids:
            return result
        
        return f"Device(s) found  : {ctx.light_green}{len(ctx.scanned_device_ids)}{ctx.def_color}\n"

    def get_connected_devices_string(self, ctx: 'Context'):
        """ Build the connected device(s) string for print_info

        :param ctx: The menu context
        :return: a string of the connected device(s)
        """
        result = f"Connected devices: {ctx.dark_gray}None{ctx.def_color}\n"

        if not ctx.connected_device_handles:
            return result

        connected_devices = []
        for handle in ctx.connected_device_handles:
            result_device_id: Nanolib.ResultDeviceId = ctx.nanolib_accessor.getDeviceId(handle)
            if result_device_id.hasError():
                continue
            connected_device_id: Nanolib.DeviceId = result_device_id.getResult()
            bus_hardware_id: Nanolib.BusHardwareId = connected_device_id.getBusHardwareId()
            connected_devices.append(
                f"{ctx.light_green}{connected_device_id.getDescription()} [id: {connected_device_id.getDeviceId()}, "
                f"protocol: {bus_hardware_id.getProtocol()}, "
                f"hw: {bus_hardware_id.getName()}]{ctx.def_color}"
            )

        return f"Connected devices: {', '.join(connected_devices)}\n"

    def get_callback_logging_string(self, ctx: 'Context'):
        """ Build the callback logging string for print_info

        :param ctx: The menu context
        :return: a string of currently used log module for logging callback
        """
        if not ctx.logging_callback_active:
            return "Callback Logging : Off\n"
        
        return (f"Callback Logging : {ctx.light_green}On{ctx.def_color} "
                f"({Nanolib.LogModuleConverter.toString(ctx.current_log_module)})\n")

    def get_object_dictionary_string(self, ctx: 'Context'):
        """ Build the object dictionary string for print_info

        :param ctx: The menu context
        :return: a string current assigned object dictionary
        """
        result = f"Object dictionary: {ctx.dark_gray}Fallback (not assigned){ctx.def_color}\n"

        if ctx.active_device == None:
            return result

        result_object_dictionary: Nanolib.ResultObjectDictionary = ctx.nanolib_accessor.getAssignedObjectDictionary(ctx.active_device)
        if result_object_dictionary.hasError():
            return result

        object_dictionary: Nanolib.ObjectDictionary = result_object_dictionary.getResult()
        result_string: Nanolib.ResultString = object_dictionary.getXmlFileName()
        if not result_string.getResult():
            return result

        return f"Object dictionary: {ctx.light_green}Assigned{ctx.def_color}\n"

    def print_info(self, ctx: 'Context'):
        """ Prints basic information for the user

        :param ctx: The menu context
        :return: the complete string for output
        """
        # Clear screen, return value not needed
        import os
        os.system('CLS' if os.name == 'nt' else 'clear')
        
        result = []
        result.append(self.get_active_device_string(ctx))
        result.append(self.get_found_bus_hw_string(ctx))
        result.append(self.get_opened_bus_hw_id_string(ctx))
        result.append(self.get_scanned_device_ids_string(ctx))
        result.append(self.get_connected_devices_string(ctx))
        result.append(self.get_callback_logging_string(ctx))
        result.append(self.get_object_dictionary_string(ctx))
        result.append(f"Log level        : {Nanolib.LogLevelConverter.toString(ctx.current_log_level)}\n")
        result.append(ctx.error_text)

        # Clear text
        ctx.error_text = ""
        
        return ''.join(result)

    def show_menu(self, ctx: 'Context'):
        """ Display the menu, wait and get user input

        :param ctx: The menu context
        :return: the user selected option
        """
        # Dynamic part (for some menus)
        self.set_menu_items(self, ctx)

        # Static part
        output = []
        number_of_menu_items = len(self.menu_items)

        # If true, stop at the end of execution of the selected option
        # until return is pressed by the user
        if ctx.wait_for_user_confirmation:
            input("Press enter to continue!")

        ctx.wait_for_user_confirmation = False

        # Create the user information part
        output.append(self.print_info(ctx))

        # Create the menu header
        output.append("---------------------------------------------------------------------------")
        output.append(f" {self.get_title()}")
        output.append("---------------------------------------------------------------------------")

        # Create the menu items (options)
        for i in range(1, number_of_menu_items + 1):
            item = self.menu_items[i - 1]
            if item.is_active:
                output.append(f"{ctx.def_color}{( ' ' if number_of_menu_items > 9 and i < 10 else '')}{i}) {item.name}")
            else:
                output.append(f"{ctx.dark_gray}{( ' ' if number_of_menu_items > 9 and i < 10 else '')}{i}) {item.name}{ctx.def_color}")

        # Create back (sub-menu) or exit option (main menu)
        if self.get_title() == MAIN_MENU:
            output.append(f"\n{( ' ' if number_of_menu_items > 9 else '')}0) Exit program\n\nEnter menu option number")
        else:
            output.append(f"\n{( ' ' if number_of_menu_items > 9 else '')}0) Back\n\nEnter menu option number")

        # Bring created output to screen and wait for user input
        return get_num("\n".join(output), 0, number_of_menu_items)

    @staticmethod
    def clear_screen():
        """ Helper function to clear the console screen"""
        os.system("cls" if os.name == "nt" else "clear")

    def run(menu, ctx: 'Context'):
        """ Executes the selected menu option

        :param menu: The current menu
        :param ctx: The menu context
        """
        # Clear screen, result not needed
        Menu.clear_screen()

        ctx.wait_for_user_confirmation = False
        while True:
            opt = menu.show_menu(ctx)

            if opt == 0:
                return
            elif opt == sys.maxsize or not menu.menu_items[opt - 1].is_active:
                ctx.error_text = f"{ctx.light_yellow}Invalid option{ctx.def_color}"
            else:
                ctx.error_text = ""

                # Store selected option to context
                ctx.selected_option = opt

                mi = menu.menu_items[opt - 1]
                if callable(mi.func):
                    mi.func(ctx)
                else:
                    mi.func.run(ctx)

