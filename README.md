# AI-Driven Corporate Website Template

A modern, data-driven, multilingual (English/Chinese) corporate website template built with Next.js, Tailwind CSS, and Framer Motion.

**No WordPress. No Database required. No Heavy CMS.**

This template is designed to be populated entirely by data files. Simply provide your content (text, images, products) in the `src/data` folder, and the website will automatically generate a professional, high-performance online presence. Ideal for manufacturers, B2B companies, and businesses needing a fast, customizable portfolio.

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ installed.

### Setup & Installation
```bash
# Install dependencies
npm install

npm run build   

# Run development server
npm run dev
```

Start the backend server:

```bash
(mypy311) kaikailiu@Kaikais-MacBook-Pro AIwebsite % cd backend 
(mypy311) kaikailiu@Kaikais-MacBook-Pro backend % uvicorn app.app:app --reload --port 8000
LOG_LEVEL=DEBUG uvicorn app.app:app --reload --port 8000
```

Open [http://localhost:3000](http://localhost:3000) to view the site.

## ⚙️ Configuration

The project uses a unified configuration approach. All environment variables are stored in `backend/.env`. The frontend (Next.js) loads these variables via `next.config.js`.

**Key Variable:**
- `NEXT_PUBLIC_API_BASE_URL`: Defines the backend API URL.
    - **Local**: `http://localhost:8000` (Direct connection, avoids Next.js proxy buffering).
    - **Production**: Leave empty to use relative paths (proxied by Nginx) or set to full URL.

**Setup:**
1. Create/Edit `backend/.env`.
2. Add `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
3. `next.config.js` is configured to load this file automatically.

---

## 🎨 How to Customize Content

### 📂 Project Structure & File Descriptions
Here is a quick overview of the key files in this project to help you navigate:

#### **`src/app/`** (Pages & Layout)
- **`layout.tsx`**: The main wrapper for the entire site. Includes the `Navbar`, `Footer`, and global font settings.
- **`page.tsx`**: The Homepage. Combines sections like `Hero`, `About`, `Facility`, `Certifications`, etc.
- **`globals.css`**: Global CSS styles and Tailwind imports.
- **`products/`**: Contains dynamic product pages.
  - **`[category]/page.tsx`**: Displays a list of products for a specific category.
  - **`[category]/[id]/page.tsx`**: The detailed view for a single product.

#### **`src/components/`** (UI Components)
- **`Navbar.tsx`**: Top navigation bar with language switcher.
- **`Footer.tsx`**: Site footer with links and contact info.
- **`Hero.tsx`**: The main slideshow at the top of the homepage.
- **`About.tsx`**: "About Us" section with text and images.
- **`Facility.tsx`**: Showcases factory capabilities (Capacity, Machinery, Inspection).
- **`Certifications.tsx`**: Displays industry certifications (ISO, BSCI, etc.).
- **`Products.tsx`**: "Product Range" section on the homepage with category cards.
- **`Services.tsx`**: Highlights company services (OEM, ODM, Design).
- **`Contact.tsx`**: Contact form and map integration.
- **`Brands.tsx`**: Sliding marquee of trusted global brand partners.
- **`CustomerSamples.tsx`**: Preview grid of customer sample products with a "View All" modal.
- **`ImageModal.tsx`**: Reusable popup modal for viewing enlarged images.
- **`GalleryModal.tsx`**: Modal for viewing large collections of images (used by CustomerSamples).
- **`ChatWidget.tsx`**: Floating chat button for customer support.
- **`products/`**: Dedicated folder for product-related components.
  - **`ProductCard.tsx`**: Reusable card component for displaying product summaries in grid views.
  - **`ProductBrowser.tsx`**: Main interface for browsing products with filters and search.

#### **`src/data/`** (Content & Data)
- **`translations.ts`**: **[IMPORTANT]** The central configuration file. Edit this file to update the **Company Name**, **About Us** details, **Product Categories**, and all other text content. Customizing this file effectively transforms the template into your specific company website.
- **`certifications.json`**: Configuration for certification logos, titles, and descriptions.
- **`images.ts`**: Centralized image path configuration.
- **`products.ts`**: Contains the `products` array with mock data.
- **`products/`**: Folder containing individual JSON files for product data (one file per product).

#### **`src/lib/`** (Logic & Data Access)
- **`products.ts`**: Service logic to fetch and filter products.

#### **`src/contexts/`** (State Management)
- **`LanguageContext.tsx`**: Handles switching between English and Chinese.

#### **`src/types/`**
- **`product.ts`**: TypeScript definitions for Product data structures.

#### **`backend/`** (Python FastAPI Backend)
- **`app/`**:
  - **`app.py`**: Main entry point for the FastAPI application.
  - **`settings.py`**: Configuration loading.
  - **`db.py`**: Database interactions (SQLite/SQLAlchemy).
  - **`llm_client.py`**: Interface for LLM providers (OpenAI, LiteLLM).
  - **`product_search.py`**: Logic for searching products.
  - **`email_ses.py`**: Email sending logic (AWS SES).
  - **`data_store.py`**: Data persistence layer.
- **`.env`**: Backend configuration variables (Unified config source).

---

### 1. Changing Text (Multilingual)
All text content for the website is stored in a centralized translation file.
- **File Location:** `src/data/translations.ts`
- **How to Edit:**
    - Open the file and locate the section you want to change (e.g., `hero`, `about`, `contact`).
    - Edit the text inside the `en` (English) or `zh` (Chinese) objects.
    - **Example:**
      ```typescript
      hero: {
        title: 'New Title Here', // Change this
        subtitle: 'New Subtitle...',
      }
      ```

### 2. Replacing Images
Currently, the website uses placeholder images from Unsplash. To use your own photos, follow these guidelines to ensure fast loading times and correct display.

#### 📐 Image Guidelines

| Section | Recommended Size (px) | Aspect Ratio | Format |
|---------|-----------------------|--------------|--------|
| **Hero Slideshow** | 1920 x 1080 | 16:9 | WebP / JPG |
| **Category Cards** | 800 x 600 | 4:3 | WebP / JPG |
| **Product Detail** | 1200 x 900 | 4:3 | WebP / JPG |
| **About/Services** | 800 x 600 | 4:3 | WebP / JPG |

*Note: For all images, try to keep the file size **under 200KB** (500KB max for Hero images).*

#### 🛠 Tools for Optimization

**Option A: Command Line (ImageMagick)**
If you have many images, use `imagemagick` to resize and convert them in bulk.

1.  **Install ImageMagick:**
    ```bash
    brew install imagemagick
    ```
2.  **Convert & Resize:**
    ```bash
    # Resize to 1920px width, convert to WebP, quality 80%
    magick input.jpg -resize 1920x -quality 80 output.webp
    ```

**Option B: Online Tools (No Install)**
- [Squoosh.app](https://squoosh.app/) (Google) - Excellent for manual compression.
- [TinyPNG](https://tinypng.com/) - Simple drag-and-drop compression.

**Option C: Desktop Software**
- **Photoshop:** File > Export > Save for Web (Legacy).
- **Preview (macOS):** Tools > Adjust Size.

#### 📥 How to Update
1.  **Prepare Images:**
    - Place your optimized image files (e.g., `hero-1.webp`, `bag-sport.webp`) into the `public/images/` folder. Create this folder if it doesn't exist.
2.  **Update References:**
    - **For Products:** Edit `src/services/productService.ts` and replace the Unsplash URLs with your local paths (e.g., `/images/my-bag.jpg`).
    - **For Hero Slideshow:** Edit `src/components/Hero.tsx`.
    - **For Category Cards:** Edit `src/components/Products.tsx`.

### 3. Managing Products
Product data is currently mocked to simulate a CMS structure.
- **File Location:** `src/services/productService.ts`
- **How to Add a Product:**
    - Add a new object to the `mockProducts` array.
    - Ensure you provide a unique `id`, `category`, `slug`, and fill in `attributes` like `name`, `description`, `materials`, and `specifications`.

---

## 🛠 Configuration & Styling

### Changing Color Scheme
The website uses Tailwind CSS for styling. The current theme is **Blue & Gold**.
- **Navbar Colors:** Edit `src/components/Navbar.tsx`. Look for classes like `from-blue-900`, `text-amber-400`.
- **Footer Colors:** Edit `src/components/Footer.tsx`.
- **Global Colors:** You can define custom colors in `src/app/globals.css` or extend the Tailwind config in `tailwind.config.ts` (if you create one, currently using v4 zero-config or standard CSS variables).

### Updating Contact Info
- **Chatbot Email/Phone:** The chat widget collects user info but currently just logs it to the chat history. To change where this goes (e.g., send an email), you would need to implement a backend API route.
- **Contact Section Map:**
    - Edit `src/components/Contact.tsx`.
    - Update the Google Maps `iframe` `src` with your new location link.
    - Update the Baidu Maps link for the Chinese view.

### Switching to a Different Template
If you wish to rebuild the site using a different Next.js template, you can initialize a new project with a specific example.

**Popular Next.js Templates & Resources:**
*   **Official Examples:** [github.com/vercel/next.js/tree/canary/examples](https://github.com/vercel/next.js/tree/canary/examples)
*   **Vercel Templates:** [vercel.com/templates](https://vercel.com/templates) (E-commerce, SaaS, Portfolios)
*   **Tailwind UI:** [tailwindui.com/templates](https://tailwindui.com/templates) (Premium)
*   **Creative Tim:** [creative-tim.com/templates/nextjs](https://www.creative-tim.com/templates/nextjs)

**Command to initialize with a template:**
```bash
npx create-next-app@latest my-app --example <template-name>
# Example: npx create-next-app@latest my-blog --example blog-starter
```

---
## 🤖 AI Chatbot Features

This project includes a powerful, context-aware AI chatbot powered by FastAPI and OpenAI (compatible with Deepseek/Qwen). It is designed to act as a 24/7 sales and support agent.

### Core Capabilities
*   **Dynamic Context Loading**: The bot doesn't just hallucinate; it reads your actual data. It dynamically loads content from `src/data/` (Website Info, Products, Certifications) to answer user questions accurately.
*   **Smart System Prompting**: Constructs a system prompt that injects relevant company and product details based on the user's query (RAG-lite approach).
*   **Multilingual Support**: Automatically detects the user's language (English/Chinese) from the frontend and responds accordingly.
*   **Lead Generation**: Can collect user contact information and "send emails" (logs to file or sends via SMTP).
*   **Offline/Fallback Mode**: If the AI service is unavailable or no API key is provided, it gracefully degrades to a rule-based responder to handle basic inquiries.

### 🛠️ Backend Setup (FastAPI)

#### 1. Start the Server
```bash
cd backend
# Create/Activate virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run Uvicorn
uvicorn app.app:app --reload --port 8000
```
*Expected Output:*
```bash
INFO:     Will watch for changes in these directories: ['.../backend']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started server process [4060]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

#### 2. API Endpoints Reference

| Method | Endpoint | Description | Query/Body Params |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/health` | Check backend status | None |
| **GET** | `/api/products/search` | Search products | `q` (query), `locale` (en/zh), `limit` (default 8) |
| **POST** | `/api/chat` | AI Chat (Standard) | JSON Body: `{ messages: [...], locale: "en", allow_actions: false }` |
| **POST** | `/api/chat/stream` | AI Chat (Streaming) | JSON Body: Same as above. Returns Server-Sent Events (SSE). |
| **POST** | `/api/send-email` | Send Contact Email | JSON Body: `{ name, email, message, locale }` |
| **POST** | `/api/inquiry` | Submit Inquiry (Same as send-email but dedicated) | JSON Body: `{ name, email, message, locale }` |

#### 3. Testing APIs (Curl Examples)
Start the backend server as described in the previous section.
```bash
LOG_LEVEL=DEBUG uvicorn app.app:app --reload --port 8000
```

**A. Health Check**
```bash
curl "http://127.0.0.1:8000/api/health"
# Output: {"status":"ok", "products_loaded": 42, "llm_backend": "openai"}
```

**B. Product Search**
```bash
# English Search
curl "http://127.0.0.1:8000/api/products/search?q=zip%20pocket%20backpack&locale=en&limit=3"

# Chinese Search
curl -G "http://127.0.0.1:8000/api/products/search" \
  --data-urlencode "q=竖拉链 双肩包" \
  --data-urlencode "locale=zh" \
  --data-urlencode "limit=3"
```

**C. AI Chat (Standard)**
```bash
curl -X POST "http://127.0.0.1:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "locale": "en",
    "allow_actions": false,
    "messages": [
      {"role":"user","text":"Do you have an everyday backpack with a vertical front zip pocket?"}
    ]
  }'
