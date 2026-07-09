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
# @file   scan_bus_callback_example.py
#
# @brief  Definition of scan bus callback class
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

from enum import Enum
from nanotec_nanolib import Nanolib

class ScanBusCallbackExample(Nanolib.NlcScanBusCallback):
    """ Implementation class of Nanolib.NlcScanBusCallback, handles scan bus callback"""
    def callback(self, info, devices_found, data):
        """
        Handle bus scan callback.

        :param info: The information about the scan (start, progress, finished)
        :param devices_found: List of devices found (not used in this example)
        :param data: Progress data
        """
        if info == Nanolib.BusScanInfo_Start:
            print("Scan started.")
        
        elif info == Nanolib.BusScanInfo_Progress:
            if (data & 1) == 0:  # data holds scan progress
                print(".", end="", flush=True)
        
        elif info == Nanolib.BusScanInfo_Finished:
            print("\nScan finished.")

        return Nanolib.ResultVoid()