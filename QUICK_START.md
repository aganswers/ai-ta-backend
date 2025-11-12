# Quick Start - CI/CD Setup

## Commands to Run Now

### 1. Make scripts executable and run setup
```bash
cd /home/ubuntu/backend
chmod +x setup-cicd.sh deploy.sh
./setup-cicd.sh
```

### 2. Get your SSH private key for GitHub
```bash
cat ~/.ssh/id_rsa
```
Copy the entire output (including `-----BEGIN` and `-----END` lines)

### 3. Get your EC2 public hostname
```bash
curl -s http://169.254.169.254/latest/meta-data/public-hostname
```

## GitHub Secrets to Add

Go to: `https://github.com/aganswers/ai-ta-backend/settings/secrets/actions`

Add these 3 SSH secrets:
- `EC2_HOST` = (output from command #3 above)
- `EC2_USER` = `ubuntu`
- `EC2_SSH_KEY` = (output from command #2 above)

Then add all your environment variables from your current `.env` file as GitHub secrets.

## Test Everything

### Test locally
```bash
curl http://localhost:8001/
```

### Push to GitHub
```bash
git add .github/workflows/ci-cd.yml deploy.sh flask-backend.service setup-cicd.sh CICD_SETUP.md QUICK_START.md
git commit -m "Add CI/CD pipeline"
git push origin main
```

Watch the GitHub Actions tab in your repository to see the deployment!

## Useful Commands

```bash
# View service status
sudo systemctl status flask-backend

# View logs (live)
sudo journalctl -u flask-backend -f

# Restart service
sudo systemctl restart flask-backend

# View application logs
tail -f /home/ubuntu/backend/output.log
```

## What Happens Now?

Every time you push to `main`:
1. GitHub runs tests (linting + Flask startup)
2. If tests pass → auto-deploys to EC2
3. If deployment fails → auto-rolls back to last working version
4. You get notified via GitHub Actions

That's it! 🚀

