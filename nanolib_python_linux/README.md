# Nanolib

This is the Python version of NanoLib with an example application. <br>
The NanoLib offers an easy to use library to control Nanotec devices.

[www.nanotec.de](https://www.nanotec.de/)

## Example Application
### Overview and Structure
The CLI example application provides a menu interface where the user can execute
the different library functions. The menu offers the user the possibility to <br>
easily and quickly select and execute all functions supported by NanoLib. <br>
The menu entries are context based and will be enabled or disabled, depending on
the state.<br>
To enable all entries you have to:
1. Scan for hardware buses
2. Connect to a found harwdare bus
3. Scan for devices on the opened hardware bus
4. Successfully connect to a found device<br>
 
With this example application it is possible to:<br> 
- do a hardware bus scan
- open a found bus hardware (several hardware buses allowed)
- close an opened bus hardware
- scan for devices on opened hardware bus(es)
- connect to a found device (several devices allowed)
- disconnect from a connected device 
- read device informations
- update the firmware
- update the bootloader
- upload a NanoJ program
- run/stop a NanoJ program
- reboot a device
- set logging and logging callback parameters
- auto tune a motor (may require manual steps before)
- get a motor to rotate
- use the object dicationary interface for reads/writes
- sample data
- scan for Profinet devices
- etc.

The application menu and the supported NanoLib functionality is logically structered into several files:<br>
Files with \*_functions_example.py contain the implementations for the NanoLib interface functions.<br>
Files with \*_callback_example.py contain implementations for the various callbacks (scan, data and logging).<br>
Files with menu\_\*.py contain the menu logic and code.<br>
Example.py is the main program, creating the menu and initializing all used parameters.<br>
Sampler_example.py contains the example implementation for sampler usage.<br>

### Windows
#### Prerequisites
- A python 3.7 up to python 3.12 installation is required. We highly recommend the official version <br>
  from [python.org](https://www.python.org/downloads/windows/).<br>
- We recommend using a virtual environment before installing NanoLib:
1. Open a command prompt (e.g. powershell) and use the following commands to setup a virtual environment:
   ```cmd
   cd <nanolib_directoy>
   python3 -m venv .env
   .\.env\Scripts\Activate.ps1
   ```
   **_Note:_** Depending on the used Python version, the names and location of the activation script may differ.<br>
   In case the setup was successful the CMD is prefixed with `(.env)`.<br>
2. The package 'wheel' is necessary to install NanoLib as a wheel package:
   ```cmd
   pip3 install wheel
   ```
- Install [HMS - Ixxat VCI 4 driver](https://hmsnetworks.blob.core.windows.net/nlw/docs/default-source/products/ixxat/monitored/pc-interface-cards/vci-v4-0-1240-windows-11-10.zip?sfvrsn=2d1dfdd7_69) and connect CAN adapter (optional).
- Install [PEAK device driver and PCAN API](https://www.peak-system.com/quick/DrvSetup) and connect CAN adapter (optional).
- Connect all devices to your adapter(s) according to the user manual and power on the devices.

#### Installing the NanoLib Wheel 
To install the Nanolib wheel open a command prompt and change to the<br>
directory where the nanolib_python_win_N.N.N.zip file is located and<br> 
extract the archive in a directory of your choice. Then change into to this<br>
directory and locate the wheel file (.whl).<br>
Use the following command to install the Nanolib into your python (virtual) environment:   
```cmd
pip3 install <directory_of_choice>\python_win\nanotec_nanolib_win-N.N.N-py3-none-win_amd64.whl
 ```
Wait for the console to produce a success report ending on "Successfully installed nanotec-nanolib-win-N.N.N".<br>
**_Note:_** Where `N.N.N` is the actual version of the NanoLib. <br>
- To check if the installation has worked open up a python shell by executing Python:
```cmd
python3
```
- Inside the python shell import the NanoLib and press Enter:
```python
import nanotec_nanolib
```
If no error shows, the installation was successful.<br>
You can now leave Python by typing exit() and press Enter.<br>

#### Running the example project
To run the example application open a command prompt and change <br>
to the directory where the NanoLib achrive has been extracted to and change <br>
into the example directory (example/nanolibexample).<br> 
Use the following command to start the example application:
```cmd
python3 example.py
```

### Linux
#### Prerequisites
- A python 3.7 up to python 3.12 installation is required. We highly recommend the official version <br>
  from [python.org](https://www.python.org/downloads/).<br>
- We recommend using a virtual environment before installing NanoLib:
1. Open a console prompt (e.g. bash) and use the following commands to setup a virtual environment:
   ```bash
   cd <nanolib_directoy>
   python3 -m venv .env
   source .env/bin/activate
   ```
   **_Note:_** Depending on the used Python version, the names and location of the activation script may differ.<br>
   In case the setup was successful the CMD is prefixed with `(.env)`.<br>
2. The package 'wheel' is necessary to install NanoLib as a wheel package:
   ```bash
   pip3 install wheel
   ```
- Install [HMS Ixxat ECI driver](https://hmsnetworks.blob.core.windows.net/nlw/docs/default-source/products/ixxat/monitored/pc-interface-cards/eci-linux.zip?sfvrsn=19eb48d7_53) and connect CAN adapter (optional).
- Download, build and install [PEAK device driver for linux and PCAN API](https://www.peak-system.com/quick/PCAN-Linux-Driver) and connect CAN adapter (optional).
- Connect all devices to your adapter(s) according to the user manual and power on the devices.

#### Installing the NanoLib Wheel 
To install the Nanolib wheel open a console prompt and change to the<br>
directory where the nanolib_python_linux_[arm64_]N.N.N.tar.gz file is located and<br> 
extract the archive in a directory of your choice. Then change into to this<br>
directory and locate the wheel file (.whl).<br>
Use the following command to install the Nanolib into your python (virtual) environment:   
```bash
pip3 install <directory_of_choice>/python_linux[_arm64]/nanotec_nanolib_linux-N.N.N-py3-none-linux_[x86_64|aarch64].whl
```
Wait for the console to produce a success report ending on "Successfully installed nanotec-nanolib-[x86_64|aarch64]-N.N.N".<br>
**_Note:_** Where `N.N.N` is the actual version of the NanoLib. <br>
- To check if the installation has worked open up a python shell by executing Python:
```bash
python3
```
- Inside the python shell import the NanoLib and press Enter:
```python
import nanotec_nanolib
```
If no error shows, the installation was successful.<br>
You can now leave Python by typing exit() and press Enter.<br>

#### Running the example project
To run the example application open a console prompt and change <br>
to the directory where the NanoLib achrive has been extracted to and change <br>
into the example directory (example/nanolibexample).<br> 
Use the following command to start the example application:
```bash
python3 example.py
```