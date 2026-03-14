workspace "Digital Twin CV" "AI-powered interactive portfolio by Damir Imangulov" {

    model {
        visitor = person "Recruiter / Visitor" "Explores the interactive digital twin CV portfolio"

        digitalTwin = softwareSystem "Digital Twin CV" "AI-powered interactive portfolio. A photorealistic WebRTC avatar answers natural-language questions via a RAG pipeline over a curated CV knowledge base." {

            frontend = container "Next.js Frontend" "TypeScript / React 19" "Browser / Vercel" {
                tags "Browser"
                videoPlayer     = component "VideoPlayer"          "React Component"       "Manages the LiveKit WebRTC room and renders the avatar video stream. Falls back to a mock canvas stream in local-dev mode."
                chatUI          = component "ChatInterface"        "React Component"       "Handles text input and push-to-talk via the Web Speech API. Calls POST /ask on submit."
                devConsole      = component "DevConsole"           "React Component"       "Real-time log panel exposing each RAG pipeline step (retrieve, embed, infer)."
                speechHook      = component "useSpeechRecognition" "React Hook"            "Wraps the browser Web Speech API; provides transcript and listening state."
                apiClient       = component "API Client"           "TypeScript / fetch"    "Typed wrapper around /ask, /session, /health, and /speak endpoints."
            }

            backend = container "FastAPI Backend" "Python 3.12" "Docker / Azure Container Apps" {
                askEndpoint     = component "/ask Endpoint"        "FastAPI Route"         "Input validation (Pydantic), invokes RAG chain, returns answer + source chunks + latency_ms."
                sessionEndpoint = component "/session Endpoint"    "FastAPI Route"         "Proxies LiveAvatar.com session creation; injects LIVEAVATAR_API_KEY from env — key never exposed to browser."
                healthEndpoint  = component "/health Endpoint"     "FastAPI Route"         "Checks Qdrant and Ollama reachability; reports RAG chain initialisation state."
                speakEndpoint   = component "/speak Endpoint"      "FastAPI Route"         "Forwards text to LiveAvatar TTS endpoint to trigger avatar lip-sync."
                ragChain        = component "RAG Chain"            "LangChain LCEL"        "Composes: question -> retriever | format_docs -> ChatPromptTemplate -> LLM -> StrOutputParser."
                llmFactory      = component "LLM Provider Factory" "Python"                "Reads LLM_PROVIDER env var; returns ChatOllama (local dev) or AzureChatOpenAI (cloud deploy)."
                embedFactory    = component "Embeddings Factory"   "Python"                "Reads LLM_PROVIDER; returns OllamaEmbeddings or AzureOpenAIEmbeddings."
                vectorStoreMgr  = component "Vector Store Manager" "Qdrant Client"         "On startup: loads bio.txt, splits into 500-token chunks (50-token overlap), embeds, upserts to Qdrant."
                avatarProxy     = component "LiveAvatar Proxy"     "httpx"                 "Stateless HTTP proxy. Injects auth headers server-side; credentials never logged or forwarded to browser."
            }

            qdrant = container "Qdrant Vector DB" "Stores the cv_knowledge_base collection — 768-dimensional cosine-similarity vectors chunked from bio.txt." "Docker" {
                tags "Database"
            }
        }

        ollama     = softwareSystem "Ollama"          "Local LLM runtime. Serves llama3.2 (3B) for chat completion and nomic-embed-text for 768-dim embeddings. All inference stays on-device — no CV data leaves the machine." "External Software"
        liveAvatar = softwareSystem "LiveAvatar.com"  "Commercial SaaS. Provides photorealistic digital-twin avatar streaming via a hosted LiveKit room (WebRTC / H.264 video / Opus audio)." "External Software"
        liveKit    = softwareSystem "LiveKit Cloud"   "Open-source WebRTC infrastructure used by LiveAvatar.com for signalling and media relay (ICE / STUN / TURN)." "External Software"

        # ── Person relationships ──────────────────────────────────────────────
        visitor -> digitalTwin    "Asks questions about the candidate" "HTTPS"
        visitor -> frontend       "Visits the portfolio and interacts" "HTTPS / WebRTC"

        # ── Container-level relationships ─────────────────────────────────────
        frontend -> backend       "REST API calls"                          "HTTP JSON"
        backend  -> qdrant        "Vector similarity search"                "HTTP / gRPC"
        backend  -> ollama        "Chat completion and embedding generation" "HTTP REST"
        backend  -> liveAvatar    "Session creation proxy"                  "HTTPS"
        frontend -> liveKit       "WebRTC signalling and media stream"      "WSS / SRTP"

        # ── Component-level relationships — Frontend ──────────────────────────
        videoPlayer  -> apiClient   "getSession()"
        chatUI       -> apiClient   "askQuestion(question)"
        chatUI       -> speechHook  "uses transcript"
        apiClient    -> backend     "HTTP fetch"

        # ── Component-level relationships — Backend ───────────────────────────
        askEndpoint     -> ragChain        "invoke(question)"
        ragChain        -> llmFactory      "createLLM()"
        ragChain        -> vectorStoreMgr  "retrieve(k=3)"
        vectorStoreMgr  -> embedFactory    "createEmbeddings()"
        vectorStoreMgr  -> qdrant          "similarity_search()"  "HTTP"
        llmFactory      -> ollama          "chat_completion()"    "HTTP"
        embedFactory    -> ollama          "embed_documents()"    "HTTP"
        sessionEndpoint -> avatarProxy     "proxy(request)"
        speakEndpoint   -> avatarProxy     "proxy(request)"
        avatarProxy     -> liveAvatar      "POST /session"        "HTTPS"
    }

    views {
        systemContext digitalTwin "L1_SystemContext" "Level 1 — System Context" {
            include *
            autoLayout lr
        }

        container digitalTwin "L2_Containers" "Level 2 — Container Diagram" {
            include *
            autoLayout lr
        }

        component frontend "L3_Frontend" "Level 3 — Next.js Frontend Components" {
            include *
            autoLayout lr
        }

        component backend "L3_Backend" "Level 3 — FastAPI Backend Components" {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                background #1d4ed8
                color #ffffff
                shape Person
            }
            element "Software System" {
                background #1e3a8a
                color #f1f5f9
            }
            element "Container" {
                background #1e3a8a
                color #f1f5f9
            }
            element "Component" {
                background #1e293b
                color #e2e8f0
            }
            element "Database" {
                shape Cylinder
                background #166534
                color #f0fdf4
            }
            element "Browser" {
                shape WebBrowser
            }
            element "External Software" {
                background #374151
                color #f9fafb
            }
            relationship "Relationship" {
                color #4b5563
            }
        }

        theme default
    }
}
