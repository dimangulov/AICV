terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # Bootstrap uses local state — this is intentional.
  # The state file for the state-store itself must live locally (chicken-and-egg).
  # Commit bootstrap/terraform.tfstate to a secure location or use a pre-existing
  # storage account. For most teams: run once, store output values in a password manager.
}

provider "azurerm" {
  features {}
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "location" {
  description = "Azure region for the state-store resources."
  type        = string
  default     = "westeurope"
}

variable "environment_suffix" {
  description = "Matches the suffix used in the main Terraform workspace."
  type        = string
  default     = "prod"
}

# ── Random suffix to ensure globally unique storage account name ──────────────
# Storage account names: 3–24 chars, lowercase alphanumeric only, globally unique.

resource "random_id" "sa_suffix" {
  byte_length = 3 # 6 hex chars
}

locals {
  tags = {
    project     = "digital-twin-cv"
    environment = var.environment_suffix
    managed_by  = "terraform-bootstrap"
  }
  sa_name = "aicvtfstate${random_id.sa_suffix.hex}" # e.g. aicvtfstatea3f9b1
}

# ── Resource group ─────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-aicv-tfstate"
  location = var.location
  tags     = local.tags
}

# ── Storage account ────────────────────────────────────────────────────────────
# Hardened: public blob access off, HTTPS only, TLS 1.2+, versioning on,
# soft-delete (90 days) so accidental state deletion is recoverable.

resource "azurerm_storage_account" "tfstate" {
  name                     = local.sa_name
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # Security hardening
  https_traffic_only_enabled      = true
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true # required for Terraform AzureRM backend

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 90 # Recover accidentally deleted state blobs
    }

    container_delete_retention_policy {
      days = 30
    }
  }

  tags = local.tags
}

# ── Blob container ─────────────────────────────────────────────────────────────

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}

# ── Lock state blobs during operations (requires Contributor on the SA) ────────
# The azurerm backend uses blob leases natively — no extra resource needed.

# ── Outputs — paste these into versions.tf backend block ──────────────────────

output "resource_group_name" {
  description = "Resource group holding the Terraform state storage account."
  value       = azurerm_resource_group.tfstate.name
}

output "storage_account_name" {
  description = "Paste into backend.storage_account_name and TF_STATE_STORAGE_ACCOUNT secret."
  value       = azurerm_storage_account.tfstate.name
}

output "container_name" {
  description = "Blob container name for the backend block."
  value       = azurerm_storage_container.tfstate.name
}

output "backend_config_snippet" {
  description = "Ready-to-paste backend block for versions.tf."
  value       = <<-EOT
    backend "azurerm" {
      resource_group_name  = "${azurerm_resource_group.tfstate.name}"
      storage_account_name = "${azurerm_storage_account.tfstate.name}"
      container_name       = "${azurerm_storage_container.tfstate.name}"
      key                  = "prod.terraform.tfstate"
    }
  EOT
}
