param name string
param location string
param tags object
param triggerIdentityId string
param createNamespace bool

resource newNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' = if (createNamespace) {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${triggerIdentityId}': {}
    }
  }
}

resource existingNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = if (!createNamespace) {
  name: name
}

resource outlook 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  name: '${name}/outlook-validation'
  properties: {
    connectorName: 'office365'
  }
  dependsOn: createNamespace ? [newNamespace] : [existingNamespace]
}

output name string = name
output connectionName string = 'outlook-validation'
output connectionRuntimeUrl string = outlook.properties.connectionRuntimeUrl
