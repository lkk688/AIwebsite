# Deployment Guide for JWLproducts.com

This guide outlines the steps to deploy the full-stack application (Next.js Frontend + FastAPI Backend + RAG/SQLite) to a Cloud VM.

## 1. System Requirements

For the current stack including RAG (Vector Search), Database, and Web Server:

| Resource | Minimal (Local Build) | Recommended (Server Build) |
|----------|-----------------------|----------------------------|
| **vCPU** | 1 vCPU                | 2 vCPU                     |
| **RAM**  | 1 GB (requires Swap)  | 2 GB+                      |
| **Disk** | 10 GB SSD             | 20 GB SSD                  |

> **Note**: If your server has only 1GB RAM, compiling Next.js (`npm run build`) will likely fail due to memory exhaustion. We recommend **Option B (Local Build)** for small instances.

## 2. Server Setup

### Update System
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install nginx git rsync curl -y
```

### Install Node.js (v18+)
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Install Python (3.10+)
```bash
sudo apt install python3-pip python3-venv -y
```

### Install PM2 (Process Manager)
We use PM2 to manage both Node.js and Python processes for a unified dashboard.
```bash
sudo npm install -g pm2
```

## 3. Deploy Application

You have two strategies to deploy the code.

### Option A: Build on Server (Standard)
*Best for servers with 2GB+ RAM.*

1. **Clone Repository**:
   ```bash
   mkdir -p /var/www/jwl-website
   git clone <YOUR_REPO_URL> /var/www/jwl-website
   cd /var/www/jwl-website
   ```

2. **Frontend Build**:
   ```bash
   npm install
   npm run build
   ```

### Option B: Local Build + Rsync (Low Resource)
*Best for 1GB RAM servers to avoid OOM errors.*

1. **Build Locally** (on your machine):
   ```bash
   npm run build
   ```

2. **Sync Files to Server**:
   Use `rsync` to upload the project.
   > **Why sync the whole repo?** 
   > 1. The **Backend** (Python) runs directly from source.
   > 2. The **Backend** needs access to `src/data` (shared JSON data).
   > 3. The **Frontend** needs `package.json` and `next.config.js` to start.
   
   ```bash
   rsync -avz --exclude 'node_modules' --exclude '.venv' --exclude '.git' --exclude '.env' ./ user@<SERVER_IP>:/var/www/jwl-website/
   ```

3. **Install Production Deps on Server**:
   ```bash
   ssh user@<SERVER_IP>
   cd /var/www/jwl-website
   npm install --production
   ```

## 4. Backend Setup & Configuration

### Setup Python Environment
```bash
cd /var/www/jwl-website/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Securely Manage Environment Variables
**NEVER** commit `.env` files to Git. Instead, create it directly on the server.

1. **Create the file**:
   ```bash
   nano /var/www/jwl-website/backend/.env
   ```

2. **Paste Production Variables**:
   Copy the content from your local `.env` (excluding any local-only debug flags) and paste it here.
   *Ensure you set a strong secret key and the correct DB path:*
   ```env
   APP_ENV=production
   INQUIRIES_DB_FILE=main.db
   SECRET_KEY=generate_a_long_random_string_here
   # ... other API keys (OpenAI, AWS, etc) ...
   ```

3. **Restrict Permissions**:
   Make the file readable only by the owner (to prevent other users on the shared server from reading secrets).
   ```bash
   chmod 600 /var/www/jwl-website/backend/.env
   ```

## 5. Process Management: PM2 vs Systemd

We use **PM2** because it simplifies managing mixed-language microservices (JS + Python) in one view.

| Feature | PM2 (Recommended) | Systemd |
|---------|-------------------|---------|
| **Ease of Use** | High (Simple CLI) | Medium (Config files) |
| **Logs** | Built-in (`pm2 logs`) | `journalctl` |
| **Node.js** | Native Cluster Mode | Good |
| **Python** | Good support | Native standard |

### Start Services with PM2

1. **Start Backend (FastAPI)**:
   ```bash
   cd /var/www/jwl-website/backend
   pm2 start "source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000" --name "jwl-backend"
   ```

2. **Start Frontend (Next.js)**:
   ```bash
   cd /var/www/jwl-website
   pm2 start npm --name "jwl-frontend" -- start
   ```

3. **Save & Startup**:
   ```bash
   pm2 save
   pm2 startup
   ```

## 6. Configure Nginx (Reverse Proxy)

Update Nginx to route traffic to Frontend (3000) and Backend (8000).

```bash
sudo nano /etc/nginx/sites-available/jwlproducts.com
```

Configuration:
```nginx
server {
    listen 80;
    server_name jwlproducts.com www.jwlproducts.com;

    # Frontend (Next.js)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API (FastAPI)
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/jwlproducts.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 7. DNS Setup

Point your domain to your server's public IP address.

1. Log in to your Domain Registrar (GoDaddy, Namecheap, Route53, etc.).
2. Go to **DNS Management** for `jwlproducts.com`.
3. Add the following records:

| Type | Host / Name | Value / Target | TTL |
|------|-------------|----------------|-----|
| **A** | `@` | `<YOUR_SERVER_PUBLIC_IP>` | 3600 (1 hour) |
| **CNAME** | `www` | `jwlproducts.com` | 3600 (1 hour) |

*Note: It may take up to 24-48 hours for DNS changes to propagate globally, though it's usually much faster.*

## 8. HTTPS Setup (SSL)

Secure your site with a free Let's Encrypt certificate using Certbot.

1. **Install Certbot**:
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   ```

2. **Obtain Certificate**:
   Run the following command and follow the interactive prompts.
   ```bash
   sudo certbot --nginx -d jwlproducts.com -d www.jwlproducts.com
   ```
   *   Select **Option 2** (Redirect) when asked if you want to redirect HTTP traffic to HTTPS. This ensures all users are automatically on the secure version.

3. **Verify Auto-Renewal**:
   Let's Encrypt certificates expire every 90 days. Certbot installs a timer to renew them automatically. Verify it's working:
   ```bash
   sudo systemctl status certbot.timer
   ```
