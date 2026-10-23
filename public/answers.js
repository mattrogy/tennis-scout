// Reading the API's answers safely, including the ones that are not JSON.
// Vercel's firewall answers 429 (too many requests) and its own 504 (timeout) with plain text, not JSON,
// so the page checks the status first and only then tries to read JSON.

const TOO_MANY_MESSAGE = "Too many reports in a short time. Please wait 10 minutes and try again.";
const NETWORK_MESSAGE = "The site could not be reached. Please check your connection and try again.";

function messageForStatus(status) {
  if (status === 429) return TOO_MANY_MESSAGE;
  if (status === 504) return "The report took too long to write. Please try again.";
  if (status === 503) return "The site is busy right now. Please try again in a minute.";
  if (status >= 500) return `The site had a problem (error ${status}). Please try again.`;
  return `Unexpected answer from the site (error ${status}). Please try again.`;
}

// Returns { ok: true, body } or { ok: false, error }. Never throws for an answer that arrived.
async function readAnswer(answer) {
  if (answer.status === 429) return { ok: false, error: TOO_MANY_MESSAGE }; // the firewall, not our API
  let body = null;
  try {
    body = await answer.json();
  } catch (notJson) {
    body = null; // a plain-text or HTML answer from Vercel itself
  }
  if (answer.ok && body) return { ok: true, body };
  if (body && body.error) return { ok: false, error: body.error }; // our API's own clear message
  return { ok: false, error: messageForStatus(answer.status) };
}

// Lets the tests load this file with Node; in the browser, `module` does not exist and this line does nothing.
if (typeof module !== "undefined") module.exports = { readAnswer, messageForStatus, TOO_MANY_MESSAGE, NETWORK_MESSAGE };
