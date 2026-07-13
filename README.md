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

### Web Control UI

`rail_web_ui.py` serves a browser-based control panel for both controllers —
the **cart** on the rail (serial ending `0168`) and the payload **lift**
(serial ending `0173`). It reuses the discovery/connection and readout logic
from `test_controllers.py` / `motion_test.py`; existing scripts are untouched.

Each controller gets a panel with:
- **Parameters** — dropdowns (mode of operation, motion profile type), number
  entries (profile acceleration, jerk) and sliders (jog speed).
- **PID balance loop** — live Kp/Ki/Kd (and setpoint/deadzone/max-speed) tuning
  with a Start/Stop for the software angle-hold loop from `motion_test.py`.
- **Manual drive** — press-and-hold jog buttons (left/right for the cart,
  up/down for the lift) plus a STOP.
- **Live readout** — statusword, position, velocity, torque, analog angle, etc.

The lift reuses the cart's readout unchanged; its up/down motion is templated
(`lift_up` / `lift_down` in `rail_web_ui.py`) with `TODO` markers for the real
travel-limit / brake behaviour to be filled in later.

With the virtual environment activated, run it from the repo root:

```bash
python rail_web_ui.py             # connect to the real controllers
python rail_web_ui.py --simulate  # no hardware; fake state for UI development
python rail_web_ui.py --port 8080 # choose the port (default 8080)
```

Then open `http://<pi-address>:8080/` in a browser on the same network. As with
the other scripts, make sure no other tool is talking to the controllers while
it runs.


