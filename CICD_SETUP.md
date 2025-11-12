# CI/CD Setup Guide

This guide will help you set up continuous integration and deployment for your Flask backend on EC2.

## Overview

The CI/CD pipeline:
- ✅ Runs linting and tests on every push/PR
- ✅ Rejects bad code before it reaches production
- ✅ Auto-deploys to EC2 when tests pass on `main` branch
- ✅ Automatically rolls back to last working commit if deployment fails
- ✅ Cleans up old backups after 7 days
- ✅ Manages Flask app via systemd service

## Quick Start

### 1. Initial EC2 Setup

Run the setup script on your EC2 instance:

```bash
cd /home/ubuntu/backend
chmod +x setup-cicd.sh
./setup-cicd.sh
```

This will:
- Verify/create Python virtual environment
- Install dependencies
- Set up systemd service
- Generate SSH keys for GitHub Actions
- Start the Flask service

### 2. GitHub Repository Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions → New repository secret):

#### SSH Connection Secrets
- `EC2_HOST`: Your EC2 public IP or hostname (e.g., `ec2-xx-xx-xx-xx.compute-1.amazonaws.com`)
- `EC2_USER`: `ubuntu`
- `EC2_SSH_KEY`: Contents of `/home/ubuntu/.ssh/id_rsa` (private key)

#### Application Environment Variables
Add all these secrets from your `.env` file:

```
SUPABASE_URL
SUPABASE_API_KEY
QDRANT_URL
QDRANT_API_KEY
VLADS_OPENAI_KEY
OLLAMA_SERVER_URL
POSTHOG_API_KEY
AGANSWERS_POSTHOG_API_KEY
AGANSWERS_S3_BUCKET_NAME
AGANSWERS_OPENAI_KEY
OPENAI_API_KEY
AGANSWERS_AWS_ACCESS_KEY_ID
AGANSWERS_AWS_SECRET_ACCESS_KEY
AGANSWERS_QDRANT_URL
AGANSWERS_QDRANT_API_KEY
AGANSWERS_QDRANT_COLLECTION_NAME
QDRANT_COLLECTION_NAME
SUPABSE_PLOT_BUCKET_NAME
AGANSWERS_SUPABASE_URL
AGANSWERS_SUPABASE_API_KEY
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_ACCESS_KEY_ID
CLOUDFLARE_SECRET_ACCESS_KEY
CLOUDFLARE_R2_ENDPOINT
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
MINIO_API_URL
BEAM_API_KEY
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
A_OPENAI_API_KEY
A_GOOGLE_API_KEY
A_SEARCH_ENGINE_ID
GOOGLE_API_KEY
GOOGLE_GENAI_USE_VERTEXAI
OPENROUTER_API_KEY
AWS_KEY
AWS_SECRET
S3_BUCKET_NAME
GOOGLE_CLOUD_PROJECT_ID
GOOGLE_APPLICATION_CREDENTIALS
VERTEX_AI_LOCATION
VERTEX_RAG_CORPUS_NAME
VERTEX_EMBEDDING_MODEL
```

### 3. Commit and Push

Commit the CI/CD files to your repository:

```bash
git add .github/workflows/ci-cd.yml deploy.sh flask-backend.service setup-cicd.sh CICD_SETUP.md
git commit -m "Add CI/CD pipeline"
git push origin main
```

## How It Works

### GitHub Actions Workflow

1. **Test Job** (runs on every push/PR):
   - Installs Python dependencies
   - Runs flake8 linting (blocks on critical errors)
   - Checks code formatting with black
   - Tests Flask app startup

2. **Deploy Job** (runs only on `main` branch after tests pass):
   - Copies environment variables to EC2 as `.env` file
   - Triggers deployment script via SSH

### Deployment Script (`deploy.sh`)

The deployment script on EC2:
1. Activates Python virtual environment
2. Cleans up backups older than 7 days
3. Fetches latest changes from GitHub
4. Backs up current commit hash
5. Installs updated dependencies
6. Runs linting checks
7. Tests Flask startup
8. Restarts systemd service
9. Verifies service is running
10. **Rolls back automatically if any step fails**

### Systemd Service

The Flask app runs as a systemd service (`flask-backend.service`):
- Auto-starts on boot
- Auto-restarts on crashes
- Logs to `/home/ubuntu/backend/output.log`

## Useful Commands

### Service Management
```bash
# Check service status
sudo systemctl status flask-backend

# View live logs
sudo journalctl -u flask-backend -f

# Restart service
sudo systemctl restart flask-backend

# Stop service
sudo systemctl stop flask-backend

# Start service
sudo systemctl start flask-backend
```

### Application Logs
```bash
# View output logs
tail -f /home/ubuntu/backend/output.log

# View last 100 lines
tail -n 100 /home/ubuntu/backend/output.log
```

### Manual Deployment
```bash
cd /home/ubuntu/backend
./deploy.sh
```

### Rollback to Previous Commit
```bash
cd /home/ubuntu/backend
LAST_WORKING=$(cat /home/ubuntu/backend_backups/last_working_commit.txt)
git reset --hard $LAST_WORKING
source /home/ubuntu/pyenvs/backend/bin/activate
pip install -r requirements.txt
sudo systemctl restart flask-backend
```

### Check Current Deployment
```bash
cd /home/ubuntu/backend
git log -1 --oneline
```

## Troubleshooting

### Deployment Fails
1. Check GitHub Actions logs in your repository
2. SSH into EC2 and check logs:
   ```bash
   sudo journalctl -u flask-backend -n 50
   tail -n 100 /home/ubuntu/backend/output.log
   ```

### Service Won't Start
1. Check for errors:
   ```bash
   sudo journalctl -u flask-backend -n 50
   ```
2. Test manually:
   ```bash
   cd /home/ubuntu/backend
   source /home/ubuntu/pyenvs/backend/bin/activate
   flask --app ai_ta_backend.main:app run --port 8001
   ```

### GitHub Actions Can't Connect to EC2
1. Verify EC2 security group allows SSH (port 22) from GitHub Actions IPs
2. Verify `EC2_SSH_KEY` secret contains the full private key
3. Test SSH connection manually:
   ```bash
   ssh -i ~/.ssh/deploy_key ubuntu@YOUR_EC2_HOST
   ```

### Environment Variables Not Working
1. Verify all secrets are added to GitHub
2. Check `.env` file on EC2:
   ```bash
   cat /home/ubuntu/backend/.env
   ```
3. Ensure systemd service has `EnvironmentFile=/home/ubuntu/backend/.env`

## Security Notes

- Never commit `.env` file to git
- Keep GitHub secrets secure
- Rotate SSH keys periodically
- Review EC2 security group rules
- Keep dependencies updated

## Testing the Pipeline

1. Make a small change to your code
2. Commit and push to a feature branch
3. Create a pull request
4. GitHub Actions will run tests
5. If tests pass, merge to `main`
6. Deployment will trigger automatically
7. Check EC2 to verify deployment succeeded

## Backup Strategy

- Last working commit hash stored in `/home/ubuntu/backend_backups/last_working_commit.txt`
- Automatic rollback on deployment failure
- Backups older than 7 days automatically cleaned up
- Manual backups recommended before major changes

