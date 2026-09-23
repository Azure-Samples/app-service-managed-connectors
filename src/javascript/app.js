import express from "express";

export class InvalidPayloadError extends Error {}

export async function processEmails(payload, flagEmail, prefix) {
  if (!prefix?.trim()) throw new Error("TEST_SUBJECT_PREFIX must be nonempty.");
  const emails = payload?.body?.value;
  if (!Array.isArray(emails) || emails.some(email =>
    !email || typeof email.id !== "string" || !email.id.trim() ||
    typeof email.subject !== "string")) {
    throw new InvalidPayloadError("Expected body.value with email IDs and subjects.");
  }
  let flagged = 0;
  for (const email of emails) {
    if (!email.subject.startsWith(prefix)) continue;
    await flagEmail(email.id);
    flagged++;
  }
  return { received: emails.length, flagged };
}

export function createApp(flagEmail, prefix) {
  const app = express();
  app.use(express.json({ limit: "1mb" }));
  app.get("/healthz", (_request, response) => response.json({ status: "healthy" }));
  app.post("/api/webhook", async (request, response) => {
    const result = await processEmails(request.body, flagEmail, prefix);
    console.info(JSON.stringify({ event: "connector_processed", ...result }));
    response.json(result);
  });
  app.use((error, _request, response, _next) => {
    const invalid = error instanceof InvalidPayloadError ||
      error.type === "entity.parse.failed";
    console.error(JSON.stringify({ event: "connector_failed", type: error.name }));
    response.status(invalid ? 400 : error.type === "entity.too.large" ? 413 : 502)
      .json({ error: invalid ? "Invalid connector payload" : "Request processing failed" });
  });
  return app;
}
