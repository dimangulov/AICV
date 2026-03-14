terraform {
  required_version = ">= 1.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116"
    }
  }

  # Remote state — stored in Azure Blob Storage (provisioned by infra/terraform/bootstrap/).
  #
  # One-time bootstrap:
  #   cd infra/terraform/bootstrap
  #   terraform init && terraform apply
  #   terraform output storage_account_name   # copy this value
  #
  # Then fill in storage_account_name below and run:
  #   cd .. && terraform init
  #
  # All other values are passed as -backend-config flags in CI (see deploy-azure.yml).
  # storage_account_name is intentionally left out here so the same versions.tf works
  # for every environment — the value is injected by CI via TF_STATE_STORAGE_ACCOUNT secret.
  backend "azurerm" {
    resource_group_name  = "rg-aicv-tfstate"
    container_name       = "tfstate"
    key                  = "prod.terraform.tfstate"
    # storage_account_name is supplied at init time:
    #   locally:  terraform init -backend-config="storage_account_name=<value>"
    #   in CI:    injected via -backend-config in the workflow
    use_oidc = true   # OIDC auth in CI; falls back to az login / env vars locally
  }
}

provider "azurerm" {
  features {}
  # Local dev:  az login
  # CI/CD:      OIDC — set ARM_CLIENT_ID, ARM_TENANT_ID,
  #             ARM_SUBSCRIPTION_ID, ARM_USE_OIDC=true as env vars in workflow
}
