import { ManagedIdentityTokenProvider } from "@azure/connectors";
import { Office365Client } from "@azure/connectors/generated/Office365Extensions";
import { createApp } from "./app.js";

function required(name) {
  const value = process.env[name];
  if (!value?.trim()) throw new Error(`Missing required setting: ${name}`);
  return value;
}

const runtimeUrl = new URL(required("OFFICE365_CONNECTION_RUNTIME_URL"));
if (runtimeUrl.protocol !== "https:") throw new Error("Connection URL must use HTTPS.");
const prefix = required("TEST_SUBJECT_PREFIX");
const client = new Office365Client(
  runtimeUrl.href,
  new ManagedIdentityTokenProvider(required("AZURE_CLIENT_ID")),
);
const app = createApp(
  id => client.flagAsync({ flag: { flagStatus: "flagged" } }, id),
  prefix,
);
app.listen(Number(process.env.PORT || 8080), process.env.HOST || "0.0.0.0");
