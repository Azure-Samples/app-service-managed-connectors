targetScope = 'subscription'

extension microsoftGraphV1

@minLength(1)
@maxLength(40)
param environmentName string
param location string
@allowed(['dotnet', 'javascript', 'typescript', 'python'])
param sampleLanguage string
param createConnectorNamespace bool = true
param serviceManagementReference string = ''
param testSubjectPrefix string = '[connector-pivots]'

var suffix = take(uniqueString(subscription().id, environmentName, sampleLanguage), 10)
var tags = {
  'azd-env-name': environmentName
  purpose: 'managed-connector-documentation-validation'
}
var configurations = {
  dotnet: { runtime: 'DOTNETCORE|10.0', startup: '' }
  javascript: { runtime: 'NODE|24-lts', startup: 'npm start' }
  typescript: { runtime: 'NODE|24-lts', startup: 'npm start' }
  python: { runtime: 'PYTHON|3.14', startup: 'python -m uvicorn main:app --host 0.0.0.0 --port 8000' }
}
var configuration = configurations[sampleLanguage]

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-${environmentName}-${sampleLanguage}'
  location: location
  tags: tags
}

module plan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: 'app-service-plan'
  scope: rg
  params: {
    name: 'plan-${suffix}'
    location: location
    tags: tags
    skuName: 'B1'
    skuCapacity: 1
    reserved: true
  }
}

module triggerIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: 'trigger-identity'
  scope: rg
  params: {
    name: 'id-trigger-${suffix}'
    location: location
    tags: tags
  }
}

module namespace './namespace.bicep' = {
  name: 'connector-namespace'
  scope: rg
  params: {
    name: 'cg-${suffix}'
    location: location
    tags: tags
    triggerIdentityId: triggerIdentity.outputs.resourceId
    createNamespace: createConnectorNamespace
  }
}

module app './app.bicep' = {
  name: 'app-${sampleLanguage}'
  scope: rg
  params: {
    name: 'app-${sampleLanguage}-${suffix}'
    location: location
    tags: union(tags, { 'azd-service-name': sampleLanguage })
    planId: plan.outputs.resourceId
    runtime: configuration.runtime
    startup: configuration.startup
    connectionRuntimeUrl: namespace.outputs.connectionRuntimeUrl
    triggerPrincipalId: triggerIdentity.outputs.principalId
    testSubjectPrefix: testSubjectPrefix
    serviceManagementReference: serviceManagementReference
  }
}

module policies './policies.bicep' = {
  name: 'connection-access'
  scope: rg
  params: {
    namespaceName: namespace.outputs.name
    connectionName: namespace.outputs.connectionName
    triggerPrincipalId: triggerIdentity.outputs.principalId
    principalIds: [app.outputs.principalId]
  }
}

output AZURE_RESOURCE_GROUP string = rg.name
output CONNECTOR_NAMESPACE string = namespace.outputs.name
output OFFICE365_CONNECTION_NAME string = namespace.outputs.connectionName
output OFFICE365_CONNECTION_RUNTIME_URL string = namespace.outputs.connectionRuntimeUrl
output TRIGGER_IDENTITY_ID string = triggerIdentity.outputs.resourceId
output TEST_SUBJECT_PREFIX string = testSubjectPrefix
output APPLICATION object = {
  language: sampleLanguage
  name: app.outputs.name
  url: app.outputs.url
  audience: app.outputs.audience
  clientId: app.outputs.clientId
}