```

**D. AI Chat (Streaming)**
```bash
curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "locale":"en",
    "allow_actions": false,
    "messages":[
      {"role":"user","text":"Recommend a tech-friendly backpack."}
    ]
  }'
# Output: data: {"type": "delta", "text": "We recommend..."} ...
```

**E. Send Email**
```bash
curl -X POST "http://127.0.0.1:8000/api/send-email" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "message": "I am interested in bulk ordering.",
    "locale": "en"
  }'
```

**F. Submit Inquiry (With DB)**
```bash
curl -X POST "http://127.0.0.1:8000/api/inquiry" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "email": "jane@example.com",
    "message": "Inquiry about OEM services.",
    "locale": "en"
  }'
```

**G. View SQLite Data**
```bash
# Enter the backend directory
cd backend

# Open the database using sqlite3
sqlite3 inquiries.db

# Run SQL query to view all inquiries
sqlite> SELECT * FROM inquiries;

# To exit sqlite3
sqlite> .exit
```

#### Test tool calling

```bash
(mypy311) kaikailiu@Kaikais-MacBook-Pro backend % curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "locale":"en",
    "allow_actions": true,
    "messages":[
      {"role":"user","text":"CONFIRM SEND. Name: Kaikai. Email: lkk688@gmail.com. Message: I need to order 1000 units. Please send me the quote."}
    ]
  }'
