<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white" alt="Groq">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
</p>

# BuyQK AI

> **AI-powered commerce assistant** — combining LangGraph orchestration, Groq/Llama inference, and a FastAPI backend to deliver a conversational shopping experience.

BuyQK AI understands natural language, classifies user intent, extracts entities, executes backend operations, and responds conversationally — all while keeping the backend as the **single source of truth** for transactional data.

---

## What It Does

| Capability | Description |
|---|---|
| **Product Search** | Find products by name, category, or keyword |
| **Order Creation** | Place orders with product, quantity & address |
| **Order Tracking** | Check real-time status of existing orders |
| **Order Cancellation** | Cancel orders with backend confirmation |
| **Customer Support** | File support tickets for issues |
| **General Chat** | Natural conversation with context awareness |

---

## Tech Stack

### Frontend
- **Framework:** Next.js / React
- **State Management:** Zustand
- **Styling:** Vanilla CSS (Minimal, no external CSS frameworks)

### Backend
- **API Framework:** FastAPI (Python 3.11+)
- **ORM:** SQLAlchemy
- **Databases:**
  - **SQLite:** Transactional data (users, orders, products)
  - **Redis:** Short-term session and conversation memory
  - **FAISS:** Vector similarity search for Knowledge Base (RAG)

### AI & Orchestration
- **Workflow Orchestration:** LangGraph
- **LLM Integration:** LangChain
- **Inference Engine:** Groq (ultra-fast inference)
- **Model:** Llama 3 (e.g., Llama-3.1-8b-instant / Llama-3.3-70b-versatile)

---

## Architecture

### System Overview

```mermaid
graph TD
    A["Next.js Frontend"] -->|"POST /chat"| B["FastAPI"]
    B --> C["LangGraph Engine"]
    B --> D["Backend Services"]
    C --> E["Groq / Llama 3.3 70B"]
    D --> F["SQLite"]
    C -->|"session context"| G["Redis Memory"]
    C -->|"knowledge lookup"| H["FAISS"]

    style A fill:#0070f3,stroke:#0051b3,color:#fff
    style B fill:#009688,stroke:#00796b,color:#fff
    style C fill:#7c3aed,stroke:#5b21b6,color:#fff
    style D fill:#059669,stroke:#047857,color:#fff
    style E fill:#f55036,stroke:#c5402b,color:#fff
    style F fill:#003b57,stroke:#002a3f,color:#fff
    style G fill:#dc382d,stroke:#b02c24,color:#fff
    style H fill:#f59e0b,stroke:#d97706,color:#fff
```

### AI Workflow Pipeline

Every user message flows through a **5-node LangGraph pipeline**:

```mermaid
graph LR
    A["User Message"] --> B["Intent Node"]
    B --> C["Entity Node"]
    C --> D["Decision Node"]
    D --> E["Tool Node"]
    E --> F["Response Node"]
    F --> G["Final Answer"]

    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style B fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style C fill:#a78bfa,stroke:#8b5cf6,color:#fff
    style D fill:#c084fc,stroke:#a855f7,color:#fff
    style E fill:#e879f9,stroke:#d946ef,color:#fff
    style F fill:#f0abfc,stroke:#e879f9,color:#fff
    style G fill:#22c55e,stroke:#16a34a,color:#fff
```

| Node | Purpose | Output |
|---|---|---|
| **Intent** | Classifies the message via LLM | `product_search`, `order_create`, `order_tracking`, `order_cancel`, `customer_support`, `general` |
| **Entity** | Extracts structured data via LLM | `product_name`, `quantity`, `order_id`, `address_id` |
| **Decision** | Deterministic routing logic | Selects which backend tool to execute |
| **Tool** | Executes the backend operation | Authoritative result from SQLite |
| **Response** | Converts result to natural language | User-facing conversational reply |

### Request Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant F as Next.js
    participant API as FastAPI
    participant G as LangGraph
    participant L as Groq/Llama
    participant S as Services
    participant DB as SQLite

    U->>F: Natural-language message
    F->>API: POST /chat
    API->>G: run_chat()
    G->>L: Classify intent
    L-->>G: Structured intent
    G->>L: Extract entities
    L-->>G: Structured entities
    G->>G: Decision routing
    G->>S: Execute tool > service
    S->>DB: Query / update
    DB-->>S: Result
    S-->>G: Tool result
    G->>L: Generate response
    L-->>G: Natural-language reply
    G-->>API: Final response
    API-->>F: JSON response
    F-->>U: Rendered answer
