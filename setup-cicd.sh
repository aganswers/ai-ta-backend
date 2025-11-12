#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Flask Backend CI/CD Setup Script    ${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run as root. Run as ubuntu user.${NC}"
   exit 1
fi

REPO_DIR="/home/ubuntu/backend"
VENV_PATH="/home/ubuntu/pyenvs/backend"
SERVICE_NAME="flask-backend"

# Step 1: Verify virtual environment exists
echo -e "${YELLOW}[1/6] Checking virtual environment...${NC}"
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    mkdir -p /home/ubuntu/pyenvs
    python3 -m venv "$VENV_PATH"
fi
echo -e "${GREEN}✓ Virtual environment ready${NC}\n"

# Step 2: Activate venv and install dependencies
echo -e "${YELLOW}[2/6] Installing dependencies...${NC}"
cd "$REPO_DIR"
"$VENV_PATH/bin/pip" install --upgrade pip --quiet
"$VENV_PATH/bin/pip" install -r requirements.txt --quiet
"$VENV_PATH/bin/pip" install flake8 pylint black --quiet
echo -e "${GREEN}✓ Dependencies installed${NC}\n"

# Step 3: Make deploy script executable
echo -e "${YELLOW}[3/6] Setting up deployment script...${NC}"
chmod +x "$REPO_DIR/deploy.sh"
echo -e "${GREEN}✓ Deploy script ready${NC}\n"

# Step 4: Install systemd service
echo -e "${YELLOW}[4/6] Installing systemd service...${NC}"
sudo cp "$REPO_DIR/flask-backend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo -e "${GREEN}✓ Systemd service installed and enabled${NC}\n"

# Step 5: Start the service
echo -e "${YELLOW}[5/6] Starting Flask service...${NC}"
sudo systemctl restart "$SERVICE_NAME"
sleep 3

# Check if service is running
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}✓ Service is running${NC}\n"
else
    echo -e "${RED}✗ Service failed to start. Check logs with: sudo journalctl -u $SERVICE_NAME -n 50${NC}\n"
    exit 1
fi

# Step 6: Setup SSH key for GitHub Actions (if not exists)
echo -e "${YELLOW}[6/6] Checking SSH setup...${NC}"
if [ ! -f ~/.ssh/id_rsa ]; then
    echo -e "${YELLOW}No SSH key found. Generating one...${NC}"
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -C "github-actions-deploy"
    echo -e "${GREEN}✓ SSH key generated${NC}"
else
    echo -e "${GREEN}✓ SSH key already exists${NC}"
fi

# Display public key
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}\n"
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "1. Add the following SSH public key to ~/.ssh/authorized_keys if not already present:"
echo -e "${BLUE}$(cat ~/.ssh/id_rsa.pub)${NC}\n"
echo -e "2. Add the following secrets to your GitHub repository:"
echo -e "   ${YELLOW}EC2_HOST${NC}: Your EC2 public IP or hostname"
echo -e "   ${YELLOW}EC2_USER${NC}: ubuntu"
echo -e "   ${YELLOW}EC2_SSH_KEY${NC}: Contents of ~/.ssh/id_rsa (private key)"
echo -e "\n3. Add all environment variables as GitHub secrets (see list in .github/workflows/ci-cd.yml)\n"
echo -e "4. Test the service:"
echo -e "   ${BLUE}curl http://localhost:8001/${NC}\n"
echo -e "5. View service logs:"
echo -e "   ${BLUE}sudo journalctl -u $SERVICE_NAME -f${NC}"
echo -e "   ${BLUE}tail -f $REPO_DIR/output.log${NC}\n"
echo -e "${BLUE}========================================${NC}"

