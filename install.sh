#!/bin/bash

# install pip, venv, and wheel
sudo apt update
sudo apt install -y python3-pip python3-venv python3-wheel

# give rights to python binary
sudo setcap 'cap_net_admin,cap_net_raw,cap_sys_nice+eip' $(readlink -f "$(command -v python)")

# create a virtual environment
python3 -m venv .venv

# activate the virtual environment
source .venv/bin/activate

# install nanolib
pip install nanolib_python_linux/nanotec_nanolib_linux_arm64-1.4.0-py3-none-linux_aarch64.whl

# deactivate the virtual environment
deactivate

# print success message
echo "Installation complete. To activate the virtual environment, run 'source .venv/bin/activate'."


