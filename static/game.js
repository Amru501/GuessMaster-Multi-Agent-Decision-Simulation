const $ = (selector) => document.querySelector(selector);
const canvas = $("#tower-canvas");
const ctx = canvas.getContext("2d");
const state = { score: 0, shownScore: 0, gameOver: false, comparison: false, runs: [] };

function bustRisk(number) { return Math.min(.7, .02 + number / 240); }
function formatRiskPct(probability) { return `${Math.round(probability * 100)}%`; }
function updateRisk() {
  const offer = Number($("#offer").value || 0);
  const risk = bustRisk(offer);
  $("#risk").textContent = `IF ADD WINS · ${formatRiskPct(risk)} bust chance`;
}

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const bounds = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(bounds.width * ratio)); canvas.height = Math.max(1, Math.floor(bounds.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0); drawTower();
}

function drawTower() {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  ctx.clearRect(0, 0, width, height);
  const total = state.shownScore;
  const blockH = Math.max(3, Math.min(12, (height - 36) / Math.max(total, 24)));
  const blockW = Math.min(width * .54, 238);
  const baseY = height - 16;
  ctx.fillStyle = "rgba(20,28,43,.14)"; ctx.fillRect(width / 2 - blockW * .62, baseY, blockW * 1.24, 4);
  for (let i = 0; i < total; i++) {
    const y = baseY - (i + 1) * blockH;
    const shift = Math.sin(i * 12.9898) * Math.min(6, i * .08);
    const hue = 213 + (i % 5) * 5;
    ctx.fillStyle = `hsl(${hue} 86% ${54 + (i % 3) * 6}%)`;
    ctx.fillRect(width / 2 - blockW / 2 + shift, y, blockW, Math.max(2, blockH - 1));
    ctx.fillStyle = "rgba(255,255,255,.18)"; ctx.fillRect(width / 2 - blockW / 2 + shift, y, blockW, 1);
  }
}

function animateTower(to, { collapse = false, comparison = false } = {}) {
  const from = state.shownScore; const started = performance.now(); const duration = collapse ? 520 : 680;
  state.comparison = comparison;
  function frame(now) {
    const p = Math.min(1, (now - started) / duration); const eased = 1 - Math.pow(1 - p, 3);
    state.shownScore = Math.round(from + (to - from) * eased); drawTower();
    if (p < 1) requestAnimationFrame(frame); else { state.shownScore = to; drawTower(); }
  }
  requestAnimationFrame(frame);
}

function renderVotes(votes, majority) {
  const list = $("#votes"); list.innerHTML = "";
  votes.forEach((vote, index) => {
    const row = document.createElement("article"); row.className = "vote"; row.style.animationDelay = `${index * 70}ms`;
    const decisionClass = vote.decision === "ADD" ? "add" : "reject";
    row.innerHTML = `<span>${vote.emoji}</span><div class="vote-name">${vote.name} <small>${Math.round(vote.confidence * 100)}%</small></div><strong class="decision ${decisionClass}">${vote.decision}</strong><p class="vote-reason">${vote.reason}</p>`;
    list.appendChild(row);
  });
  $("#vote-count").textContent = `${votes.filter(v => v.decision === "ADD").length} ADD · ${votes.filter(v => v.decision === "REJECT").length} REJECT`;
  const majorityNode = $("#majority"); majorityNode.hidden = false; majorityNode.className = `majority ${majority === "REJECT" ? "reject" : ""}`;
  majorityNode.textContent = majority === "ADD" ? "MAJORITY: ADD — the tower takes the risk." : "MAJORITY: REJECT — the panel cashes out.";
}

function outcomeMessage(result) {
  const risk = formatRiskPct(result.bust_probability);
  if (result.outcome === "SAFE_ADD") {
    return `ADD won · bust roll passed (${risk} risk) — ${result.offer} slabs added.`;
  }
  if (result.outcome === "BUST") {
    return `ADD won · bust roll failed (${risk} risk) — tower lost.`;
  }
  const kept = result.final_score ?? result.score_before ?? result.score;
  return `REJECT won · no bust roll — cashed out at ${kept} slabs.`;
}
function runSlabs(run) {
  return run.peak_score ?? run.final_score ?? 0;
}

function visibleRuns(runs) {
  return (runs || []).filter((run) => runSlabs(run) >= 1);
}

function topRuns(runs, limit = 5) {
  return visibleRuns(runs)
    .slice()
    .sort((a, b) => runSlabs(b) - runSlabs(a))
    .slice(0, limit);
}

