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
# @file   logging_callback_example.py
#
# @brief  Definition of logging callback class
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

import time
from nanotec_nanolib import Nanolib

class LoggingCallbackExample(Nanolib.NlcLoggingCallback):
    """ Implementation class of Nanolib.NlcLoggingCallback, handles logging callback"""
    def __del__(self):
        nanolib_accessor: Nanolib.NanoLibAccessor = Nanolib.getNanoLibAccessor()
        nanolib_accessor.unsetLoggingCallback()

    def callback(self, payload_str, formatted_str, logger_name, log_level, time_since_epoch, thread_id):
        """
        Called whenever a log output is made.

        :param payload_str: The complete logging string
        :param formatted_str: The formatted logging string
        :param logger_name: Name of the logger
        :param log_level: Log level
        :param time_since_epoch: Timestamp in ms (since epoch)
        :param thread_id: Thread id of logging call
        """
        formatted_string = formatted_str
        # Truncate formatted string at the line ending
        if "\r\n" in formatted_string:
            formatted_string = formatted_string.split("\r\n", 1)[0]
        else:
            formatted_string = formatted_string.split("\n", 1)[0]

        # Print log information
        print("----------------------------------------------------------------------------------")
        print(f"| Payload = '{payload_str}'")
        print(f"| Formatted string = '{formatted_string}'")
        print(f"| Logger name = '{logger_name}'")
        print(f"| nlc_log_level = '{Nanolib.LogLevelConverter.toString(log_level)}'")
        print(f"| Local Time = '{self.time_since_epoch_to_localtime_string(time_since_epoch)}'")
        print(f"| Thread id = '{thread_id}'")
        print("----------------------------------------------------------------------------------")

    def time_since_epoch_to_localtime_string(self, time_since_epoch_in_ms):
        """
        Convert time since epoch to local time string.

        :param time_since_epoch_in_ms: Time since epoch in milliseconds
        :return: Local time as string
        """
        # Convert milliseconds to seconds
        seconds_since_epoch = time_since_epoch_in_ms / 1000.0
        local_time = time.localtime(seconds_since_epoch)
        fractional_seconds = time_since_epoch_in_ms % 1000

        return time.strftime("%d-%m-%Y %H:%M:%S", local_time) + f":{fractional_seconds}"