// Tests for public/answers.js, run with Node's built-in test runner: node --test tests/js/
// They use real Response objects, the same kind the browser's fetch() returns.

const test = require("node:test");
const assert = require("node:assert");
const { readAnswer, TOO_MANY_MESSAGE } = require("../../public/answers.js");

const json = (body, status) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

test("a good answer gives its body", async () => {
  assert.deepStrictEqual(await readAnswer(json({ report: "## 1. Summary" }, 200)), { ok: true, body: { report: "## 1. Summary" } });
});

test("Vercel's firewall 429 (plain text, not JSON) gives the wait message", async () => {
  const result = await readAnswer(new Response("Too Many Requests", { status: 429 }));
  assert.deepStrictEqual(result, { ok: false, error: TOO_MANY_MESSAGE });
});

test("a 504 timeout page (HTML) gives a clear message, not a crash", async () => {
  const result = await readAnswer(new Response("<html>An error occurred</html>", { status: 504 }));
  assert.strictEqual(result.ok, false);
  assert.match(result.error, /took too long/);
});

test("our API's own error message is shown as it is", async () => {
  const result = await readAnswer(json({ error: "The model is busy right now. Please try again in a minute." }, 503));
  assert.deepStrictEqual(result, { ok: false, error: "The model is busy right now. Please try again in a minute." });
});

test("an unexpected status without JSON names the status", async () => {
  const result = await readAnswer(new Response("", { status: 502 }));
  assert.match(result.error, /error 502/);
});
