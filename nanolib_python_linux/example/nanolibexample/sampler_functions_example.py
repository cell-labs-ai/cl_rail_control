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
# @file   sampler_functions_example.py
#
# @brief  Definition of sampler specific functions
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

from nanotec_nanolib import *
from menu_utils import *
from sampler_example import *

def execute_sampler_without_notification_normal_mode(ctx: 'Context'):
    """Execute the sampler example in normal mode without notification callback.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print("In normal mode the number of samples can be configured.")
    print("In this example the sampler will run for 5 samples.")

    sampler_example = SamplerExample(ctx)
    sampler_example.process_sampler_without_notification_normal()

    print("Finished")

def execute_sampler_without_notification_repetitive_mode(ctx: 'Context'):
    """Execute the sampler example in repetitive mode without notification callback.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print("In repetitive mode the sampler runs until stopped.")
    print("In this example the sampler will run for 4 iterations and then stop.")

    sampler_example = SamplerExample(ctx)
    sampler_example.process_sampler_without_notification_repetitive()

    print("Finished")

def execute_sampler_without_notification_continuous_mode(ctx: 'Context'):
    """Execute the sampler example in continuous mode without notification callback.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print("In continuous mode the sampler runs until stopped.")
    print("In this example the sampler will run for 10 samples and then stop.")

    sampler_example = SamplerExample(ctx)
    sampler_example.process_sampler_without_notification_continuous()

    print("Finished")

def execute_sampler_with_notification_normal_mode(ctx: 'Context'):
    """Execute the sampler example in normal mode with notification callback.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print("In normal mode the number of samples can be configured.")
    print("In this example the sampler will run for 5 samples.")

    sampler_example = SamplerExample(ctx)
    sampler_example.process_sampler_with_notification_normal()

    print("Finished")

def execute_sampler_with_notification_repetitive_mode(ctx: 'Context'):
    """Execute the sampler example in repetitive mode with notification callback.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print("In repetitive mode the sampler runs until stopped.")
    print("In this example the sampler will run for 4 iterations and then stop.")

    sampler_example = SamplerExample(ctx)
    sampler_example.process_sampler_with_notification_repetitive()

    print("Finished")

def execute_sampler_with_notification_continuous_mode(ctx: 'Context'):
    """Execute the sampler example in continuous mode with notification callback.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = True

    if ctx.active_device == None:
        handle_error_message(ctx, "No active device set. Select an active device first.")
        return

    print("In continuous mode the sampler runs until stopped.")
    print("In this example the sampler will run for 10 samples and then stop.")

    sampler_example = SamplerExample(ctx)
    sampler_example.process_sampler_with_notification_continuous()

    print("Finished")