```

### RAG
Test build the RAG index
```bash
python -c "from app.embeddings_client import EmbeddingsClient; from app.data_store import DataStore; from app.product_rag import ProductRAG; from app.settings import settings; s=DataStore(settings.data_dir); rag=ProductRAG(s.products, EmbeddingsClient()); rag.build_index(); print('built', len(s.products))"
```

### 📧 Email Configuration
The bot can send real emails using Python's `smtplib`. It supports both logging to a file (`tools/email_logs.txt`) and sending via SMTP.

To enable real email sending, add these variables to `tools/.env`:
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
RECIPIENT_EMAIL=support@yourcompany.com
```

### 💻 Frontend Integration
The `ChatWidget.tsx` component handles the UI and communicates with the backend. We use `NEXT_PUBLIC_API_BASE_URL` to dynamically connect to the backend.

**Chat Stream (`src/components/ChatWidget.tsx`):**
```typescript
const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || ''}/api/chat/stream`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    messages: [...history, { role: 'user', text: msg }],
    locale: t.nav?.home === '首页' ? 'zh' : 'en',
    allow_actions: true,
  }),
});
```

**Product Search (`src/components/products/ProductBrowser.tsx`):**
```typescript
const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || ''}/api/products/search?${params.toString()}`);
```

*   **API Endpoint**: Calls `${API_BASE}/api/chat` for conversation.
*   **Typing Indicators**: Displays a natural typing state while waiting for the AI response.
*   **Form Integration**: The contact form within the chat sends data to `${API_BASE}/api/send-email`.

