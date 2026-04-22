variable "environment_suffix" {
  description = "Short label appended to every resource name (dev | prod)."
  type        = string
  default     = "prod"
}

variable "resource_group_name" {
  description = "Name of the Azure Resource Group to create."
  type        = string
  default     = "rg-aicv-prod"
}

variable "location" {
  description = "Primary Azure region for most resources."
  type        = string
  default     = "northeurope"
}

variable "openai_location" {
  description = "Azure region for Azure OpenAI (availability is limited)."
  type        = string
  default     = "swedencentral"
  validation {
    condition = contains(
      ["eastus", "eastus2", "westus", "westeurope", "swedencentral", "australiaeast", "japaneast"],
      var.openai_location
    )
    error_message = "Azure OpenAI is not available in that region. Choose from: eastus, eastus2, westus, westeurope, swedencentral, australiaeast, japaneast."
  }
}



variable "qdrant_cloud_url" {
  description = "Qdrant Cloud cluster HTTPS URL (e.g. https://xyz.azure.qdrant.io:6333)."
  type        = string
  sensitive   = true
}

variable "qdrant_cloud_api_key" {
  description = "Qdrant Cloud API key."
  type        = string
  sensitive   = true
}

variable "azure_openai_api_key" {
  description = "Azure OpenAI API key. Leave empty to use Managed Identity (recommended on Container Apps)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "live_avatar_api_key" {
  description = "LiveAvatar.com API key. Leave empty to enable canvas mock avatar mode."
  type        = string
  sensitive   = true
  default     = ""
}

variable "live_avatar_avatar_id" {
  description = "LiveAvatar avatar ID (UUID). Set via TF_VAR_live_avatar_avatar_id or LIVEAVATAR_AVATAR_ID GitHub Actions variable."
  type        = string
  default     = "dd73ea75-1218-4ef3-92ce-606d5f7fbc0a"
  validation {
    condition     = can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.live_avatar_avatar_id))
    error_message = "live_avatar_avatar_id must be a valid UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)."
  }
}

variable "live_avatar_is_sandbox" {
  description = "LiveAvatar sandbox mode flag (free tier). Set via TF_VAR_live_avatar_is_sandbox or LIVE_AVATAR_IS_SANDBOX GitHub Actions variable."
  type        = bool
  default     = true
}

variable "live_avatar_session_mode" {
  description = "LiveAvatar session mode. Set via TF_VAR_live_avatar_session_mode or LIVE_AVATAR_SESSION_MODE GitHub Actions variable."
  type        = string
  default     = "LITE"
  validation {
    condition     = contains(["LITE", "FULL", "CUSTOM"], var.live_avatar_session_mode)
    error_message = "live_avatar_session_mode must be one of: LITE, FULL, CUSTOM."
  }
}

variable "enable_container_apps" {
  description = "Deploy the Container Apps Environment and backend Container App. Set false to skip (saves cost during development)."
  type        = bool
  default     = true
}
