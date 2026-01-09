# Backend Documentation

This document provides a detailed overview of the backend structure, configuration, and extensibility of the AI Website project.

## 🏗 Project Structure

The backend code is organized into a modular architecture to support scalability, maintainability, and easy switching of components (like LLM providers or databases).

```
backend/
├── app/
│   ├── main.py                 # Application Entry Point (FastAPI app, middleware, logging)
│   ├── api/                    # HTTP Interface Layer
│   │   ├── routes/             # API Route Handlers
│   │   │   ├── chat.py         # Chat endpoints (sync & stream)
│   │   │   └── general.py      # General endpoints (health, email, product search)
│   │   └── schemas.py          # Pydantic Models (Request/Response validation)
│   ├── core/                   # Core Infrastructure
│   │   ├── config.py           # Centralized Configuration (Settings)
│   │   ├── logging.py          # Logging Setup & SessionLogger
│   │   └── services.py         # Dependency Injection Container (Singletons)
│   ├── services/               # Business Logic Layer
│   │   ├── chat/               # Chat Domain Logic
│   │   │   ├── service.py      # Main ChatService (Orchestrator)
│   │   │   ├── state.py        # Conversation State Management (LRU Cache)
│   │   │   └── router.py       # Intent Routing Logic
│   │   ├── rag/                # Retrieval-Augmented Generation Logic
│   │   │   ├── product.py      # Product RAG
│   │   │   ├── kb.py           # Knowledge Base RAG
│   │   │   └── vector.py       # Vector Index Implementation (Numpy/Faiss)
│   │   ├── product.py          # Product Search Logic
│   │   └── data.py             # Data Loading Logic
│   ├── adapters/               # External System Interfaces
│   │   ├── llm.py              # LLM Client (OpenAI / LiteLLM)
│   │   ├── embeddings.py       # Embedding Client
│   │   ├── db.py               # Database Adapter
│   │   └── email.py            # Email Service Adapter (AWS SES)
│   └── tools/                  # Agent Tools
│       ├── registry.py         # Tool Definitions & Configuration
│       ├── dispatcher.py       # Tool Execution Dispatcher
│       └── handlers.py         # Tool Implementation Handlers
├── logs/                       # Application Logs
├── .env                        # Environment Variables
└── backend_readme.md           # This file
```

---

## ⚙️ Configuration

The application uses `pydantic-settings` to manage configuration. All settings are defined in `backend/app/core/config.py` and loaded from the `.env` file.

### **1. LLM & Embeddings (Switching Providers)**

You can switch between **OpenAI** (default) and **LiteLLM** (for Ollama, Anthropic, DeepSeek, etc.) by changing environment variables.

**A. OpenAI (Default)**
```bash
LLM_BACKEND=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-proj-...
```

**B. LiteLLM (e.g., Local Ollama)**
```bash
LLM_BACKEND=litellm
LLM_MODEL=ollama/llama3
LITELLM_API_BASE=http://localhost:11434
```

**C. LiteLLM (e.g., DeepSeek via API)**
```bash
LLM_BACKEND=litellm
LLM_MODEL=deepseek/deepseek-chat
LITELLM_API_KEY=sk-deepseek-...
LITELLM_API_BASE=https://api.deepseek.com
```

### **2. Embeddings Provider**

Control the embedding model separately from the LLM.

```bash
EMBEDDINGS_BACKEND=openai
EMBEDDINGS_MODEL=text-embedding-3-small
# Or for local:
# EMBEDDINGS_BACKEND=litellm
# EMBEDDINGS_MODEL=ollama/nomic-embed-text
```

### **3. External Services**

*   **AWS SES (Email)**: Required for `send_inquiry` tool.
    ```bash
    AWS_REGION=us-west-2
    AWS_ACCESS_KEY_ID=...
    AWS_SECRET_ACCESS_KEY=...
    SES_FROM_EMAIL=sender@example.com
    SES_TO_EMAIL=recipient@example.com
    ```

*   **Vector Index**:
    ```bash
    VECTOR_INDEX_TYPE=numpy  # 'numpy' (default, simple) or 'faiss' (fast, requires install)
    ```

---

## 🚀 Extensibility Guide

### **1. Adding a New LLM Provider**
The system uses `backend/app/adapters/llm.py` as a unified interface.
*   **Via LiteLLM**: Just update `LLM_MODEL` in `.env`. LiteLLM supports 100+ providers out of the box.
*   **Custom Adapter**: If you need a completely custom SDK (e.g., specialized Agent SDK), modify `LLMClient` in `adapters/llm.py` to add a new backend branch.

### **2. Adding New Agent Tools**
1.  **Define Tool**: Add configuration in `src/data/chat_config.json` under `"tools"`.
    ```json
    "my_new_tool": {
        "enabled": true,
        "description": {"en": "Description..."},
        "parameters": { ... },
        "handler": "my_tool_handler"
    }
    ```
