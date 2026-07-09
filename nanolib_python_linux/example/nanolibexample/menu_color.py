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
# @file   menu_color.py
#
# @brief  Definitions for console output coloring
#
# @date   29-10-2024
#
# @author Michael Milbradt
#

class MenuColor:
    """Enum-like class for all possible escape codes."""
    RESET = 0
    FG_BOLD = 1
    FG_DIM = 2
    FG_UNDERLINED = 4
    FG_BLINK = 5
    FG_REVERSE = 7
    FG_HIDDEN = 8
    FG_RESET_BOLD = 21
    FG_RESET_DIM = 22
    FG_RESET_UNDERLINED = 24
    FG_RESET_BLINK = 25
    FG_RESET_REVERSE = 27
    FG_RESET_HIDDEN = 28
    FG_BLACK = 30
    FG_RED = 31
    FG_GREEN = 32
    FG_YELLOW = 33
    FG_BLUE = 34
    FG_MAGENTA = 35
    FG_CYAN = 36
    FG_LIGHT_GRAY = 37
    FG_DEFAULT = 39
    BG_RED = 41
    BG_GREEN = 42
    BG_YELLOW = 43
    BG_BLUE = 44
    BG_DEFAULT = 49
    FG_DARK_GRAY = 90
    FG_LIGHT_RED = 91
    FG_LIGHT_GREEN = 92
    FG_LIGHT_YELLOW = 93
    FG_LIGHT_BLUE = 94
    FG_LIGHT_MAGENTA = 95
    FG_LIGHT_CYAN = 96
    FG_WHITE = 97

class ColorModifier:
    """Class to colorize output streams."""
    
    def __init__(self, code=MenuColor.RESET):
        """Initialize with an escape code."""
        self.code = code

    def __str__(self):
        """Return the escape sequence as a string."""
        return f"\033[{self.code}m"

    def set_code(self, code):
        """Set escape sequence for ColorModifier."""
        self.code = code

