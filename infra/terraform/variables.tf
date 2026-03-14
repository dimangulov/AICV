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
  default     = "westeurope"
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

variable "backend_image_tag" {
  description = "Backend Docker image tag to deploy to Container Apps."
  type        = string
  default     = "latest"
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
  description = "LiveAvatar avatar ID."
  type        = string
  default     = "default"
}

variable "enable_container_apps" {
  description = "Deploy the Container Apps Environment and backend Container App. Set false to skip (saves cost during development)."
  type        = bool
  default     = true
}