## 🔌 Extending Functionality

### 1. Connecting to Strapi (Headless CMS)
The project is architected to easily switch from mock data to a real Strapi backend.

**Step 1: Setup Strapi**
- Create a Strapi project and define a `Product` content type with fields matching the types in `src/lib/products.ts` (name, description, category, images, specifications (JSON), etc.).

**Step 2: Update Service Layer**
- Open `src/lib/products.ts`.
- Replace the mock functions with actual API calls.
- **Example:**
  ```typescript
  const STRAPI_URL = process.env.NEXT_PUBLIC_STRAPI_URL || 'http://localhost:1337';

  export const getProductsByCategory = async (category: string) => {
    const res = await fetch(`${STRAPI_URL}/api/products?filters[category][$eq]=${category}&populate=*`);
    const data = await res.json();
    return data.data; // Ensure this maps to your Product type
  };
  ```

### 2. Adding Email Notifications
To receive emails from the Contact Form or Chat Widget:
1.  Create an API route in `src/app/api/contact/route.ts`.
2.  Use a service like **Resend**, **SendGrid**, or **Nodemailer**.
3.  Update `src/components/ChatWidget.tsx` to `POST` the user's data to this API route instead of just updating the local state.

---

## 📦 Deployment

### 🐳 Deploying with Docker (Recommended)

