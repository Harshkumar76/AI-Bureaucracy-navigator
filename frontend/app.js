/* AI Bureaucracy Navigator — frontend logic.
   Submits the profile, reads the SSE stream, animates the agent panel,
   then renders findings cards + document checklist. */

const STATES = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat",
  "Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh",
  "Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab",
  "Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh",
  "Uttarakhand","West Bengal","Delhi","Jammu & Kashmir","Ladakh","Puducherry",
  "Chandigarh","Andaman & Nicobar Islands","Dadra & Nagar Haveli and Daman & Diu","Lakshadweep"
];
// ---- auth guard: this page requires a session ----
fetch("/api/auth/me").then(async (r) => {
  if (!r.ok) { location.href = "/signin.html"; return; }
  const user = await r.json();
  const chip = document.getElementById("user-chip");
  chip.replaceChildren();
  const name = document.createElement("span");
  name.textContent = user.name;
  const signout = document.createElement("button");
  signout.id = "signout-btn";
  signout.textContent = "Sign out";
  chip.append(name, signout);
  signout.onclick = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    location.href = "/";
  };
});

const stateSelect = document.getElementById("state-select");
for (const s of STATES) {
  const o = document.createElement("option");
  o.textContent = s;
  stateSelect.appendChild(o);
}

const $ = (id) => document.getElementById(id);

function buildProfile(form) {
  const fd = new FormData(form);
  const num = (k) => (fd.get(k) ? parseInt(fd.get(k), 10) : null);
  const str = (k) => fd.get(k) || null;
  const bool = (k) => (form.elements[k].checked ? true : null); // unchecked = unknown, not "no"
  return {
    age: num("age"),
    gender: str("gender"),
    state: str("state"),
    residence: str("residence"),
    annual_income: num("annual_income"),
    category: str("category"),
    religion: str("religion"),
    occupation: str("occupation"),
    education_level: str("education_level"),
    marital_status: str("marital_status"),
    disability_pct: num("disability_pct"),
    has_bpl_card: bool("has_bpl_card"),
    owns_cultivable_land: bool("owns_cultivable_land"),
    owns_pucca_house: form.elements["owns_pucca_house"].checked ? true : null,
    has_girl_child_under_10: bool("has_girl_child_under_10"),
    documents_have: [...document.querySelectorAll("#doc-checkboxes input:checked")].map(c => c.value),
    extra_info: str("extra_info"),
  };
}

/* ---- agent panel ---- */
const agentRows = {};
function agentEvent(ev) {
  let row = agentRows[ev.agent];
  if (!row) {
    row = document.createElement("div");
    row.className = "agent-row working";
    row.innerHTML = `
      <div class="emoji">${ev.emoji}</div>
      <div class="info">
        <div class="agent-name">${ev.label}</div>
        <div class="agent-msg"></div>
      </div>
      <div class="status"><span class="spinner"></span></div>`;
    $("agent-list").appendChild(row);
    agentRows[ev.agent] = row;
  }
  row.querySelector(".agent-msg").textContent = ev.message;
  if (ev.state === "done") {
    row.classList.remove("working");
    row.classList.add("done");
    row.querySelector(".status").textContent = "✅";
  }
}

