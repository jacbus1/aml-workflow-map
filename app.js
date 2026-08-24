const caseRecords = {
  "XXXXXX": { assigned: "YES", level: "L2", owner: "Tier 2 Investigation", updated: "12:54", queue: "P1 · Urgent" },
  "CASE-24081": { assigned: "YES", level: "L3", owner: "Financial Crime Investigator", updated: "12:55", queue: "P1 · Urgent" },
  "CASE-24082": { assigned: "NO", level: "L1", owner: "Unassigned", updated: "12:41", queue: "P2 · High risk" }
};
let currentCase = "XXXXXX";
let inspectedLevel = "L2";
const levelOwnership = {
  L1: { stage: "Intake & validation", owners: ["Queue Analyst · Anna Li", "Operations Reviewer · Marcus Green"] },
  L2: { stage: "Triage & investigation", owners: ["Tier 2 Investigator · Dana Patel", "Senior Analyst · Jordan Lee"] },
  L3: { stage: "Enhanced due diligence", owners: ["Financial Crime Investigator · Priya Shah", "Subject Matter Expert · Theo Martin", "Quality Reviewer · Sam Wong"] },
  L4: { stage: "Quality assurance", owners: ["QA Lead · Morgan Chen", "QA Reviewer · Alex Rivera"] },
  L5: { stage: "MLRO decision & filing", owners: ["MLRO · Robin Taylor", "Deputy MLRO · Casey Brown"] }
};

const workflow = {
  id: "portfolio", name: "AML Case Portfolio", meta: "1,248 active cases", status: "green", children: [
    { id: "p1", name: "P1 · Urgent", meta: "72 cases · < 4h SLA", status: "red", children: [
      { id: "p1-case", name: "High-risk escalation", meta: "CASE-24081 · analyst review", status: "red", children: [
        { id: "p1-triage", name: "Triage & containment", meta: "Owner: Tier 2 · SLA 2h", status: "red", detail: "Validate the alert, contain immediate risk and notify the required internal teams. Evidence: alert, KYC and the previous 90 days of activity." },
        { id: "p1-mlro", name: "MLRO decision", meta: "Owner: MLRO · SLA 4h", status: "amber", detail: "Decide whether to file a SAR/STR and confirm account restrictions and the follow-up monitoring period." }
      ]}
    ]},
    { id: "p2", name: "P2 · High risk", meta: "386 cases · 24h SLA", status: "amber", children: [
      { id: "p2-cash", name: "Cash activity alerts", meta: "143 cases · queue A", status: "amber", children: [
        { id: "p2-review", name: "Investigate pattern", meta: "Owner: Investigation · 24h", status: "amber", detail: "Compare source of funds, transaction patterns and expected customer activity; group related counterparties into one investigation bundle." },
        { id: "p2-qa", name: "QA review", meta: "Owner: Quality team · 8h", status: "green", detail: "Check the narrative, evidence chain and decision rationale. Return cases that lack an auditable basis." }
      ]},
      { id: "p2-sanctions", name: "Sanctions screening", meta: "89 cases · queue B", status: "green", children: [
        { id: "p2-disposition", name: "Disposition", meta: "Owner: Analyst · 8h", status: "green", detail: "Confirm true hit or false positive and record the matching evidence and disposition rationale." }
      ]}
    ]},
    { id: "p3", name: "P3 · Standard", meta: "790 cases · 72h SLA", status: "green", children: [
      { id: "p3-tm", name: "Transaction monitoring", meta: "514 cases · queue C", status: "green", children: [
        { id: "p3-intake", name: "Intake validation", meta: "Owner: Ops · 8h", status: "green", detail: "Check alert completeness, duplicate detection, customer grouping and routing rules; return incomplete cases for remediation." },
        { id: "p3-close", name: "Close / monitor", meta: "Owner: Analyst · 72h", status: "green", detail: "Retain the rationale, evidence index and next-monitoring conditions; add recurring patterns to the watchlist." }
      ]}
    ]}
  ]
};

const expanded = new Set(["portfolio", "p1", "p1-case", "p2", "p2-cash", "p3", "p3-tm"]);
let selectedId = null;
const tree = document.querySelector("#tree"), links = document.querySelector("#links"), detail = document.querySelector("#detail");
const caseInput = document.querySelector("#case-input"), caseSearch = document.querySelector("#case-search"), caseStatus = document.querySelector("#case-status"), ownershipInspector = document.querySelector("#ownership-inspector");

