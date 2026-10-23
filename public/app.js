// Tennis Scout page: name search, the Scout button, and safe display of the report.
// Visitors only pick players from the search list; the page sends player keys, never free text, to /api/report.

const pickedKeys = { scouted: null, coach: null }; // the player_key chosen in each box

function el(id) {
  return document.getElementById(id);
}

// ---------------------------------------------------------------- name search

function setUpSearch(boxName) {
  const input = el(boxName);
  const list = el(`${boxName}-list`);
  let timer = null;

  input.addEventListener("input", () => {
    pickedKeys[boxName] = null; // typing again cancels the previous choice
    input.classList.remove("picked");
    clearTimeout(timer);
    const text = input.value.trim();
    if (text.length < 2) {
      list.hidden = true;
      return;
    }
    timer = setTimeout(() => search(text, list, input, boxName), 250); // wait for a pause in typing
  });

  input.addEventListener("blur", () => setTimeout(() => (list.hidden = true), 200));
}

async function search(text, list, input, boxName) {
  let result;
  try {
    result = await readAnswer(await fetch(`/api/players?q=${encodeURIComponent(text)}`));
  } catch (networkFailure) {
    result = { ok: false, error: NETWORK_MESSAGE }; // only a real network failure lands here
  }
  const candidates = result.ok ? result.body.candidates : [];
  list.replaceChildren(); // build the list with textContent only, so names can never become HTML
  if (candidates.length === 0) {
    const empty = document.createElement("li");
    empty.className = "detail";
    empty.textContent = result.ok ? "No tour-level player found since 2015." : result.error;
    list.append(empty);
  }
  for (const player of candidates) {
    const item = document.createElement("li");
    const choose = document.createElement("button");
    choose.type = "button";
    const detail = document.createElement("span");
    detail.className = "detail";
    detail.textContent = ` ${player.tour.toUpperCase()} · ${player.country || "?"} · rank ${player.current_rank}`;
    choose.append(document.createTextNode(player.name), detail);
    choose.addEventListener("click", () => {
      pickedKeys[boxName] = player.player_key;
      input.value = player.name;
      input.classList.add("picked");
      list.hidden = true;
    });
    item.append(choose);
    list.append(item);
  }
  list.hidden = false;
}

// ---------------------------------------------------------------- the report

function showCheck(check) {
  const box = el("check");
  box.replaceChildren();
  if (check.passed) {
    box.className = "badge";
    box.textContent = "Numbers check: OK. Every number below was found in the statistics.";
    return;
  }
  // A report that fails the check is still shown, with this warning (and the server never caches it).
  box.className = "banner";
  const title = document.createElement("strong");
  title.textContent = "Warning: parts of this report did not pass the automatic check. Do not rely on them.";
  const details = document.createElement("ul");
  for (const number of check.numbers_not_found) {
    const line = document.createElement("li");
    line.textContent = `Number not found in the statistics: ${number}`;
    details.append(line);
  }
  for (const problem of check.problems) {
    const line = document.createElement("li");
    line.textContent = problem;
    details.append(line);
  }
  box.append(title, details);
}

async function scout(event) {
  event.preventDefault();
  const message = el("form-message");
  message.textContent = "";
  if (!pickedKeys.scouted) {
    message.textContent = "Pick the player to scout from the list that appears as you type.";
    return;
  }
  if (el("coach").value.trim() && !pickedKeys.coach) {
    message.textContent = "Pick your player from the list, or leave that box empty.";
    return;
  }

  const params = new URLSearchParams({ scouted: pickedKeys.scouted });
  if (pickedKeys.coach) params.set("coach", pickedKeys.coach);
  if (el("surface").value) params.set("surface", el("surface").value);

  const button = el("scout-button");
  button.disabled = true;
  message.replaceChildren();
  const spinner = document.createElement("span");
  spinner.className = "spinner";
  message.append(spinner, document.createTextNode("Writing the report (usually under 15 seconds)..."));
  message.classList.add("busy");

  try {
    let result;
    try {
      result = await readAnswer(await fetch(`/api/report?${params}`));
    } catch (networkFailure) {
      result = { ok: false, error: NETWORK_MESSAGE }; // only a real network failure lands here
    }
    message.classList.remove("busy");
    if (!result.ok) {
      message.textContent = result.error; // 429 from the firewall, 504, our API's own messages...
      return;
    }
    const body = result.body;
    message.textContent = "";
    showCheck(body.check);
    // The report is Markdown: turned into HTML by marked, then cleaned by DOMPurify, so nothing in it can run.
    el("report").innerHTML = DOMPurify.sanitize(marked.parse(body.report));
    el("made-by").textContent = `Headlines in sections 1 and 9 written by ${body.model}, checked by code.`;
    el("result").hidden = false;
    el("result").scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    button.disabled = false;
  }
}

// ---------------------------------------------------------------- start

async function showFreshness() {
  try {
    const answer = await fetch("/api/health");
    if (!answer.ok) return;
    const body = await answer.json();
    el("freshness").textContent = `ATP and WTA tour-level matches since 2015, data through ${body.data_through}.`;
  } catch (error) {
    // the footer keeps its default text
  }
}

setUpSearch("scouted");
setUpSearch("coach");
el("scout-form").addEventListener("submit", scout);
showFreshness();
