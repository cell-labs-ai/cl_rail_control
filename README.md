# Cell Labs

## Rail Control

### Installation

1. Run the install script to set up the environment and install dependencies:
   ```bash
   ./install.sh
   ```
   
   This script will:
   - Install Python 3 dependencies (pip, venv, wheel)
   - Set required capabilities on the Python binary for network operations
   - Create a virtual environment in `.venv`
   - Install the Nanotec Nanolib package

### Running Examples

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


