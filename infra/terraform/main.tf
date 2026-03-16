locals {
  prefix   = "aicv-${var.environment_suffix}"
  acr_name = "aicv${var.environment_suffix}acr" # ACR: alphanumeric only, 5–50 chars
  tags = {
    project     = "digital-twin-cv"
    environment = var.environment_suffix
    managed_by  = "terraform"
  }
}

# ── Resource Group ─────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

# ── Log Analytics Workspace (first 5 GB/month free) ───────────────────────────

resource "azurerm_log_analytics_workspace" "law" {
  name                = "${local.prefix}-law"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

# ── Azure Container Registry — Basic (~$5/month) ──────────────────────────────

resource "azurerm_container_registry" "acr" {
  name                = local.acr_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Basic"
  admin_enabled       = false # Authenticate via Managed Identity — no stored passwords
  tags                = local.tags
}

# ── User-Assigned Managed Identity for the backend ────────────────────────────

resource "azurerm_user_assigned_identity" "backend" {
  name                = "${local.prefix}-backend-id"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags
}

# ── RBAC: AcrPull — backend identity can pull images from ACR ─────────────────

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.backend.principal_id
}

# ── Azure OpenAI Service (pay-per-use) ────────────────────────────────────────

resource "azurerm_cognitive_account" "openai" {
  name                  = "${local.prefix}-aoai"
  location              = var.openai_location
  resource_group_name   = azurerm_resource_group.rg.name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "${local.prefix}-aoai"
  tags                  = local.tags
}

# gpt-4o-mini — cheapest capable chat model (~$0.15 / 1M input tokens)
resource "azurerm_cognitive_deployment" "chat" {
  name                 = "gpt-4o-mini"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4o-mini"
    version = "2024-07-18"
  }

  scale {
    type     = "GlobalStandard"
    capacity = 20 # 20 K tokens-per-minute
  }
}

# text-embedding-3-small — cheapest embeddings ($0.02 / 1M tokens)
# depends_on ensures only one deployment is created at a time within the account
resource "azurerm_cognitive_deployment" "embed" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.openai.id
  depends_on           = [azurerm_cognitive_deployment.chat]

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }

  scale {
    type     = "GlobalStandard"
    capacity = 120
  }
}

# ── RBAC: Cognitive Services User — keyless Azure OpenAI via Managed Identity ─

resource "azurerm_role_assignment" "cognitive_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_user_assigned_identity.backend.principal_id
}

# ── Azure Speech Services (TTS for avatar voice) ───────────────────────────────
# F0 = free (5 h neural TTS / month) — sufficient for a portfolio demo

resource "azurerm_cognitive_account" "speech" {
  name                = "${local.prefix}-speech"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  kind                = "SpeechServices"
  sku_name            = "F0"
  tags                = local.tags
}


resource "azurerm_static_web_app" "frontend" {
  name                = "${local.prefix}-swa"
  # SWA availability — westeurope is available and keeps deployment in Europe
  location            = "westeurope"
  resource_group_name = azurerm_resource_group.rg.name
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}

# ── Container Apps Environment (Consumption — scales to zero) ─────────────────

resource "azurerm_container_app_environment" "cae" {
  count                      = var.enable_container_apps ? 1 : 0
  name                       = "${local.prefix}-cae"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
  tags                       = local.tags
}

# ── Backend Container App ──────────────────────────────────────────────────────
# min_replicas=0 → scales to zero when idle; cold-start ~3–5 s (fine for a portfolio)

resource "azurerm_container_app" "backend" {
  count                        = var.enable_container_apps ? 1 : 0
  name                         = "${local.prefix}-backend"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.cae[0].id
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.backend.id]
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = azurerm_user_assigned_identity.backend.id
  }

  # ── Secrets — stored encrypted, never appear as plain env vars ───────────────
  secret {
    name  = "qdrant-url"
    value = var.qdrant_cloud_url
  }
  secret {
    name  = "qdrant-api-key"
    value = var.qdrant_cloud_api_key
  }
  secret {
    name  = "liveavatar-api-key"
    value = var.live_avatar_api_key
  }
  secret {
    name  = "speech-key"
    value = azurerm_cognitive_account.speech.primary_access_key
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8000
    transport                  = "http"
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 0
    max_replicas = 3

    container {
      name   = "backend"
      image  = "${azurerm_container_registry.acr.login_server}/aicv-backend:${var.backend_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      # ── AI provider ──────────────────────────────────────────────────────────
      env {
        name  = "LLM_PROVIDER"
        value = "azure_openai"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = "2024-08-01-preview"
      }
      env {
        name  = "AZURE_OPENAI_CHAT_DEPLOYMENT"
        value = azurerm_cognitive_deployment.chat.name
      }
      env {
        name  = "AZURE_OPENAI_EMBED_DEPLOYMENT"
        value = azurerm_cognitive_deployment.embed.name
      }
      # Empty string → Python DefaultAzureCredential uses the Managed Identity
      env {
        name  = "AZURE_OPENAI_API_KEY"
        value = ""
      }

      # ── Vector database ───────────────────────────────────────────────────────
      env {
        name  = "QDRANT_MODE"
        value = "cloud"
      }
      env {
        name        = "QDRANT_CLOUD_URL"
        secret_name = "qdrant-url"
      }
      env {
        name        = "QDRANT_CLOUD_API_KEY"
        secret_name = "qdrant-api-key"
      }

      # ── LiveAvatar ────────────────────────────────────────────────────────────
      env {
        name        = "LIVEAVATAR_API_KEY"
        secret_name = "liveavatar-api-key"
      }
      env {
        name  = "LIVEAVATAR_AVATAR_ID"
        value = var.live_avatar_avatar_id
      }

      # ── CORS: restrict to the Static Web App origin ───────────────────────────
      env {
        name  = "ALLOWED_ORIGINS"
        value = "https://${azurerm_static_web_app.frontend.default_host_name}"
      }

      # ── Azure Speech TTS ──────────────────────────────────────────────────────
      env {
        name        = "AZURE_SPEECH_KEY"
        secret_name = "speech-key"
      }
      env {
        name  = "AZURE_SPEECH_REGION"
        value = azurerm_resource_group.rg.location
      }
    }

    http_scale_rule {
      name                = "http-traffic"
      concurrent_requests = "10"
    }
  }

  depends_on = [
    azurerm_role_assignment.acr_pull,
    azurerm_role_assignment.cognitive_user,
  ]
}

