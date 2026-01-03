import os
import json
import glob
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
API_KEY = os.getenv("AI_API_KEY")
BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("AI_MODEL_NAME", "gpt-3.5-turbo")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# Data Loading
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/data"))

def load_json_file(filepath: str) -> Any:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}

def load_all_data():
    data = {}
    
    # Load main info files
    data["website_info"] = load_json_file(os.path.join(DATA_DIR, "websiteinfo.json"))
    data["product_info"] = load_json_file(os.path.join(DATA_DIR, "productinfo.json"))
    data["certifications"] = load_json_file(os.path.join(DATA_DIR, "certifications.json"))
    
    # Load products
    products = []
    product_files = glob.glob(os.path.join(DATA_DIR, "products", "*.json"))
    for pf in product_files:
        products.append(load_json_file(pf))
    data["products"] = products
    
    return data

website_data = load_all_data()

# Helper functions for dynamic context
def get_relevant_products(query: str, locale: str = "en") -> str:
    """Find products relevant to the query."""
    query = query.lower()
    matches = []
    keywords = query.split()
    
    for p in website_data.get("products", []):
        score = 0
        name = p.get("name", {}).get(locale, p.get("name", {}).get("en", ""))
        category = p.get("category", "")
        desc = p.get("description", {}).get(locale, p.get("description", {}).get("en", ""))
        tags = " ".join(p.get("tags", []))
        
        text_to_search = f"{name} {category} {desc} {tags}".lower()
        
        for kw in keywords:
            if kw in text_to_search:
                score += 1
        
        if score > 0:
            matches.append((score, p))
            
    matches.sort(key=lambda x: x[0], reverse=True)
    
    if not matches:
        return ""
        
    summary = []
    # Limit to top 3 to keep prompt short as requested
    for score, p in matches[:3]:
        name = p.get("name", {}).get(locale, p.get("name", {}).get("en", ""))
        cat = p.get("category", "")
        desc = p.get("description", {}).get(locale, p.get("description", {}).get("en", ""))
        # Shorten description
        summary.append(f"- {name} ({cat}): {desc[:150]}...")
        
    return "Relevant Products:\n" + "\n".join(summary)

def get_company_context(query: str, locale: str = "en") -> str:
    """Get company info based on keywords."""
    query = query.lower()
    info_parts = []
    
    # About
    if any(k in query for k in ["about", "company", "who", "history", "mission", "factory", "manufacture"]):
        about = website_data['website_info'].get('about', {})
        info_parts.append(f"About:\n{json.dumps(about, indent=2, ensure_ascii=False)}")

    # Contact
    if any(k in query for k in ["contact", "email", "phone", "address", "location", "reach", "call", "fax", "wechat"]):
        contact = website_data['website_info'].get('contact', {})
        info_parts.append(f"Contact:\n{json.dumps(contact, indent=2, ensure_ascii=False)}")
        
    # Services
    if any(k in query for k in ["service", "oem", "odm", "custom", "design", "quality"]):
        services = website_data['website_info'].get('services', {})
        info_parts.append(f"Services:\n{json.dumps(services, indent=2, ensure_ascii=False)}")
    
    # Certifications
    if any(k in query for k in ["certifi", "standard", "audit"]):
        certs = website_data.get('certifications', {})
        info_parts.append(f"Certifications:\n{json.dumps(certs, indent=2, ensure_ascii=False)}")

    return "\n\n".join(info_parts)

def get_base_system_prompt(locale: str = "en"):
    company_name = website_data["website_info"].get("companyName", {}).get(locale, "JWL Travel Gear")
    
    prompt = f"""You are the AI assistant for {company_name}, a premium bag manufacturer.
Your goal is to assist visitors with information about the company, its products, and services.

Guidelines:
1. Be polite, professional, and helpful.
2. Answer questions based on the provided context. If you don't know, ask the user to contact support.
3. If the user wants to place an order or has a specific inquiry that requires human attention, offer to draft an email to the company.
4. If the user agrees to send a message, ask for their name, email, and message content (if not provided).
5. Once you have the details, output a special JSON block to signal the backend/frontend to send the email.
   Format: 
   ```json
   {{
     "action": "send_email",
     "data": {{
       "name": "User Name",
       "email": "user@email.com",
       "message": "User message..."
     }}
   }}
   ```
   Do not output this JSON unless you have confirmed with the user.
6. Support multiple languages. If the user speaks Chinese, reply in Chinese.
"""
    return prompt

class ChatMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    locale: Optional[str] = "en"

class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None

class EmailRequest(BaseModel):
    name: str
    email: str
    message: str

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USERNAME)
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

