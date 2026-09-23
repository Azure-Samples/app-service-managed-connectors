targetScope = 'subscription'

extension microsoftGraphV1

@minLength(1)
@maxLength(40)
param environmentName string
param location string
param createConnectorNamespace bool = true
param serviceManagementReference string = ''
param testSubjectPrefix string = '[connector-pivots]'

var suffix = take(uniqueString(subscription().id, environmentName), 10)
var tags = {
  'azd-env-name': environmentName
  purpose: 'managed-connector-documentation-validation'
}
var languages = [
  { name: 'dotnet', runtime: 'DOTNETCORE|10.0', startup: '' }
  { name: 'javascript', runtime: 'NODE|24-lts', startup: 'npm start' }
  { name: 'typescript', runtime: 'NODE|24-lts', startup: 'npm start' }
  { name: 'python', runtime: 'PYTHON|3.14', startup: 'python -m uvicorn main:app --host 0.0.0.0 --port 8000' }
]

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-${environmentName}'
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

module apps './app.bicep' = [for lang in languages: {
  name: 'app-${lang.name}'
  scope: rg
  params: {
    name: 'app-${lang.name}-${suffix}'
    location: location
    tags: union(tags, { 'azd-service-name': lang.name })
    planId: plan.outputs.resourceId
    runtime: lang.runtime
    startup: lang.startup
    connectionRuntimeUrl: namespace.outputs.connectionRuntimeUrl
    triggerPrincipalId: triggerIdentity.outputs.principalId
    testSubjectPrefix: testSubjectPrefix
    serviceManagementReference: serviceManagementReference
  }
}]

module policies './policies.bicep' = {
  name: 'connection-access'
  scope: rg
  params: {
    namespaceName: namespace.outputs.name
    connectionName: namespace.outputs.connectionName
    triggerPrincipalId: triggerIdentity.outputs.principalId
    principalIds: [for (lang, i) in languages: apps[i].outputs.principalId]
  }
}

output AZURE_RESOURCE_GROUP string = rg.name
output CONNECTOR_NAMESPACE string = namespace.outputs.name
output OFFICE365_CONNECTION_NAME string = namespace.outputs.connectionName
output OFFICE365_CONNECTION_RUNTIME_URL string = namespace.outputs.connectionRuntimeUrl
output TRIGGER_IDENTITY_ID string = triggerIdentity.outputs.resourceId
output TEST_SUBJECT_PREFIX string = testSubjectPrefix
output APPLICATIONS array = [for (lang, i) in languages: {
  language: lang.name
  name: apps[i].outputs.name
  url: apps[i].outputs.url
  audience: apps[i].outputs.audience
  clientId: apps[i].outputs.clientId
}]
