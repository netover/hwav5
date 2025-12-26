#!/bin/bash
# =============================================================================
# Resync Production Deployment with Self-Healing
# =============================================================================
# Deploys Resync with auto-restart and health monitoring
# =============================================================================

set -e

echo "🚀 Deploying Resync with Self-Healing..."
echo ""

# Configuration
DEPLOY_DIR="/opt/resync"
SERVICE_USER="resync"
API_PORT=8000

# =============================================================================
# Step 1: Install Dependencies
# =============================================================================

echo "📦 Installing system dependencies..."

sudo apt-get update
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    postgresql-client \
    redis-tools \
    curl

echo "✅ System dependencies installed"
echo ""

# =============================================================================
# Step 2: Create Service User
# =============================================================================

echo "👤 Creating service user..."

if ! id "$SERVICE_USER" &>/dev/null; then
    sudo useradd -r -s /bin/bash -d "$DEPLOY_DIR" -m "$SERVICE_USER"
    echo "✅ User $SERVICE_USER created"
else
    echo "✅ User $SERVICE_USER already exists"
fi

echo ""

# =============================================================================
# Step 3: Install UV
# =============================================================================

echo "📦 Installing UV package manager..."

if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✅ UV installed"
else
    echo "✅ UV already installed"
fi

echo ""

# =============================================================================
# Step 4: Deploy Application
# =============================================================================

echo "📂 Deploying application..."

# Copy files
sudo cp -r . "$DEPLOY_DIR/"
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$DEPLOY_DIR"

# Install dependencies
cd "$DEPLOY_DIR"
sudo -u "$SERVICE_USER" uv sync --frozen --no-dev

echo "✅ Application deployed"
echo ""

# =============================================================================
# Step 5: Configure Environment
# =============================================================================

echo "⚙️ Configuring environment..."

# Create .env if not exists
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    cat > "$DEPLOY_DIR/.env" << EOF
# Resync Production Configuration
DATABASE_URL=postgresql://resync:password@localhost/resync
REDIS_URL=redis://localhost:6379
TWS_API_URL=http://tws-server:9443
SECRET_KEY=$(openssl rand -hex 32)
LOG_LEVEL=INFO
EOF
    sudo chown "$SERVICE_USER:$SERVICE_USER" "$DEPLOY_DIR/.env"
    echo "✅ Created .env file (EDIT BEFORE STARTING!)"
else
    echo "✅ .env already exists"
fi

echo ""

# =============================================================================
# Step 6: Install Systemd Services
# =============================================================================

echo "🔧 Installing systemd services..."

# Install Resync API service
sudo cp "$DEPLOY_DIR/deploy/systemd/resync-api.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable resync-api

echo "✅ Resync API service installed"

# Install Self-Healing Monitor service
sudo cp "$DEPLOY_DIR/deploy/systemd/resync-monitor.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable resync-monitor

echo "✅ Self-Healing Monitor service installed"
echo ""

# =============================================================================
# Step 7: Start Services
# =============================================================================

echo "🚀 Starting services..."

# Start API
sudo systemctl start resync-api
sleep 5

# Check API health
if curl -f http://localhost:$API_PORT/health > /dev/null 2>&1; then
    echo "✅ Resync API is healthy"
else
    echo "❌ Resync API failed health check!"
    sudo journalctl -u resync-api -n 50
    exit 1
fi

# Start Monitor
sudo systemctl start resync-monitor
sleep 2

if sudo systemctl is-active --quiet resync-monitor; then
    echo "✅ Self-Healing Monitor is running"
else
    echo "❌ Monitor failed to start!"
    exit 1
fi

echo ""

# =============================================================================
# Step 8: Verify Deployment
# =============================================================================

echo "🔍 Verifying deployment..."
echo ""

echo "Services status:"
sudo systemctl status resync-api --no-pager | head -5
sudo systemctl status resync-monitor --no-pager | head -5

echo ""
echo "Health check:"
curl http://localhost:$API_PORT/health | python3 -m json.tool

echo ""

# =============================================================================
# Done!
# =============================================================================

cat << EOF

✅ DEPLOYMENT COMPLETE!

📊 Service URLs:
   API: http://localhost:$API_PORT
   Docs: http://localhost:$API_PORT/docs
   Admin: http://localhost:$API_PORT/admin

🔧 Management Commands:
   View logs:        sudo journalctl -u resync-api -f
   View monitor:     sudo journalctl -u resync-monitor -f
   Restart API:      sudo systemctl restart resync-api
   Restart monitor:  sudo systemctl restart resync-monitor
   Stop all:         sudo systemctl stop resync-api resync-monitor

🏥 Self-Healing Features:
   ✅ Auto-restart on crash
   ✅ Health monitoring (5s interval)
   ✅ Resource monitoring
   ✅ Graceful shutdown
   ✅ Restart rate limiting (5/hour)

⚠️ IMPORTANT:
   1. Edit $DEPLOY_DIR/.env with your configuration
   2. Restart services after editing: sudo systemctl restart resync-api
   3. Monitor is watching - service will auto-restart on crash!

🎉 Resync is now running with Self-Healing protection!

EOF
