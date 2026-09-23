param namespaceName string
param connectionName string
param principalIds array
param triggerPrincipalId string

resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' existing = {
  name: '${namespaceName}/${connectionName}'
}

resource access 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = [for principalId in concat([triggerPrincipalId], principalIds): {
  parent: connection
  name: principalId
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: {
        objectId: principalId
        tenantId: tenant().tenantId
      }
    }
  }
}]
