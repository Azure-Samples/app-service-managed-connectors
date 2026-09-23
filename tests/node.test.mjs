import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const language = process.env.SAMPLE_LANGUAGE;
assert.ok(["javascript", "typescript"].includes(language));
const modulePath = language === "typescript" ? "typescript/dist/app.js" : "javascript/app.js";
const { processEmails, createApp } = await import(`../src/${modulePath}`);
const payloads = JSON.parse(await readFile(new URL("./payloads.json", import.meta.url)));
const prefix = "[connector-pivots]";

test("only prefixed emails invoke actions", async () => {
  const ids = [];
  const result = await processEmails(payloads.mixed, async id => { ids.push(id); }, prefix);
  assert.deepEqual(ids, ["test-1", "test-2"]);
  assert.deepEqual(result, { received: 3, flagged: 2 });
});
test("empty batch succeeds without actions", async () => {
  assert.deepEqual(await processEmails(payloads.empty, async () => assert.fail(), prefix),
    { received: 0, flagged: 0 });
});
test("invalid payloads fail before actions", async () => {
  for (const payload of payloads.invalid) {
    await assert.rejects(processEmails(payload, async () => assert.fail(), prefix));
  }
});
test("empty prefix cannot flag unrelated email", async () => {
  await assert.rejects(processEmails(payloads.mixed, async () => assert.fail(), ""));
});
test("action failure is not acknowledged as success", async () => {
  await assert.rejects(processEmails(payloads.mixed, async () => {
    throw new Error("Action failed");
  }, prefix), /Action failed/);
});
test("HTTP accepts valid events and rejects invalid JSON and failed actions", async t => {
  const app = createApp(async id => {
    if (id === "fail") throw new Error("Action failed");
  }, prefix);
  const server = app.listen(0, "127.0.0.1");
  await new Promise(resolve => server.once("listening", resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}/api/webhook`;
  const post = body => fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body,
  });
  assert.equal((await post(JSON.stringify(payloads.mixed))).status, 200);
  assert.equal((await post("{")).status, 400);
  assert.equal((await post("{}")).status, 400);
  assert.equal((await post(JSON.stringify({
    body: { value: [{ id: "fail", subject: prefix }] },
  }))).status, 502);
});
