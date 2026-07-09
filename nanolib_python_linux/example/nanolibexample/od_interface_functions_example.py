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
# @file   od_interface_functions_example.py
#
# @brief  Definition of object dictionary interface specific functions
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

import os.path
from menu_utils import *

def read_number(ctx: 'Context'):
    """Read a number (no interpretation of the data possible).
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print(f"Reading mode of operation ({OdIndex.odModeOfOperation.toString()}) ...")
    result_int = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odModeOfOperation)
    if result_int.hasError():
        handle_error_message(ctx, "Error during read_number: ", result_int.getError())
        return
    print(f"{OdIndex.odModeOfOperation.toString()} = {result_int.getResult()}")
    print("This is only the raw value. The OD value might be signed or unsigned up to a total length of 4 bytes\n")

    print(f"Reading SI unit position ({OdIndex.odSIUnitPosition.toString()}) ...")
    result_int = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odSIUnitPosition)
    if result_int.hasError():
        handle_error_message(ctx, "Error during read_number: ", result_int.getError())
        return
    print(f"{OdIndex.odSIUnitPosition.toString()} = {result_int.getResult()}")
    print("This is only the raw value. The OD value might be signed or unsigned up to a total length of 4 bytes")

def read_string(ctx: 'Context'):
    """Read a string (string might be zero).
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print(f"Reading Nanotec home page string ({OdIndex.odHomePage.toString()}) ...")
    result_string = ctx.nanolib_accessor.readString(ctx.active_device, OdIndex.odHomePage)
    if result_string.hasError():
        handle_error_message(ctx, "Error during read_string: ", result_string.getError())
        return
    print(f"{OdIndex.odHomePage.toString()} = '{result_string.getResult()}'")

def read_array(ctx: 'Context'):
    """Read an array (no interpretation of the data possible).
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print("Reading device error stack (0x1003) ...")
    result_array_int = ctx.nanolib_accessor.readNumberArray(ctx.active_device, OdIndex.odErrorStackIndex)
    if result_array_int.hasError():
        handle_error_message(ctx, "Error during read_array: ", result_array_int.getError())
        return

    error_stack = result_array_int.getResult()
    print(f"The error stack has {len(error_stack)} elements")
    print(f"The first element (error count) is: {error_stack[0]}")

def write_number(ctx: 'Context'):
    """Write a number with a certain length.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print(f"Writing motor stop command to control word ({OdIndex.odControlWord.toString()} = 0x06) ...")
    result_void = ctx.nanolib_accessor.writeNumber(ctx.active_device, 6, OdIndex.odControlWord, 16)
    if result_void.hasError():
        handle_error_message(ctx, "Error during write_number: ", result_void.getError())

