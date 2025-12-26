#!/bin/bash
# =============================================================================
# Resync v5.9.3 - Linux VM Setup Script
# =============================================================================
# Supported: Ubuntu 20.04+, Debian 11+
# Usage: sudo ./setup_linux.sh
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Starting Resync Environment Setup...${NC}"

# 1. System Updates & Dependencies
echo "Updating system packages..."
apt-get update
# Install Python 3.10+ and build essentials
apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip build-essential libpq-dev git redis-server curl

# 2. Redis Setup
echo "Configuring Redis..."
systemctl enable redis-server
systemctl start redis-server
if systemctl is-active --quiet redis-server; then
    echo -e "${GREEN}Redis is running.${NC}"
else
    echo -e "${RED}Redis failed to start.${NC}"
fi

# 3. Application Directory Setup
APP_DIR="/opt/resync"
# Assuming script is run from inside the repo or we copy files to /opt/resync
# For this script, we assume we are running IN the project root.

# 4. Virtual Environment
echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3.10 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip

# 5. Install Python Dependencies
echo "Installing Python dependencies (this may take a while)..."
pip install -r requirements.txt

# 6. Configuration Check
if [ ! -f ".env" ]; then
    echo -e "${RED}WARNING: .env file not found!${NC}"
    echo "Copying production template..."
    cp production.env.example .env
    chmod 600 .env
    echo -e "${GREEN}Created .env from template. PLEASE EDIT IT NOW.${NC}"
else
    echo -e "${GREEN}.env file found.${NC}"
fi

# 7. Systemd Service Setup
echo "Installing Systemd service..."
# We assume resync.service is in scripts/ directory relative to this script
if [ -f "scripts/resync.service" ]; then
    cp scripts/resync.service /etc/systemd/system/
    systemctl daemon-reload
    # Don't enable automatically to allow config validation first
    echo "Service registered but NOT started. Run 'systemctl start resync' after configuration."
else
    echo -e "${RED}resync.service file not found in scripts/ directory.${NC}"
fi

echo -e "${GREEN}Setup Complete!${NC}"
echo "Next steps:"
echo "1. Edit .env with your production secrets"
echo "2. Run 'alembic upgrade head' to setup database"
echo "3. Start service: 'systemctl start resync'"
echo "4. Check status: 'systemctl status resync'"
