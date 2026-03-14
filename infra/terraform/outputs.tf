output "backend_url" {
  description = "HTTPS URL of the FastAPI backend Container App."
  value       = "https://${azurerm_container_app.backend.latest_revision_fqdn}"
}

output "frontend_url" {
  description = "HTTPS URL of the Azure Static Web Apps frontend."
  value       = "https://${azurerm_static_web_app.frontend.default_host_name}"
}

output "acr_login_server" {
  description = "Azure Container Registry login server (used in GitHub Actions for docker push)."
  value       = azurerm_container_registry.acr.login_server
}

output "acr_name" {
  description = "Short name of the Azure Container Registry (used in az acr login)."
  value       = azurerm_container_registry.acr.name
}

output "openai_endpoint" {
  description = "Azure OpenAI service endpoint."
  value       = azurerm_cognitive_account.openai.endpoint
}

output "container_app_name" {
  description = "Name of the backend Container App (used by the deploy GitHub Action)."
  value       = azurerm_container_app.backend.name
}

output "resource_group_name" {
  description = "Resource group containing all deployed resources."
  value       = azurerm_resource_group.rg.name
}

output "static_web_app_api_key" {
  description = "SWA deployment API key — store as AZURE_STATIC_WEB_APPS_API_TOKEN in GitHub secrets."
  value       = azurerm_static_web_app.frontend.api_key
  sensitive   = true
}