function renderCaseStatus() {
  const record = caseRecords[currentCase];
  if (!record) { caseStatus.textContent = "Case not found. Try XXXXXX, CASE-24081 or CASE-24082 (demo data)."; ownershipInspector.replaceChildren(); return; }
  inspectedLevel = levelOwnership[inspectedLevel] ? inspectedLevel : record.level;
  const chips = ["L1", "L2", "L3", "L4", "L5"].map(level => `<button type="button" class="level-chip ${level === record.level ? "active" : ""}" data-level="${level}" aria-pressed="${level === inspectedLevel}">${level}</button>`).join("");
  caseStatus.innerHTML = `<div class="case-field"><b>ASSIGNED</b><strong class="assigned-${record.assigned.toLowerCase()}">${record.assigned}</strong></div><div class="case-field"><b>CURRENT LEVEL · click to inspect</b><strong class="level-track">${chips}</strong></div><div class="case-field"><b>CURRENT OWNER</b><strong>${record.owner}</strong></div><div class="case-field"><b>QUEUE / UPDATED</b><strong>${record.queue} · ${record.updated}</strong></div>`;
  caseStatus.querySelectorAll("[data-level]").forEach(button => button.addEventListener("click", () => { inspectedLevel = button.dataset.level; renderCaseStatus(); }));
  const assignment = levelOwnership[inspectedLevel];
  ownershipInspector.innerHTML = `<span>LEVEL ${inspectedLevel} · ${assignment.stage}</span><strong>${assignment.owners.map(owner => `<i>${owner}</i>`).join("")}</strong>`;
}
function loadCase() { currentCase = caseInput.value.trim().toUpperCase(); caseInput.value = currentCase; if (caseRecords[currentCase]) inspectedLevel = caseRecords[currentCase].level; renderCaseStatus(); }

function visibleNodes(node, level = 0, parent = null, rows = []) {
  rows.push({ node, level, parent });
  if (expanded.has(node.id)) (node.children || []).forEach(child => visibleNodes(child, level + 1, node.id, rows));
  return rows;
}
function render() {
  const rows = visibleNodes(workflow);
  tree.replaceChildren();
  const byLevel = new Map();
  rows.forEach(item => { if (!byLevel.has(item.level)) byLevel.set(item.level, []); byLevel.get(item.level).push(item); });
  const positions = new Map();
  for (let level = 0; level < 4; level++) {
    const nodes = byLevel.get(level) || [];
    nodes.forEach((item, index) => {
      const wrap = document.createElement("div"); wrap.className = "node-wrap"; wrap.style.gridColumn = level + 1; wrap.style.gridRow = Math.round((index + 1) * (12 / (nodes.length + 1)));
      const button = document.createElement("button"); button.className = `node ${level === 0 ? "root" : ""} ${selectedId === item.node.id ? "selected" : ""}`;
      button.setAttribute("role", "treeitem"); button.setAttribute("aria-expanded", item.node.children?.length ? expanded.has(item.node.id) : "false");
      const canExpand = item.node.children?.length;
      button.innerHTML = `<span class="topline"><span>${canExpand ? (expanded.has(item.node.id) ? "− collapse" : "+ expand") : "● workflow step"}</span><span class="pill status-${item.node.status}">${item.node.status === "red" ? "ESCALATE" : item.node.status === "amber" ? "WATCH" : "ON TRACK"}</span></span><div class="name">${item.node.name}</div><div class="meta">${item.node.meta}</div>`;
      button.onclick = () => { selectedId = item.node.id; if (canExpand) expanded.has(item.node.id) ? expanded.delete(item.node.id) : expanded.add(item.node.id); showDetail(item.node); render(); };
      wrap.append(button); tree.append(wrap); positions.set(item.node.id, { button, parent: item.parent });
    });
  }
  requestAnimationFrame(() => drawLinks(positions));
}
function drawLinks(positions) {
  const treeRect = tree.getBoundingClientRect(); links.replaceChildren(); links.setAttribute("viewBox", `0 0 ${treeRect.width} ${treeRect.height}`);
  positions.forEach(({button, parent}) => { if (!parent || !positions.has(parent)) return; const a = positions.get(parent).button.getBoundingClientRect(), b = button.getBoundingClientRect(); const x1=a.right-treeRect.left, y1=a.top+a.height/2-treeRect.top, x2=b.left-treeRect.left, y2=b.top+b.height/2-treeRect.top; const path=document.createElementNS("http://www.w3.org/2000/svg","path"); path.setAttribute("d",`M ${x1} ${y1} C ${x1+52} ${y1}, ${x2-52} ${y2}, ${x2} ${y2}`); path.setAttribute("fill","none"); path.setAttribute("stroke","#3b414b"); path.setAttribute("stroke-width","1.2"); links.append(path); });
}
function showDetail(node) { if (!node.detail) { detail.className="detail"; detail.innerHTML=`<p class="detail-label">${node.name}</p><h2>${node.meta}</h2><p>Expand this node to inspect child workflows. A production version can connect to a case-management system for live queues and SLA data.</p>`; return; } detail.className="detail"; detail.innerHTML=`<p class="detail-label">WORKFLOW STEP · ${node.status.toUpperCase()}</p><h2>${node.name}</h2><div class="detail-grid"><div><span>SUMMARY</span>${node.detail}</div><div><span>CONTROL POINTS</span>Complete audit trail · four-eyes review · separation of duties</div></div>`; }
caseSearch.addEventListener("click", loadCase);
caseInput.addEventListener("keydown", e => { if (e.key === "Enter") loadCase(); });
window.addEventListener("resize", () => render());
window.addEventListener("keydown", e => { if (e.key === "Escape") { selectedId=null; detail.className="detail empty"; detail.innerHTML="<p class=\"detail-label\">SELECT A NODE</p><h2>Choose a workflow node</h2><p>View the owner, SLA, escalation rule and required evidence.</p>"; render(); }});
renderCaseStatus();
render();
