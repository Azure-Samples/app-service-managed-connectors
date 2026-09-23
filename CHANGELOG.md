# Changelog

## Single-language deployment

- Each language folder is now an independent AZD project that provisions one
  app, two managed identities, one Entra registration, and one connector trigger.
- Shared infrastructure takes a required language parameter; trigger creation,
  live verification, and cleanup instructions target only the chosen app.
- Existing four-app environments are not automatically removed or migrated.

## Initial preview samples

- Equivalent C#, JavaScript, TypeScript, and Python Outlook trigger/action samples.
- Shared Bicep and Azure Developer CLI deployment with managed identities and
  App Service authentication.
- Local unit and HTTP smoke checks, CI, and opt-in live verification.
