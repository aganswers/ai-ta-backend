#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

REPO_DIR="/home/ubuntu/backend"
BACKUP_DIR="/home/ubuntu/backend_backups"
SERVICE_NAME="flask-backend"
VENV_PATH="/home/ubuntu/pyenvs/backend"

echo -e "${GREEN}Starting deployment process...${NC}"

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Cleanup old backups (older than 7 days)
echo -e "${YELLOW}Cleaning up old backups...${NC}"
find "$BACKUP_DIR" -type f -mtime +7 -delete 2>/dev/null || true

# Store current commit hash before pulling
CURRENT_COMMIT=$(git -C "$REPO_DIR" rev-parse HEAD)
echo "Current commit: $CURRENT_COMMIT"

# Fetch latest changes
echo -e "${YELLOW}Fetching latest changes from origin/main...${NC}"
cd "$REPO_DIR"
git fetch origin main

# Check if there are new commits
LATEST_COMMIT=$(git rev-parse origin/main)
if [ "$CURRENT_COMMIT" = "$LATEST_COMMIT" ]; then
    echo -e "${GREEN}Already up to date. No deployment needed.${NC}"
    exit 0
fi

echo -e "${YELLOW}New commits detected. Starting update process...${NC}"

# Save current working commit to backup file
echo "$CURRENT_COMMIT" > "$BACKUP_DIR/last_working_commit.txt"

# Pull latest changes
echo -e "${YELLOW}Pulling latest changes...${NC}"
git pull origin main

# Install/update dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt --quiet

# Run linting checks
echo -e "${YELLOW}Running linting checks...${NC}"
if ! python -m flake8 ai_ta_backend --count --select=E9,F63,F7,F82 --show-source --statistics; then
    echo -e "${RED}Linting failed! Rolling back...${NC}"
    git reset --hard "$CURRENT_COMMIT"
    pip install -r requirements.txt --quiet
    exit 1
fi

# Test Flask startup
echo -e "${YELLOW}Testing Flask application startup...${NC}"
timeout 30s flask --app ai_ta_backend.main:app run --port 8001 > /tmp/flask_test.log 2>&1 &
FLASK_PID=$!

# Wait for Flask to start
FLASK_STARTED=false
for i in {1..20}; do
    if curl -s http://localhost:8001/ > /dev/null 2>&1; then
        echo -e "${GREEN}Flask test startup successful!${NC}"
        FLASK_STARTED=true
        kill $FLASK_PID 2>/dev/null || true
        break
    fi
    sleep 1
done

if [ "$FLASK_STARTED" = false ]; then
    echo -e "${RED}Flask failed to start! Rolling back...${NC}"
    cat /tmp/flask_test.log
    kill $FLASK_PID 2>/dev/null || true
    git reset --hard "$CURRENT_COMMIT"
    pip install -r requirements.txt --quiet
    exit 1
fi

# Restart the production service
echo -e "${YELLOW}Restarting production service...${NC}"
sudo systemctl restart "$SERVICE_NAME"

# Wait for service to start
sleep 3

# Check if service is running
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}✓ Deployment successful! Service is running.${NC}"
    echo "Deployed commit: $LATEST_COMMIT"
    # Update last working commit
    echo "$LATEST_COMMIT" > "$BACKUP_DIR/last_working_commit.txt"
    exit 0
else
    echo -e "${RED}✗ Service failed to start! Rolling back...${NC}"
    git reset --hard "$CURRENT_COMMIT"
    pip install -r requirements.txt --quiet
    sudo systemctl restart "$SERVICE_NAME"
    exit 1
fi