```

---

## Project Structure

```
buyqk-ai/
|
├── ai_engine/                        # AI orchestration layer
│   ├── graph/
│   │   ├── state.py                  # GraphState TypedDict
│   │   ├── builder.py                # LangGraph construction
│   │   └── runner.py                 # run_chat() entry point
│   ├── nodes/
│   │   ├── intent_node.py            # Intent classification (LLM)
│   │   ├── entity_node.py            # Entity extraction (LLM)
│   │   ├── decision_node.py          # Deterministic routing
│   │   ├── tool_node.py              # Backend tool execution
│   │   └── response_node.py          # Response generation (LLM)
│   ├── llm/
│   │   └── client.py                 # Centralized Groq/Llama config
│   ├── memory/
│   │   └── redis_memory.py           # Redis + in-memory fallback
│   ├── prompts/
│   │   └── system_prompt.txt         # Behavioral contract
│   └── tests/                        # AI-specific tests
│
├── backend/                          # FastAPI application
│   ├── api/
│   │   ├── chat.py                   # POST /chat endpoint
│   │   └── health.py                 # GET /health endpoint
│   ├── models/                       # SQLAlchemy ORM models (11 tables)
│   ├── schemas/                      # Pydantic request/response schemas
│   ├── services/
│   │   ├── product_service.py        # Product search & lookup
│   │   ├── order_service.py          # Order CRUD operations
│   │   └── support_service.py        # Support ticket operations
│   ├── database/
│   │   ├── sqlite.py                 # SQLite engine config
│   │   ├── dependencies.py           # FastAPI DB session dependency
│   │   ├── redis_client.py           # Redis connection helper
│   │   ├── vector_store.py           # FAISS vector store
│   │   └── init_db.py               # Table initialization
│   ├── tests/                        # Backend-specific tests
│   └── main.py                       # FastAPI app entry point
│
├── requirements.txt
├── .env                              # API keys (never commit)
├── .gitignore
└── README.md
```

---

## Data Layer

### Entity Relationships

```mermaid
erDiagram
    USERS ||--o{ ADDRESSES : "has"
    USERS ||--o{ ORDERS : "creates"
    USERS ||--o{ CONVERSATION_HISTORY : "owns"
    USERS ||--o{ SUPPORT_TICKETS : "creates"
    CATEGORIES ||--o{ PRODUCTS : "contains"
    MERCHANTS ||--o{ PRODUCTS : "sells"
    ADDRESSES ||--o{ ORDERS : "delivers to"
    RIDERS ||--o{ ORDERS : "delivers"
    ORDERS ||--o{ ORDER_ITEMS : "contains"
    PRODUCTS ||--o{ ORDER_ITEMS : "included in"
    ORDERS ||--o{ PAYMENTS : "has"
    ORDERS ||--o{ SUPPORT_TICKETS : "concerns"
```

### Data Infrastructure

| Store | Purpose | Scope |
|---|---|---|
| **SQLite** | Transactional data (users, orders, products, payments) | Persistent, authoritative |
| **Redis** | Short-term conversation/session memory | Ephemeral, session-scoped |
| **FAISS** | Vector similarity search for knowledge retrieval (RAG) | Knowledge base only |

> [!IMPORTANT]
> FAISS is **not** a transactional database. Redis is **not** a replacement for SQLite. Each store has a clearly separated responsibility.

---

## Setup

### Prerequisites

- **Python 3.11+**
- **Groq API key** — [console.groq.com](https://console.groq.com)
- **Redis** *(optional — in-memory fallback is automatic)*

### Installation

```bash
# Clone the repository
git clone https://github.com/Rohit1x52/BuyQK-Chatbot.git
cd BuyQK-Chatbot

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=1024
```

> [!CAUTION]
> Never commit your `.env` file. It is already included in `.gitignore`.

---

## Usage

### Start the Backend

```bash
cd backend
uvicorn main:app --reload
```

| Resource | URL |
|---|---|
| API Server | `http://127.0.0.1:8000` |
| Swagger Docs | `http://127.0.0.1:8000/docs` |
| Health Check | `http://127.0.0.1:8000/health` |

### API Endpoint

**`POST /chat`**

```json
{
  "message": "Find Amul milk",
  "user_id": 1,
  "session_id": "session-abc-123"
}
```

**Response:**

```json
{
  "session_id": "session-abc-123",
  "response": "I found Amul Toned Milk (1L) for ₹27. Would you like to order?",
  "intent": "product_search",
  "metadata": { "products": [...] }
}
```

---

## Testing

Run tests from the **project root**:

```bash
# Backend services
python -m backend.tests.test_services

# AI graph execution
python -m ai_engine.tests.test_graph

# Full AI + backend integration
python -m ai_engine.tests.test_integration

# Chat API end-to-end
python -m backend.tests.test_chat_api
```

**LLM tests** *(require a valid Groq API key — makes real API calls):*

```bash
python -m ai_engine.tests.test_llm
python -m ai_engine.tests.test_intent_llm
python -m ai_engine.tests.test_entity_llm
python -m ai_engine.tests.test_response_llm
```

---

## Design Principles

| Principle | Description |
|---|---|
| **Backend is the source of truth** | The LLM understands intent; the backend executes and validates. The AI never invents prices, stock, or order data. |
| **AI orchestrates, backend executes** | LangGraph controls *what* happens. Services determine *whether* and *how* it happens. |
| **Separation of concerns** | API routes → services → database. AI pipeline → tool node → services. No shortcuts. |
| **No hallucination** | If information is unavailable, the AI asks the user — it never fabricates data. |
| **Graceful degradation** | Redis unavailable? In-memory fallback. LLM API error? Deterministic keyword heuristics. |

---

<p align="center">
  <sub>Made by <strong>Rohit Ranjan Kumar</strong></sub>
</p>