function renderComparison(runs) {
  const section = $("#comparison");
  const bars = $("#run-bars");
  const ranked = topRuns(runs, 5);
  if (!ranked.length) {
    section.hidden = true;
    bars.innerHTML = "";
    state.runs = [];
    return;
  }
  state.runs = ranked;
  section.hidden = false;
  bars.innerHTML = "";
  const max = Math.max(1, ...ranked.map((run) => runSlabs(run)));
  ranked.forEach((run, index) => {
    const slabs = runSlabs(run);
    const item = document.createElement("div");
    item.className = "run";
    const height = Math.max(5, Math.round(slabs / max * 96));
    item.innerHTML = `<span class="value">${slabs}</span><div class="run-bar" style="height:${height}px"></div><span>#${index + 1}</span>`;
    bars.appendChild(item);
  });
}

async function submitOffer() {
  const offer = Number($("#offer").value); const button = $("#submit-offer");
  button.disabled = true; button.textContent = "Panel thinking…"; $("#stage-message").textContent = "Five independent personas are deciding.";
  try {
    const response = await fetch("/api/offer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ offer }) });
    const result = await response.json();
    if (response.status === 409) {
      showEndedRun(result.error || "This run is over. Start a new tower to play again.", result);
      return;
    }
    if (!response.ok) throw new Error(result.error || "The panel could not decide.");
    if (result.votes?.length) {
      renderVotes(result.votes, result.majority);
    }
    $("#stage-message").textContent = outcomeMessage(result);
    if (result.outcome === "SAFE_ADD") {
      state.score = result.score;
      $("#score").textContent = result.score;
      $("#round").textContent = result.round;
      animateTower(result.score);
    } else if (result.outcome === "BUST") {
      state.score = 0;
      $("#score").textContent = 0;
      $("#round").textContent = result.round;
      animateTower(0, { collapse: true });
      renderComparison(result.previous_runs);
      finishGame();
    } else {
      const kept = result.final_score ?? result.score_before ?? result.score;
      state.score = kept;
      $("#score").textContent = kept;
      $("#round").textContent = result.round;
      animateTower(kept);
      renderComparison(result.previous_runs);
      finishGame();
    }
  } catch (error) { $("#stage-message").textContent = `Round cancelled: ${error.message}`; }
  finally { if (!state.gameOver) { button.disabled = false; button.textContent = "Ask the panel"; } }
}

function showEndedRun(message, result = {}) {
  state.gameOver = true;
  if (result.final_score != null) {
    state.score = result.final_score;
    $("#score").textContent = result.final_score;
    animateTower(result.final_score);
  }
  if (result.round != null) $("#round").textContent = result.round;
  $("#stage-message").textContent = message;
  $("#submit-offer").disabled = true;
  $("#offer").disabled = true;
  $("#new-game").hidden = false;
}

async function syncSession() {
  try {
    const response = await fetch("/api/status");
    const result = await response.json();
    if (!response.ok) return;
    state.score = result.score;
    state.shownScore = result.score;
    $("#score").textContent = result.score;
    $("#round").textContent = result.round;
    if (result.game_over) {
      showEndedRun("This run is over. Build a new tower to play again.", result);
    }
    if (result.previous_runs?.length) renderComparison(result.previous_runs);
    drawTower();
  } catch (_error) {
    $("#stage-message").textContent = "Could not reach the game server.";
  }
}

function finishGame() { state.gameOver = true; $("#submit-offer").disabled = true; $("#offer").disabled = true; $("#new-game").hidden = false; }
async function newGame() { const response = await fetch("/api/new-game", { method: "POST" }); const result = await response.json(); state.score = state.shownScore = 0; state.gameOver = state.comparison = false; $("#score").textContent = 0; $("#round").textContent = result.round; $("#votes").innerHTML = '<p class="empty-state">Choose an offer to hear from the five personas.</p>'; $("#vote-count").textContent = "Waiting"; $("#majority").hidden = true; $("#comparison").hidden = true; $("#new-game").hidden = true; $("#offer").disabled = false; $("#submit-offer").disabled = false; $("#submit-offer").textContent = "Ask the panel"; $("#stage-message").textContent = "Build as high as the panel allows."; drawTower(); }

$("#offer").addEventListener("input", updateRisk); $("#submit-offer").addEventListener("click", submitOffer); $("#new-game").addEventListener("click", newGame); $("#offer").addEventListener("keydown", event => { if (event.key === "Enter") submitOffer(); }); window.addEventListener("resize", resizeCanvas); updateRisk(); resizeCanvas(); syncSession();
