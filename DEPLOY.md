# Deployment Guide for JWLproducts.com

This guide outlines the steps to deploy the Next.js website to a Cloud VM (e.g., AWS EC2, DigitalOcean, Linode) running Ubuntu, and how to configure the DNS.

## Prerequisites

- A Cloud VM with Ubuntu 20.04/22.04 LTS.
- A domain name (JWLproducts.com) purchased from a registrar (e.g., GoDaddy, Namecheap).
- SSH access to your VM.

## 1. Server Setup

### Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### Install Node.js (v18 or later)
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Install PM2 (Process Manager)
PM2 ensures your app stays online.
```bash
sudo npm install -g pm2
```

### Install Nginx (Web Server)
```bash
sudo apt install nginx -y
```

## 2. Deploy Application

### Clone/Upload Code
You can clone from git or upload your project files to `/var/www/jwl-website`.

```bash
mkdir -p /var/www/jwl-website
# Copy your files here
cd /var/www/jwl-website
```

### Install Dependencies & Build
```bash
npm install
npm run build
```

### Start with PM2
```bash
pm2 start npm --name "jwl-website" -- start
pm2 save
pm2 startup
```

## 3. Configure Nginx

Create a new configuration file:
```bash
sudo nano /etc/nginx/sites-available/jwlproducts.com
```

Paste the following configuration:
```nginx
server {
    listen 80;
    server_name jwlproducts.com www.jwlproducts.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/jwlproducts.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 4. DNS Setup

Go to your Domain Registrar's DNS settings and add the following records:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A    | @    | <YOUR_VM_PUBLIC_IP> | 3600 |
| CNAME| www  | jwlproducts.com     | 3600 |

*Replace `<YOUR_VM_PUBLIC_IP>` with the actual IP address of your server.*

## 5. SSL Certificate (HTTPS)

Secure your site with a free Let's Encrypt certificate.

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d jwlproducts.com -d www.jwlproducts.com
```

Follow the prompts to redirect HTTP to HTTPS.

## 6. Future Integrations

### Connecting Strapi (CMS)
1. Install Strapi on a separate server or path (e.g., `api.jwlproducts.com`).
2. Update the Next.js code to fetch data from the Strapi API instead of using static content in `src/data/translations.ts`.

### Connecting AI Chatbot
1. Choose a provider (e.g., OpenAI Assistant, Intercom, or custom).
2. Add the chatbot script to `src/app/layout.tsx` or create a `Chatbot` component.
