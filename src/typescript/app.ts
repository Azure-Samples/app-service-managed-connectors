import express, { type ErrorRequestHandler } from "express";

export class InvalidPayloadError extends Error {}
type Email = { id: string; subject: string };
type FlagEmail = (id: string) => Promise<void>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isEmail(value: unknown): value is Email {
  return isRecord(value) && typeof value.id === "string" &&
    value.id.trim().length > 0 && typeof value.subject === "string";
}

export async function processEmails(
  payload: unknown, flagEmail: FlagEmail, prefix: string,
): Promise<{ received: number; flagged: number }> {
  if (!prefix.trim()) throw new Error("TEST_SUBJECT_PREFIX must be nonempty.");
  const emails = isRecord(payload) && isRecord(payload.body) ? payload.body.value : undefined;
  if (!Array.isArray(emails) || !emails.every(isEmail)) {
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

export function createApp(flagEmail: FlagEmail, prefix: string) {
  const app = express();
  app.use(express.json({ limit: "1mb" }));
  app.get("/healthz", (_request, response) => response.json({ status: "healthy" }));
  app.post("/api/webhook", async (request, response) => {
    const result = await processEmails(request.body, flagEmail, prefix);
    console.info(JSON.stringify({ event: "connector_processed", ...result }));
    response.json(result);
  });
  const onError: ErrorRequestHandler = (error: unknown, _request, response, _next) => {
    const type = isRecord(error) ? error.type : undefined;
    const invalid = error instanceof InvalidPayloadError || type === "entity.parse.failed";
    console.error(JSON.stringify({
      event: "connector_failed", type: error instanceof Error ? error.name : "UnknownError",
    }));
    response.status(invalid ? 400 : type === "entity.too.large" ? 413 : 502)
      .json({ error: invalid ? "Invalid connector payload" : "Request processing failed" });
  };
  app.use(onError);
  return app;
}