2.  **Implement Handler**: Add the python function in `backend/app/tools/handlers.py`.
3.  **Register Handler**: Update `backend/app/services/chat/service.py` to register the new handler in `__init__`:
    ```python
    self.dispatcher.register("my_new_tool", handle_my_tool)
    ```

### **3. Integrating Frameworks (LlamaIndex / LangChain)**
To replace the custom RAG implementation with a framework:
1.  Create a new service in `backend/app/services/rag/`.
    *   e.g., `llamaindex_service.py`.
2.  Implement the retrieval logic using the framework.
3.  Update `backend/app/services/chat/service.py` to use your new service instead of `product_rag.py`.

### **4. Switching Database**
Currently, the app uses a lightweight file-based store (`DataStore`) and SQLite (`adapters/db.py`).
*   To use **PostgreSQL**: Update `backend/app/adapters/db.py` to use `SQLAlchemy` with a Postgres connection string. The rest of the app calls `insert_inquiry` which abstracts the DB implementation.
*   To use a **Vector DB** (Pinecone/Weaviate): Create a new adapter `backend/app/adapters/vectordb.py` and update `services/rag/vector.py` to delegate to it.

---

## 🛠 Development

### **Start Server**
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload --port 8000
```

### **Directory Paths**
*   `BASE_DIR`: Resolves to `backend/`.
*   `DATA_DIR`: Defaults to `../src/data` (relative to `backend/`).

---

## 🌊 Chat Process (Streaming & Tool Use)

The core chat logic resides in `backend/app/services/chat/service.py` and supports both **Streaming** (`/api/chat/stream`) and **Synchronous** (`/api/chat`) endpoints. Both use a unified **Agent Loop** approach.

### **How it works:**

1.  **Request Handling**:
    *   User sends a message.
    *   `ChatService` prepares the context:
        *   Retrieves conversation history (LRU Cache).
        *   Determines Intent (Routing).
        *   Retrieves RAG Context (Product + Knowledge Base).
        *   Selects allowed Tools based on configuration.

2.  **Agent Loop (`MAX_TURNS`)**:
    *   The LLM is called with the user message + tools.
    *   **Turn 1**:
        *   LLM may decide to call a tool (e.g., `product_search`, `send_inquiry`).
        *   Backend executes the tool via `ToolDispatcher`.
        *   Tool result is fed back to the LLM as a "System Notification".
    *   **Turn 2**:
        *   LLM generates a final natural language response based on the tool output.

3.  **Streaming Response (SSE)**:
    *   The `/stream` endpoint uses Server-Sent Events (SSE) to push updates in real-time.
    *   **Events**:
        *   `delta`: Text chunks (token by token).
        *   `tool_call`: Notification that a tool is being executed.
        *   `action_event`: Triggers UI side effects (e.g., show success toast).
        *   `final`: The complete final text response (or UI data for rendering cards).
        *   `done`: Stream complete.

---

## 📂 Data-Driven Architecture

The application logic is heavily driven by JSON configuration files located in `src/data/`. This allows you to modify behavior without changing code.

### **1. Chat Configuration (`src/data/chat_config.json`)**
Controls the chatbot's personality, tools, and intent routing.
*   **`system_prompts`**: Define the LLM's persona and rules per locale.
*   **`tools`**: Enable/disable tools, configure required slots.
*   **`routing_keywords`**: Keywords to trigger specific retrieval strategies (broad vs. technical).
*   **`intent_examples`**: Example queries to train the embedding-based Intent Router.

### **2. Search Configuration (`src/data/search_config.json`)**
Controls the product search algorithm.
*   **`fields`**: Which JSON fields to index and their weight.
*   **`stop_words`**: Words to ignore in search queries.

### **3. Product Data (`src/data/products/`)**
*   Each product is a JSON file.
*   The system automatically indexes these files on startup (`DataStore` service).
*   **To Add a Product**: Simply add a new JSON file to this folder. No DB migration needed.

### **4. Website Info (`src/data/websiteinfo.json`)**
*   Contains company details (About Us, Contact Info) used for RAG (Retrieval Augmented Generation) to answer general questions.

---

## 🐛 Debugging & Logs

### **1. Enabling Debug Logs**
Set `LOG_LEVEL` in `.env` or when running the command:
```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

### **2. Log Files**
Logs are stored in `backend/logs/`.
*   **Session Logs**: Each chat session generates a dedicated log file for easy debugging.
    *   Format: `YYYYMMDD_HHMM_{conversation_id}.log`
    *   Contains: User input, full prompt sent to LLM, tool execution details (args/results), and final response.
*   **Consolidation**: All requests for the same `conversation_id` are appended to the same file.

### **3. Test Scripts**
Useful scripts are located in `backend/scripts/`.

*   **`test_chat_stream.py`**: Simulates a full streaming chat session (User asks -> Tool Search -> User Confirms -> Tool Email).
    ```bash
    python backend/scripts/test_chat_stream.py
    ```

