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
# @file   logging_functions_example.py
#
# @brief  Definition of logging functions
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

from menu_utils import *
from nanotec_nanolib import *

def set_log_level(ctx: 'Context'):
    """Sets the log level to use (spdlog).
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False
    index = ctx.selected_option - 1

    log_levels = {
        0: Nanolib.LogLevel_Trace,
        1: Nanolib.LogLevel_Debug,
        2: Nanolib.LogLevel_Info,
        3: Nanolib.LogLevel_Warning,
        4: Nanolib.LogLevel_Error,
        5: Nanolib.LogLevel_Critical,
        6: Nanolib.LogLevel_Off
    }

    # Default to 'Info' if index is not found
    log_level = log_levels.get(index, 'Info')
    ctx.nanolib_accessor.setLoggingLevel(log_level)
    ctx.current_log_level = log_level

def set_logging_callback(ctx: 'Context'):
    """Sets the logging callback for the selected option.
    
    :param ctx: menu context
    """
    ctx.wait_for_user_confirmation = False
    index = ctx.selected_option

    log_modules = {
        1: Nanolib.LogModule_NanolibCore,
        2: Nanolib.LogModule_NanolibCANopen,
        3: Nanolib.LogModule_NanolibEtherCAT,
        4: Nanolib.LogModule_NanolibModbus,
        5: Nanolib.LogModule_NanolibRest,
        6: Nanolib.LogModule_NanolibUSB
    }

    if index in log_modules:
        log_module = log_modules[index]
        ctx.nanolib_accessor.setLoggingCallback(ctx.logging_callback, log_module)
        ctx.current_log_module = log_module
        ctx.logging_callback_active = True
    else:
        ctx.nanolib_accessor.unsetLoggingCallback()
        ctx.logging_callback_active = False