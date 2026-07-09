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
# @file   motor_functions_example.py
#
# @brief  Definition of motor specific functions
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

import time
from nanotec_nanolib import *
from menu_utils import *

def motor_auto_setup(ctx: 'Context'):
    """Determine motor parameters and store them on the device.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "", "No active device set. Select an active device first.")
        return

    print("\n" + ctx.light_yellow)
    print("Please note the following requirements for performing the auto-setup:")
    print("- The motor must be unloaded.")
    print("- The motor must not be touched.")
    print("- The motor must be able to rotate freely in any direction.")
    print("- No NanoJ program may be running." + ctx.def_color)

    result = input("Do you want to continue? [y/n]: ")
    if result.lower() != "y":
        return

    # Stop a possibly running NanoJ program
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x00, OdIndex.odNanoJControl, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during motor_auto_setup: ", write_result.getError())
        return

    # Switch the state machine to "voltage enabled"
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x06, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during motor_auto_setup: ", write_result.getError())
        return

    # Set mode of operation to auto-setup
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0xFE, OdIndex.odModeOfOperation, 8)
    if write_result.hasError():
        handle_error_message(ctx, "Error during motor_auto_setup: ", write_result.getError())
        return

    # Switch on
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x07, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during motor_auto_setup: ", write_result.getError())
        return

    # Switch the state machine to "enable operation"
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x0F, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during motor_auto_setup: ", write_result.getError())
        return

    # Run auto setup
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x1F, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during motor_auto_setup: ", write_result.getError())
        return

    print("Motor auto setup is running, please wait ...")

    # Wait until auto setup is finished, check status word
    while True:
        read_number_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odStatusWord)
        if read_number_result.hasError():
            handle_error_message(ctx, "Error during motor_auto_setup: ", read_number_result.getError())
            return

        # Finish if bits 12, 9, 5, 4, 2, 1, 0 are set
        if (read_number_result.getResult() & 0x1237) == 0x1237:
            break

    # Reboot current active device
    print("Rebooting ...")
    reboot_result: Nanolib.ResultVoid = ctx.nanolib_accessor.rebootDevice(ctx.active_device)
    if reboot_result.hasError():
        handle_error_message(ctx, "Error during motor_auto_setup: ", reboot_result.getError())
        return
    print("Motor auto setup finished.")

def execute_profile_velocity_mode(ctx: 'Context'):
    """Demonstrate how to move a motor in profile velocity mode.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "", "No active device set. Select an active device first.")
        return

    print("This example lets the motor run in Profile Velocity mode ...")

    # Stop a possibly running NanoJ program
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x00, OdIndex.odNanoJControl, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
        return

    # Choose Profile Velocity mode
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x03, OdIndex.odModeOfOperation, 8)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
        return

    # Set the desired speed in rpm (60)
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x3C, OdIndex.odTargetVelocity, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
        return

    # Switch the state machine to "operation enabled"
    for command in [0x06, 0x07, 0x0F]:
        write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, command, OdIndex.odControlWord, 16)
        if write_result.hasError():
            handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
            return

    print("Motor is running clockwise ...")

    # Let the motor run for 3 seconds
    time.sleep(3)

    # Stop the motor
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x06, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
        return

    # Set the desired speed in rpm (60), now counterclockwise
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, -0x3C, OdIndex.odTargetVelocity, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
        return

    # Start the motor
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x0F, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
        return

    print("Motor is running counterclockwise ...")

    # Let the motor run for 3 seconds
    time.sleep(3)

    # Stop the motor
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x06, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_profile_velocity_mode: ", write_result.getError())
        return

def execute_positioning_mode(ctx: 'Context'):
    """Demonstrate how to move a motor in positioning mode.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "", "No active device set. Select an active device first.")
        return

    print("This example lets the motor run in Profile Position mode ...")

    # Stop a possibly running NanoJ program
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x00, OdIndex.odNanoJControl, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    # Choose Profile Position mode
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x01, OdIndex.odModeOfOperation, 8)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    # Set the desired speed in rpm (60)
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x3C, OdIndex.odProfileVelocity, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    # Set the desired target position (36000)
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x8CA0, OdIndex.odTargetPosition, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    # Switch the state machine to "operation enabled"
    for command in [0x06, 0x07, 0x0F]:
        write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, command, OdIndex.odControlWord, 16)
        if write_result.hasError():
            handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
            return

    # Move the motor to the desired target position relatively
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x5F, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    print("Motor is running clockwise until position is reached ...")
    
    while True:
        read_result: Nanolib.ResultInt = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odStatusWord)
        if read_result.hasError():
            handle_error_message(ctx, "Error during execute_positioning_mode: ", read_result.getError())
            # Try to stop the motor
            ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x06, OdIndex.odControlWord, 16)
            break

        if (read_result.getResult() & 0x1400) == 0x1400:
            break

    # Stop the motor
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x06, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    # Set the desired target position (-36000)
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, -0x8CA0, OdIndex.odTargetPosition, 32)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    # State machine operation enabled
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x0F, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    # Move the motor to the desired target position relatively
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x5F, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return

    print("Motor is running counterclockwise until position is reached ...")
    
    while True:
        read_result = ctx.nanolib_accessor.readNumber(ctx.active_device, OdIndex.odStatusWord)
        if read_result.hasError():
            handle_error_message(ctx, "Error during execute_positioning_mode: ", read_result.getError())
            # Try to stop the motor
            ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x06, OdIndex.odControlWord, 16)
            break

        if (read_result.getResult() & 0x1400) == 0x1400:
            break

    # Stop the motor
    write_result: Nanolib.ResultVoid = ctx.nanolib_accessor.writeNumber(ctx.active_device, 0x06, OdIndex.odControlWord, 16)
    if write_result.hasError():
        handle_error_message(ctx, "Error during execute_positioning_mode: ", write_result.getError())
        return