This approach uses Docker Compose to run the Next.js frontend, FastAPI backend, and Nginx reverse proxy in containers.

#### 1. Install Docker on your VM (Ubuntu)
```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add user to docker group (allows running docker without sudo)
sudo usermod -aG docker $USER

# Log out and back in for changes to take effect
exit
```

#### 2. Sync Code to Server
On your local machine, use `rsync` to upload the project.
Replace `ubuntu@54.65.52.96` with your server's user and IP.

```bash
# Create app directory on server
ssh -i ~/.ssh/id_ed25519 ubuntu@54.65.52.96 "mkdir -p ~/app"

# Sync project files (excluding heavy/unnecessary folders)
rsync -avz -e "ssh -i ~/.ssh/id_ed25519" \
  --exclude node_modules \
  --exclude .next \
  --exclude backend/__pycache__ \
  --exclude backend/.env \
  ./ ubuntu@54.65.52.96:~/mywebsite/

# Copy environment variables file separately (for security)
scp -i ~/.ssh/id_ed25519 backend/.env ubuntu@54.65.52.96:~/mywebsite/backend/.env
```

#### 3. Start Services
On the server:
```bash
cd ~/mywebsite
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f --tail=200 nginx
docker compose logs -f --tail=200 api
docker compose logs -f --tail=200 web
```

- **Website**: `http://<your-server-ip>`
- **API Health Check**: `http://<your-server-ip>/api/health`

### ☁️ Deploying to a Cloud VM (Manual Method)

This guide assumes you have a VM running Ubuntu 20.04/22.04 LTS and a domain name pointing to your server's IP.

#### 1. Prepare the Server
Connect to your server via SSH and install the necessary tools:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js (v18+)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Process Manager (PM2)
sudo npm install -g pm2

# Install Web Server (Nginx)
sudo apt install nginx -y
```

#### 2. Deploy Code
1.  Clone your repository to `/var/www/my-website` or upload files via SFTP.
2.  Install dependencies and build the project:
    ```bash
    cd /var/www/my-website
    npm install
    npm run build
    ```
3.  Start the application with PM2:
    ```bash
    pm2 start npm --name "my-website" -- start
    pm2 save
    pm2 startup
    ```

#### 3. Configure Nginx (Reverse Proxy)
Create a configuration file for your domain:
```bash
sudo nano /etc/nginx/sites-available/your-domain.com
```

Paste this configuration (replace `your-domain.com` with your actual domain):
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

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

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/your-domain.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 4. Add HTTPS Support (SSL)
Secure your site with a free Let's Encrypt certificate using Certbot:

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain and install certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```
Follow the prompts to enable automatic HTTPS redirection.