/* ---- findings ---- */
function renderFindings(data) {
  // detail pages read the user's verdicts from here
  sessionStorage.setItem("nav_findings", JSON.stringify(data.findings));
  $("summary-box").textContent = data.summary;

  const cards = $("finding-cards");
  cards.innerHTML = "";
  const show = data.findings.filter(f => f.status !== "ineligible");
  const hide = data.findings.filter(f => f.status === "ineligible");

  const mk = (f) => {
    const card = document.createElement("div");
    card.className = `card ${f.status}` + (f.status === "ineligible" ? " ineligible-card" : "");
    const statusLabel = { eligible: "Eligible", possible: "Possibly eligible", ineligible: "Not eligible" }[f.status];
    const railMark = { eligible: "✓", possible: "?", ineligible: "✕" }[f.status];
    const railLabel = { eligible: "match", possible: "confirm", ineligible: "no match" }[f.status];
    const missing = f.documents_missing.length
      ? `<span class="missing">Missing: ${f.documents_missing.join(", ")}</span>`
      : "You have all required documents ✓";
    const linkNote = f.link_alive === false ? " ⚠ portal unreachable right now" : "";
    card.innerHTML = `
      <div class="rail">
        <span class="rail-mark">${railMark}</span>
        <span class="rail-label">${railLabel}</span>
      </div>
      <div class="card-main">
        <div class="card-top">
          <h3><a class="scheme-link" href="scheme.html?id=${encodeURIComponent(f.scheme_id)}">${f.name}</a></h3>
          <div class="card-actions">
            <span class="pill ${f.status}">${statusLabel}</span>
            <a class="btn-details" href="scheme.html?id=${encodeURIComponent(f.scheme_id)}">View details →</a>
          </div>
        </div>
        <div class="benefit">${f.benefit}</div>
        <ul class="reasons">${f.reasons.map(r => `<li>${r}</li>`).join("")}</ul>
        <div class="docs">Needs: ${f.documents.join(", ")}<br>${missing}</div>
        <div class="source">
          <span><a href="${f.official_url}" target="_blank" rel="noopener">${new URL(f.official_url).hostname}</a>
            — ${f.apply_mode}${linkNote}</span>
          <span>verified ${f.last_verified}</span>
        </div>
      </div>`;
    return card;
  };

  show.forEach(f => cards.appendChild(mk(f)));

  if (hide.length) {
    const btn = document.createElement("button");
    btn.className = "toggle-ineligible";
    btn.textContent = `Show ${hide.length} schemes you don't qualify for (and why) ▾`;
    const hidden = document.createElement("div");
    hidden.style.display = "none";
    hide.forEach(f => hidden.appendChild(mk(f)));
    btn.onclick = () => {
      const open = hidden.style.display === "none";
      hidden.style.display = open ? "block" : "none";
      btn.textContent = open
        ? "Hide ineligible schemes ▴"
        : `Show ${hide.length} schemes you don't qualify for (and why) ▾`;
    };
    cards.appendChild(btn);
    cards.appendChild(hidden);
  }

  const box = $("checklist-box");
  if (data.checklist.length) {
    box.innerHTML = "<h2>📋 Your document checklist</h2>";
    for (const c of data.checklist) {
      const item = document.createElement("div");
      item.className = "check-item";
      item.innerHTML = `
        <span class="mark">${c.have ? "✅" : "⬜"}</span>
        <span><b>${c.document}</b>
          <span class="for">— needed for ${c.needed_for.length} scheme(s)</span></span>`;
      box.appendChild(item);
    }
  } else {
    box.innerHTML = "";
  }
  $("findings").classList.remove("hidden");
}

/* ---- submit + SSE stream ---- */
$("profile-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("submit-btn");
  btn.disabled = true;
  btn.textContent = "Agents working...";
  $("placeholder").style.display = "none";
  $("findings").classList.add("hidden");
  $("agent-list").innerHTML = "";
  Object.keys(agentRows).forEach(k => delete agentRows[k]);
  $("agent-panel").classList.remove("hidden");

  try {
    const res = await fetch("/api/navigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildProfile(e.target)),
    });
    if (res.status === 401) { location.href = "/signin.html"; return; }
    if (!res.ok) throw new Error(`Server error ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const ev = JSON.parse(line.slice(5));
        if (ev.type === "agent") agentEvent(ev);
        else if (ev.type === "findings") renderFindings(ev);
      }
    }
  } catch (err) {
    $("agent-list").innerHTML = `<div class="agent-row">❌ ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "🚀 Find my schemes";
  }
});