def send_real_email(name: str, email: str, message: str) -> bool:
    """Send a real email using SMTP."""
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, RECIPIENT_EMAIL]):
        print("SMTP configuration missing. Logging to file only.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = f"New Inquiry from {name}"

        body = f"""
        New message from website contact form:
        
        Name: {name}
        Email: {email}
        
        Message:
        {message}
        """
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"Error sending email via SMTP: {e}")
        return False

def log_email(name: str, email: str, message: str):
    """Log email to a file and optionally send via SMTP."""
    try:
        # Log to file
        with open("email_logs.txt", "a", encoding='utf-8') as f:
            f.write(f"--- New Message ---\n")
            f.write(f"From: {name} <{email}>\n")
            f.write(f"Message: {message}\n")
            f.write("---------------------\n\n")
        
        # Append to emails.json
        email_entry = {
            "timestamp": "TODO: Add timestamp", 
            "name": name,
            "email": email,
            "message": message
        }
        
        emails_file = "emails.json"
        existing_emails = []
        
        if os.path.exists(emails_file):
            try:
                with open(emails_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        existing_emails = json.loads(content)
            except json.JSONDecodeError:
                pass # File might be empty or corrupted, start fresh
        
        existing_emails.append(email_entry)
        
        with open(emails_file, 'w', encoding='utf-8') as f:
            json.dump(existing_emails, f, indent=2, ensure_ascii=False)
        
        # Try sending real email
        send_real_email(name, email, message)
        
        return True
    except Exception as e:
        print(f"Error logging email: {e}")
        return False

@app.post("/api/send-email")
async def send_email_endpoint(request: EmailRequest):
    success = log_email(request.name, request.email, request.message)
    if success:
        return {"status": "success", "message": "Email sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    # Determine language from locale
    lang_instruction = ""
    if request.locale == "zh":
        lang_instruction = "IMPORTANT: You MUST reply in Chinese (Simplified). 用户使用中文，请务必用中文回答。"
    else:
        lang_instruction = "Reply in English."

    # Get last user message to determine context
    last_user_msg = request.messages[-1].text
    
    # Dynamic Context Injection
    product_context = get_relevant_products(last_user_msg, request.locale)
    company_context = get_company_context(last_user_msg, request.locale)
    
    context_str = ""
    if product_context:
        context_str += f"\n\n{product_context}"
    if company_context:
        context_str += f"\n\n{company_context}"
    
    # Base prompt with context
    base_prompt = get_base_system_prompt(request.locale)
    system_prompt_final = f"{base_prompt}\n\nContext Information:{context_str}\n\n{lang_instruction}"

    messages = [{"role": "system", "content": system_prompt_final}]
    
    # Add conversation history
    for msg in request.messages:
        role = "assistant" if msg.role == "bot" else "user"
        messages.append({"role": role, "content": msg.text})
    
    try:
        # Check if OpenAI client is configured
        if not API_KEY:
            # Fallback mode: Basic auto-responder
            last_msg = request.messages[-1].text.lower()
            
            # Simple keyword matching
            if "email" in last_msg or "contact" in last_msg or "message" in last_msg:
                if request.locale == "zh":
                    bot_reply = "请提供您的姓名、电子邮件和留言内容，我会将其转发给我们的团队。"
                else:
                    bot_reply = "Please provide your name, email, and message, and I will forward it to our team."
            else:
                if request.locale == "zh":
                    bot_reply = "我现在处于离线模式。请使用联系表单直接联系我们，或在此留言。"
                else:
                    bot_reply = "I am currently in offline mode. Please use the contact form to reach us directly, or leave your message here."
            
            return ChatResponse(response=bot_reply)

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
        )
        
        bot_reply = response.choices[0].message.content
        
        # Check for action block
        action = None
        action_data = None
        
        if "```json" in bot_reply and "\"action\": \"send_email\"" in bot_reply:
            try:
                # Extract JSON
                start = bot_reply.find("```json") + 7
                end = bot_reply.find("```", start)
                json_str = bot_reply[start:end].strip()
                data = json.loads(json_str)
                
                if data.get("action") == "send_email":
                    action = "send_email"
                    action_data = data.get("data")
                    
                    # Log email (Simulate sending)
                    log_email(action_data.get('name'), action_data.get('email'), action_data.get('message'))
                        
                    # Remove the JSON block from the reply shown to user
                    # Keep the text before/after or just replace it with a confirmation message
                    bot_reply = bot_reply.replace(f"```json{json_str}```", "").strip()
                    if not bot_reply:
                        bot_reply = "I have sent your message to our team. They will contact you shortly."
            except Exception as e:
                print(f"Error parsing action: {e}")
        
        return ChatResponse(response=bot_reply, action=action, action_data=action_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "products_loaded": len(website_data["products"])}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
