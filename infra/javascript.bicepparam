using './main.bicep'

param sampleLanguage = 'javascript'
param environmentName = readEnvironmentVariable('AZURE_ENV_NAME')
param location = readEnvironmentVariable('AZURE_LOCATION')
param serviceManagementReference = readEnvironmentVariable('SERVICE_MANAGEMENT_REFERENCE', '')
param createConnectorNamespace = bool(readEnvironmentVariable('CREATE_CONNECTOR_NAMESPACE', 'true'))
