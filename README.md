# Interactive Digital Twin CV

**Live site: [dimangulov.space](https://dimangulov.space/)**

A web-based interactive résumé where a photorealistic digital twin (via LiveAvatar.com WebRTC stream) answers questions about the candidate. The AI "brain" is a local LLM (Ollama) orchestrated by LangChain with a RAG pipeline backed by Qdrant.

---

## Architecture Overview

```
Browser (Next.js)  ─── REST ──►  FastAPI Backend  ─── LangChain ──►  Ollama (local)
        │                               │                                    │
        │ WebRTC                        └── Qdrant (Docker)  ◄──── embeddings┘
        │
LiveAvatar.com
```

See [DESIGN.md](./DESIGN.md) for the full C4 architecture document.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | ≥ 20 | https://nodejs.org |
| pnpm | ≥ 9 | `npm i -g pnpm` |
| Python | ≥ 3.11 | https://python.org |
| Docker Desktop | latest | https://docker.com |
| Ollama | latest | https://ollama.com |

---

## Quick Start

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd aicv
```

### 2. Start Qdrant (Docker)

```bash
docker compose up -d
```

Qdrant REST API will be available at `http://localhost:6333`.  
The Qdrant dashboard is available at `http://localhost:6333/dashboard`.

### 3. Pull Ollama models

```bash
# LLM for chat/generation
ollama pull llama3.2

# Embedding model for RAG
ollama pull nomic-embed-text
```

Verify both are available:
```bash
ollama list
```

### 4. Set up the FastAPI backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `backend/.env`:
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
EMBED_MODEL=nomic-embed-text
QDRANT_URL=http://localhost:6333
USE_IN_MEMORY_QDRANT=true
LIVEAVATAR_API_KEY=           # Leave empty for mock avatar
LIVEAVATAR_AVATAR_ID=default
ALLOWED_ORIGINS=http://localhost:3000
```

> **Tip:** Set `USE_IN_MEMORY_QDRANT=true` for the POC. This stores vectors in RAM and does not require the Docker Qdrant instance. Set to `false` to use persistent Qdrant.

Start the backend:
```bash
uvicorn main:app --reload --port 8000
```

The API documentation is at `http://localhost:8000/docs`.

### 5. Set up the Next.js frontend

```bash
cd frontend

# Install dependencies
pnpm install

# Copy environment file
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS/Linux
```

Edit `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:
```bash
pnpm dev
```

Open `http://localhost:3000`.

---

## Project Structure

```
aicv/
├── DESIGN.md                    ← Full architecture design document
├── README.md                    ← This file
├── docker-compose.yml           ← Qdrant (+ optional Ollama)
│
├── backend/
│   ├── main.py                  ← FastAPI app + RAG chain
│   ├── bio.txt                  ← CV knowledge base (edit this!)
│   ├── requirements.txt         ← Python dependencies
│   └── .env.example             ← Environment variable template
│
└── frontend/
    ├── app/
    │   ├── layout.tsx           ← Root layout + metadata
    │   ├── page.tsx             ← Main page, state management
    │   └── globals.css          ← Tailwind base + custom scrollbar
    ├── components/
    │   ├── VideoPlayer.tsx      ← WebRTC avatar player
    │   ├── ChatInterface.tsx    ← Push-to-Talk + text input
    │   ├── DevConsole.tsx       ← Live log panel
    │   └── ArchitectureSection.tsx  ← C4 diagram visualization
    ├── hooks/
    │   └── useSpeechRecognition.ts  ← webkitSpeechRecognition hook
    ├── lib/
    │   └── api.ts               ← Typed fetch wrappers
    ├── types/
    │   └── index.ts             ← Shared TypeScript interfaces
    └── .env.local.example       ← Frontend env template
```

---

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ask` | Submit a question, get a RAG-grounded answer |
| `GET` | `/session` | Get a LiveAvatar WebRTC session (mock or real) |
| `GET` | `/health` | Check Ollama and Qdrant connectivity |
| `GET` | `/docs` | Interactive Swagger UI |

---

## LiveAvatar Integration

The POC runs in **mock mode** when `LIVEAVATAR_API_KEY` is empty:
- A canvas-based animated placeholder is displayed in the video panel
- The `/session` endpoint returns a mock session object

To enable the real avatar:
1. Sign up at [https://liveavatar.com](https://liveavatar.com)
2. Create an avatar and note your `avatar_id`
3. Copy your API key into `LIVEAVATAR_API_KEY` in `backend/.env`
4. Set `LIVEAVATAR_AVATAR_ID` to your avatar ID
5. Complete the SDP exchange in `frontend/components/VideoPlayer.tsx`  
   (see the `// TODO: exchange SDP with LiveAvatar` comment)

---

## Customizing the CV

Edit `backend/bio.txt` with the candidate's real information. The file is chunked and embedded at startup — restart the FastAPI server after any changes.

For production, replace `bio.txt` with a structured JSON document and update the loader in `main.py` to use `langchain_community.document_loaders.JSONLoader`.

---

## Running Ollama in Docker (Optional)

If you prefer to run Ollama inside Docker instead of installing it locally, uncomment the `ollama` service in `docker-compose.yml`:

```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama_models:/root/.ollama
```

Then set `OLLAMA_BASE_URL=http://localhost:11434` in `backend/.env`.

After starting, pull models via:
```bash
docker exec -it aicv-ollama-1 ollama pull llama3.2
docker exec -it aicv-ollama-1 ollama pull nomic-embed-text
```

---

## Azure Deployment

The stack is designed to run on **Azure** with a ~$8–13/month budget.

```
Azure Static Web Apps (Free)  ──REST──►  Azure Container Apps (consumption)
                                               ├── Azure OpenAI (gpt-4o-mini)
                                               └── Qdrant Cloud (free tier)
```

### Services used

| Service | Tier | Est. monthly cost |
|---------|------|------------------|
| Azure Static Web Apps | Free | $0 |
| Azure Container Apps | Consumption (scales to 0) | ~$2–5 |
| Azure Container Registry | Basic | ~$5 |
| Azure OpenAI (gpt-4o-mini + embed-3-small) | Pay-per-use | ~$1–3 |
| Qdrant Cloud | Free 1-cluster | $0 |
| Log Analytics | First 5 GB free | $0 |
| **Total** | | **~$8–13** |

### Prerequisites

| Tool | Install |
|------|---------|
| Azure CLI | https://learn.microsoft.com/en-us/cli/azure/install-azure-cli |
| Azure subscription | https://azure.microsoft.com/free |
| Qdrant Cloud account | https://cloud.qdrant.io (free tier) |

### Step 1 — Create a Qdrant Cloud cluster

1. Sign up at [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create a **Free** cluster in the Azure region closest to you
3. Note the cluster **URL** (e.g. `https://abc123.azure.qdrant.io:6333`) and generate an **API key**

### Step 2 — Provision Terraform remote state storage (bootstrap, one-time)

A dedicated Bootstrap Terraform configuration in `infra/terraform/bootstrap/` creates the storage account. Its own state is stored locally (the classic chicken-and-egg bootstrap pattern).

```bash
cd infra/terraform/bootstrap

# Authenticate
az login

# Apply (creates resource group + storage account + blob container)
terraform init
terraform apply

# Note the storage account name from the output
terraform output storage_account_name
# e.g. aicvtfstatea3f9b1
```

The bootstrap local state (`bootstrap/terraform.tfstate`) is gitignored. Store it safely (e.g. in a password manager or team secrets vault).

### Step 3 — Deploy Azure infrastructure with Terraform

```bash
cd infra/terraform

# Copy example vars (non-sensitive values only)
cp terraform.tfvars.example terraform.tfvars

# Initialise — provide the storage account name from bootstrap output
terraform init \
  -backend-config="storage_account_name=<output-from-bootstrap>" \
  -backend-config="resource_group_name=rg-aicv-tfstate"

# Preview, then apply (sensitive vars passed as flags, not in files)
terraform plan \
  -var="qdrant_cloud_url=https://your-cluster.azure.qdrant.io:6333" \
  -var="qdrant_cloud_api_key=<key>" \
  -var="live_avatar_api_key=<key>"   # omit for mock avatar

terraform apply \
  -var="qdrant_cloud_url=https://your-cluster.azure.qdrant.io:6333" \
  -var="qdrant_cloud_api_key=<key>" \
  -var="live_avatar_api_key=<key>"
```

Note the outputs:
```bash
terraform output                               # all non-sensitive outputs
terraform output -raw static_web_app_api_key  # SWA deploy token (sensitive)
```

### Step 4 — Set up GitHub Actions CI/CD

**Configure OIDC federated credentials** (no stored service principal secrets):
```bash
az ad app create --display-name "aicv-github-oidc"
# Follow: https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect
```

**Add GitHub repository secrets** (`Settings → Secrets and variables → Actions`):

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `TF_STATE_STORAGE_ACCOUNT` | Storage account name from bootstrap output |
| `QDRANT_CLOUD_URL` | `https://your-cluster.azure.qdrant.io:6333` |
| `QDRANT_CLOUD_API_KEY` | Qdrant Cloud API key |
| `LIVEAVATAR_API_KEY` | LiveAvatar key (or leave empty for mock) |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | From `terraform output -raw static_web_app_api_key` |

### Step 5 — Push to deploy

```bash
git push origin main
```

The pipeline runs 4 jobs in sequence:
1. **Terraform Apply** — provisions / updates all Azure infrastructure
2. **Build Backend** — Docker build → push to ACR (ACR name from TF outputs)
3. **Deploy Backend** — updates Container App revision (app name from TF outputs)
4. **Deploy Frontend** — Next.js static export → Azure Static Web Apps

### Dual-Mode: Testing Azure OpenAI locally

To test against Azure OpenAI from your local machine without deploying:

```bash
# backend/.env
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://aicv-prod-aoai.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>       # Get from Azure portal → Keys and Endpoint
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_EMBED_DEPLOYMENT=text-embedding-3-small

QDRANT_MODE=cloud
QDRANT_CLOUD_URL=https://your-cluster.azure.qdrant.io:6333
QDRANT_CLOUD_API_KEY=<qdrant-api-key>
```

Then start the backend as usual:
```bash
uvicorn main:app --reload --port 8000
```

On **Azure Container Apps**, `AZURE_OPENAI_API_KEY` is intentionally left empty — the backend authenticates via the User-Assigned Managed Identity, which has the `Cognitive Services User` role on the Azure OpenAI resource. No API key is stored anywhere.

---

## Development Notes

- **Speech recognition** requires Chrome or Edge; Firefox is not supported by `webkitSpeechRecognition`.
- **WebRTC** video only works over HTTPS in production. Use `localhost` for development.
- **First startup** may be slow — Ollama loads the model into VRAM on the first request.
- **In-memory Qdrant** data is lost on backend restart; this is intentional for the POC.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, Tailwind CSS, Lucide-react |
| Backend | FastAPI, Python 3.12, Uvicorn |
| AI Orchestration | LangChain LCEL, langchain-ollama, langchain-community |
| LLM Runtime | Ollama (llama3.2 + nomic-embed-text) |
| Vector Database | Qdrant (Docker / in-memory) |
| Avatar Stream | LiveAvatar.com WebRTC |
| Speech Input | Web Speech API (client-side) |
| Infrastructure | Docker Compose |

---

## Operations

Rollback procedure, Phase 2 key-rotation procedure, and the sandbox-behavior
baseline: see [docs/rollback.md](./docs/rollback.md).
