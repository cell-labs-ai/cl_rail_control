# Cell Labs

## Rail Control

### Installation

1. Run the install script to set up the environment and install dependencies:
   ```bash
   bash install.sh
   ```
   
   This script will:
   - Install Python 3 dependencies (pip, venv, wheel)
   - Set required capabilities on the Python binary for network operations
   - Create a virtual environment in `.venv`
   - Install the Nanotec Nanolib package

### Running Examples

> ⚠️ **IMPORTANT DISCLAIMER**: Before running any examples, ensure that **no other tools or applications** are connected to the motor controllers. Running examples while other tools are accessing the controllers can cause unexpected behavior or conflicts.

After installation, you can run the example scripts. First, activate the virtual environment:

```bash
source .venv/bin/activate
```

Then run any example script:

```bash
python nanolib_python_linux/example/nanolibexample/example.py
```

Other available examples include:
- `bus_functions_example.py`
- `device_functions_example.py`
- `motor_functions_example.py`
- `profinet_functions_example.py`
- And more in `nanolib_python_linux/example/nanolibexample/`

When finished, deactivate the virtual environment:

```bash
deactivate
```

### Testing the Controllers

`test_controllers.py` is a simple connectivity test. It opens the Modbus TCP (WiFi) bus, discovers the motor controllers, connects to each, reads and prints some data (device info, statusword, position, velocity, torque, error count), then disconnects.

With the virtual environment activated, run it from the repo root:

```bash
python test_controllers.py
```

No IP configuration is needed — the controllers are discovered automatically on the wireless interface. (If auto-discovery fails, the script falls back to the fixed IPs defined near the top of the file.)


