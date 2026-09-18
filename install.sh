#!/bin/bash
# install.sh - Sets up everything on the Raspberry Pi 5 (Raspberry Pi OS Bookworm).
#
# Run ONCE from the project folder:
#     bash install.sh
# then reboot. After that the logger starts automatically at every boot.
#
# What it does:
#   1. installs system packages
#   2. switches on I2C, SPI and the UART on GPIO 14/15 (and off the serial console)
#   3. adds your user to the groups that may use I2C/SPI/UART
#   4. creates a Python virtual environment (venv) and installs the libraries
#   5. installs and enables the systemd service (auto-start + auto-restart)

set -e   # stop at the first error

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"
CONFIG_TXT="/boot/firmware/config.txt"

echo "== 1/5 system packages"
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev i2c-tools

echo "== 2/5 enable I2C, SPI, UART"
sudo raspi-config nonint do_i2c 0          # 0 means "enable" in raspi-config
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_serial_hw 0    # serial port hardware on ...
sudo raspi-config nonint do_serial_cons 1  # ... but no login console on it
# On the Pi 5 the UART on GPIO 14/15 additionally needs this line:
if ! grep -q "^dtparam=uart0=on" "$CONFIG_TXT"; then
    echo "dtparam=uart0=on" | sudo tee -a "$CONFIG_TXT" > /dev/null
fi

echo "== 3/5 user groups (i2c, spi, dialout, gpio)"
sudo usermod -aG i2c,spi,dialout,gpio "$USER_NAME"

echo "== 4/5 Python virtual environment + libraries"
cd "$PROJECT_DIR"
if [ ! -d venv ]; then
    python3 -m venv venv
fi
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "== 5/5 systemd service"
sed -e "s|__USER__|$USER_NAME|g" -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    weather-balloon.service | sudo tee /etc/systemd/system/weather-balloon.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable weather-balloon.service

echo
echo "Done. Now reboot:   sudo reboot"
echo "After the reboot:   sudo systemctl status weather-balloon"
echo "                    python tools/live_view.py"
