# TypeScript / Express

Receive an Outlook event at `/api/webhook` and flag only test-prefix messages.

- [server.ts](server.ts): managed-identity client and server startup.
- [app.ts](app.ts): typed validation of untrusted JSON, routing, and filtering.
- Runtime: Node.js 24 with ES modules; strict TypeScript compilation and pinned
  `@azure/connectors@0.2.0-preview`.

From the repository root:

```bash
npm ci --prefix src/typescript
npm test --prefix src/typescript
```

The test command compiles the app before exercising it. Follow the shared
[setup and deployment instructions](../../README.md#deploy-to-azure) to provision
the authenticated app and its connector. After provisioning, deploy this
language with `azd deploy typescript --no-prompt`.

Use `ManagedIdentityTokenProvider` and `flagAsync(input, messageId)` with this SDK
version. Local tests replace the outbound action and do not implement Easy Auth.
See the shared [authentication model](../../README.md#architecture-and-authentication)
and [live verification steps](../../README.md#connect-outlook-and-create-triggers).
