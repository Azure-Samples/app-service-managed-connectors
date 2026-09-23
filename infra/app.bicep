extension microsoftGraphV1

param name string
param location string
param tags object
param planId string
param runtime string
param startup string
param connectionRuntimeUrl string
param triggerPrincipalId string
param testSubjectPrefix string
param serviceManagementReference string

module identity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: '${name}-identity'
  params: {
    name: 'id-${name}'
    location: location
    tags: tags
  }
}

var audience = 'api://${name}'
resource registration 'Microsoft.Graph/applications@v1.0' = {
  uniqueName: name
  displayName: 'Connector validation - ${name}'
  signInAudience: 'AzureADMyOrg'
  identifierUris: [audience]
  serviceManagementReference: !empty(serviceManagementReference) ? serviceManagementReference : null
  api: { requestedAccessTokenVersion: 2 }
  web: {
    redirectUris: ['https://${name}.azurewebsites.net/.auth/login/aad/callback']
  }
}
resource servicePrincipal 'Microsoft.Graph/servicePrincipals@v1.0' = {
  appId: registration.appId
}
resource federation 'Microsoft.Graph/applications/federatedIdentityCredentials@v1.0' = {
  name: '${registration.uniqueName}/web-app-managed-identity'
  audiences: ['api://AzureADTokenExchange']
  issuer: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'
  subject: identity.outputs.principalId
}

module site 'br/public:avm/res/web/site:0.22.0' = {
  name: '${name}-site'
  params: {
    name: name
    location: location
    tags: tags
    kind: 'app,linux'
    serverFarmResourceId: planId
    httpsOnly: true
    managedIdentities: { userAssignedResourceIds: [identity.outputs.resourceId] }
    siteConfig: {
      linuxFxVersion: runtime
      appCommandLine: startup
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: {
          AZURE_CLIENT_ID: identity.outputs.clientId
          OFFICE365_CONNECTION_RUNTIME_URL: connectionRuntimeUrl
          TEST_SUBJECT_PREFIX: testSubjectPrefix
          SCM_DO_BUILD_DURING_DEPLOYMENT: startsWith(runtime, 'DOTNETCORE|') ? 'false' : 'true'
          OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID: identity.outputs.clientId
        }
      }
      {
        name: 'authsettingsV2'
        properties: {
          platform: { enabled: true, runtimeVersion: '~1' }
          globalValidation: {
            requireAuthentication: true
            unauthenticatedClientAction: 'Return401'
          }
          httpSettings: { requireHttps: true }
          identityProviders: {
            azureActiveDirectory: {
              enabled: true
              registration: {
                openIdIssuer: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0'
                clientId: registration.appId
                clientSecretSettingName: 'OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID'
              }
              validation: {
                allowedAudiences: [registration.appId, audience]
                defaultAuthorizationPolicy: {
                  allowedPrincipals: { identities: [triggerPrincipalId] }
                }
              }
            }
          }
          login: { tokenStore: { enabled: false } }
        }
      }
    ]
  }
}

resource logs 'Microsoft.Web/sites/config@2024-11-01' = {
  name: '${name}/logs'
  properties: {
    applicationLogs: { fileSystem: { level: 'Information' } }
    httpLogs: {
      fileSystem: { enabled: true, retentionInDays: 3, retentionInMb: 35 }
    }
  }
  dependsOn: [site]
}

output name string = name
output url string = 'https://${name}.azurewebsites.net'
output audience string = audience
output principalId string = identity.outputs.principalId
output clientId string = registration.appId