def assign_object_dictionary(ctx: 'Context'):
    """Assign a valid object dictionary to the current active device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    prompt = []
    prompt.append("Please enter the directory (path) where the od.xml is located: ")

    input_path = None
    while input_path is None:
        input_path = get_string_with_prompt(''.join(prompt))

    result_object_dictionary = ctx.nanolib_accessor.autoAssignObjectDictionary(ctx.active_device, input_path)
    if result_object_dictionary.hasError():
        handle_error_message(ctx, "Error during assign_object_dictionary: ", result_object_dictionary.getError())

def read_number_via_dictionary_interface(ctx: 'Context'):
    """Read a number (with interpretation of the data).
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_object_dictionary = ctx.nanolib_accessor.getAssignedObjectDictionary(ctx.active_device)
    if result_object_dictionary.hasError():
        handle_error_message(ctx, "Error during read_number_via_dictionary_interface: ", result_object_dictionary.getError())
        return

    if not result_object_dictionary.getResult().getXmlFileName().getResult():
        print(f"{ctx.light_yellow}No valid object dictionary assigned. Using fallback method!{ctx.def_color}")

    object_dictionary = result_object_dictionary.getResult()

    device_handle_result: Nanolib.ResultDeviceHandle = object_dictionary.getDeviceHandle()
    device_handle: Nanolib.DeviceHandle = device_handle_result.getResult()
    if not device_handle.equals(ctx.active_device):
        handle_error_message(ctx, "", "Object dictionary mismatch in read_number_via_dictionary_interface.")
        return

    print(f"Reading mode of operation ({OdIndex.odModeOfOperation.toString()}) ...")
    result_int = object_dictionary.readNumber(OdIndex.odModeOfOperation)
    if result_int.hasError():
        handle_error_message(ctx, "Error during read_number_via_dictionary_interface: ", result_int.getError())
        return
    # OD 0x6060:00 is of type int8_t in C++ but there is only int in plain python, so cast to int
    mode_of_operation = int(result_int.getResult())
    print(f"{OdIndex.odModeOfOperation.toString()} = {mode_of_operation}")

    print("Some object entry properties: ")
    object_entry = object_dictionary.getObjectEntry(OdIndex.odModeOfOperation.getIndex()).getResult()
    object_code_string = {
        Nanolib.ObjectCode_Null: "Null",
        Nanolib.ObjectCode_Deftype: "Deftype",
        Nanolib.ObjectCode_Defstruct: "Defstruct",
        Nanolib.ObjectCode_Var: "Var",
        Nanolib.ObjectCode_Array: "Array",
        Nanolib.ObjectCode_Record: "Record"
        }.get(object_entry.getObjectCode(), str(int(object_entry.getObjectCode())))
    print(f"Object(0x6060).ObjectCode = {object_code_string}")
    print(f"Object(0x6060).DataType = {Nanolib.OdTypesHelper.objectEntryDataTypeToString(object_entry.getDataType())}")

    print("Some ObjectSubEntry properties: ")
    object_sub_entry = object_dictionary.getObject(OdIndex.odModeOfOperation).getResult()
    print(f"OdIndex({OdIndex.odModeOfOperation.toString()}).DataType = {Nanolib.OdTypesHelper.objectEntryDataTypeToString(object_sub_entry.getDataType())}")
    print(f"OdIndex({OdIndex.odModeOfOperation.toString()}).BitLength = {object_sub_entry.getBitLength()}")
    print("")

    print(f"Reading SI unit position ({OdIndex.odSIUnitPosition.toString()}) ...")
    result_int = object_dictionary.readNumber(OdIndex.odSIUnitPosition)
    if result_int.hasError():
        handle_error_message(ctx, "Error during read_number_via_dictionary_interface: ", result_int.getError())
        return
    # OD 0x60A8:00 is of type uint32_t in C++ but there is only int in plain python, so cast to int
    unit_position = int(result_int.getResult())
    print(f"{OdIndex.odSIUnitPosition.toString()} = {unit_position}")

    print("Some object entry properties: ")
    object_entry2 = object_dictionary.getObjectEntry(OdIndex.odSIUnitPosition.getIndex()).getResult()
    object_code_string = {
        Nanolib.ObjectCode_Null: "Null",
        Nanolib.ObjectCode_Deftype: "Deftype",
        Nanolib.ObjectCode_Defstruct: "Defstruct",
        Nanolib.ObjectCode_Var: "Var",
        Nanolib.ObjectCode_Array: "Array",
        Nanolib.ObjectCode_Record: "Record"
        }.get(object_entry2.getObjectCode(), str(int(object_entry2.getObjectCode())))
    print(f"Object(0x60A8).ObjectCode = {object_code_string}")
    print(f"Object(0x60A8).DataType = {Nanolib.OdTypesHelper.objectEntryDataTypeToString(object_entry2.getDataType())}")

    print("Some ObjectSubEntry properties: ")
    object_sub_entry2 = object_dictionary.getObject(OdIndex.odSIUnitPosition).getResult()
    print(f"OdIndex({OdIndex.odSIUnitPosition.toString()}).DataType = {Nanolib.OdTypesHelper.objectEntryDataTypeToString(object_sub_entry2.getDataType())}")
    print(f"OdIndex({OdIndex.odSIUnitPosition.toString()}).BitLength = {object_sub_entry2.getBitLength()}")

def write_number_via_dictionary_interface(ctx: 'Context'):
    """Write a number (no length has to be defined).
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device is None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    result_object_dictionary = ctx.nanolib_accessor.getAssignedObjectDictionary(ctx.active_device)
    if result_object_dictionary.hasError():
        handle_error_message(ctx, "Error during write_number_via_dictionary_interface: ", result_object_dictionary.getError())
        return

    if not result_object_dictionary.getResult().getXmlFileName().getResult():
        print(f"{ctx.light_yellow}No valid object dictionary assigned. Using fallback method!{ctx.def_color}")

    object_dictionary = result_object_dictionary.getResult()

    device_handle_result: Nanolib.ResultDeviceHandle = object_dictionary.getDeviceHandle()
    device_handle: Nanolib.DeviceHandle = device_handle_result.getResult()
    if not device_handle.equals(ctx.active_device):
        handle_error_message(ctx, "", "Object dictionary mismatch in write_number_via_dictionary_interface.")
        return

    print(f"Writing motor stop command to control word ({OdIndex.odControlWord.toString()}) with value 0x06 ...")
    value = 6
    write_result = object_dictionary.writeNumber(OdIndex.odControlWord, value)

    if write_result.hasError():
        handle_error_message(ctx, "Error during write_number_via_dictionary_interface: ", write_result.getError())