---

### 🚀 Deploying on Vercel (Alternative)
1.  Push code to GitHub.
2.  Import project into Vercel.
3.  The build settings are pre-configured (`npm run build`).

## Security Enhancement
Do not commit or add the `.env` file to your repository. Instead, use environment variables on your server. Check whether the `.env` file is already in git: `git log --all -- .env`, if the output is empty, then the file is not committed.

When deployment, create a root read-only env file on your server. 
```bash
sudo mkdir -p /etc/mywebsite
sudo nano /etc/mywebsite/backend.env
#add content
sudo chmod 600 /etc/mywebsite/backend.env
sudo chown root:root /etc/mywebsite/backend.env
```

systemmd service will refer it: /etc/systemd/system/mywebsite-backend.service：
```bash
[Unit]
Description=MyWebsite FastAPI
After=network.target

[Service]
WorkingDirectory=/opt/mywebsite/backend
EnvironmentFile=/etc/mywebsite/backend.env
ExecStart=/opt/mywebsite/backend/venv/bin/uvicorn app.app:app --host 127.0.0.1 --port 8000
Restart=always
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```
Then, start
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mywebsite-backend
```

If using docker-compose deployment:
```bash
mkdir -p /opt/mywebsite/secrets
nano /opt/mywebsite/secrets/backend.env
chmod 600 /opt/mywebsite/secrets/backend.env
```
Add these to docker-compose.yml:
```bash
services:
  api:
    env_file:
      - /opt/mywebsite/secrets/backend.env
```

Exclude the env file during rsync:
```bash
rsync -av --delete \
  --exclude '.env' --exclude '.env.*' \
  --exclude '__pycache__' --exclude '*.pyc' \
  backend/ user@server:/opt/mywebsite/backend/
```

## 🤖 AI Chat System

The backend features an advanced AI chat system with embedding-based intent routing and a modular tool execution layer.

### Core Components

1.  **Intent Router (`backend/app/chat/intent_router.py`)**:
    *   Uses embedding similarity (cosine distance) to classify user queries into intents (e.g., `quote_order`, `technical`, `broad_product`).
    *   Configurable via `src/data/chat_config.json` under `intent_examples`.

2.  **Tool Execution Layer (`backend/app/tools/`)**:
    *   **Dispatcher (`dispatcher.py`)**: Central hub that routes tool calls to the correct handler.
    *   **Handlers (`handlers.py`)**: Implementation of tool logic (e.g., `handle_product_search`, `handle_send_inquiry`).
    *   **Context (`base.py`)**: Passes shared dependencies (database, mailer, settings) to tools safely.

3.  **Chat Service (`chat_service.py`)**:
    *   Orchestrates the conversation.
    *   Dynamic tool filtering based on intent and conversation stage.

### 🛠 How to Add a New Tool

1.  **Define Tool in Config**:
    Add your tool definition to `src/data/chat_config.json`:
    ```json
    "tools": {
      "my_new_tool": {
        "enabled": true,
        "description": {"en": "...", "zh": "..."},
        "parameters": { ... },
        "handler": "my_tool_handler"
      }
    }
    ```

2.  **Implement Handler**:
    Add the python function in `backend/app/tools/handlers.py`:
    ```python
    def handle_my_tool(ctx: ToolContext, arg1: str):
        # Your logic here
        return {"result": "ok"}
    ```

3.  **Register Handler**:
    Register the new handler in `backend/app/app.py`:
    ```python
    from .tools.handlers import handle_my_tool
    dispatcher.register("my_tool_handler", handle_my_tool)
    ```