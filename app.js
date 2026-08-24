const workflow = {
  id: "portfolio", name: "AML Case Portfolio", meta: "1,248 active cases", status: "green", children: [
    { id: "p1", name: "P1 · Urgent", meta: "72 cases · < 4h SLA", status: "red", children: [
      { id: "p1-case", name: "High-risk escalation", meta: "CASE-24081 · analyst review", status: "red", children: [
        { id: "p1-triage", name: "Triage & containment", meta: "Owner: Tier 2 · SLA 2h", status: "red", detail: "立即核實命中規則、凍結風險與跨部門通知。證據：alert、KYC、近 90 日交易。" },
        { id: "p1-mlro", name: "MLRO decision", meta: "Owner: MLRO · SLA 4h", status: "amber", detail: "決定是否提交 SAR／STR，並確認帳戶限制及後續監控期間。" }
      ]}
    ]},
    { id: "p2", name: "P2 · High risk", meta: "386 cases · 24h SLA", status: "amber", children: [
      { id: "p2-cash", name: "Cash activity alerts", meta: "143 cases · queue A", status: "amber", children: [
        { id: "p2-review", name: "Investigate pattern", meta: "Owner: Investigation · 24h", status: "amber", detail: "比對資金來源、交易型態與客戶預期行為；將關聯對手方合併為一個 investigation bundle。" },
        { id: "p2-qa", name: "QA review", meta: "Owner: Quality team · 8h", status: "green", detail: "抽查敘事、證據鏈與決策理由，退回缺少可稽核依據的案件。" }
      ]},
      { id: "p2-sanctions", name: "Sanctions screening", meta: "89 cases · queue B", status: "green", children: [
        { id: "p2-disposition", name: "Disposition", meta: "Owner: Analyst · 8h", status: "green", detail: "確認 true hit / false positive，記錄匹配依據與處置原因。" }
      ]}
    ]},
    { id: "p3", name: "P3 · Standard", meta: "790 cases · 72h SLA", status: "green", children: [
      { id: "p3-tm", name: "Transaction monitoring", meta: "514 cases · queue C", status: "green", children: [
        { id: "p3-intake", name: "Intake validation", meta: "Owner: Ops · 8h", status: "green", detail: "檢查 alert 完整性、去重、客戶群組與路由規則；不完整案件自動退回補件。" },
        { id: "p3-close", name: "Close / monitor", meta: "Owner: Analyst · 72h", status: "green", detail: "結案時保留理由、證據索引及下次監控條件；對重複型態建立 watchlist。" }
      ]}
    ]}
  ]
};

const expanded = new Set(["portfolio", "p1", "p1-case", "p2", "p2-cash", "p3", "p3-tm"]);
let selectedId = null;
const tree = document.querySelector("#tree"), links = document.querySelector("#links"), detail = document.querySelector("#detail");

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
      button.innerHTML = `<span class="topline"><span>${canExpand ? (expanded.has(item.node.id) ? "− 收合" : "+ 展開") : "● 工作項"}</span><span class="pill status-${item.node.status}">${item.node.status === "red" ? "ESCALATE" : item.node.status === "amber" ? "WATCH" : "ON TRACK"}</span></span><div class="name">${item.node.name}</div><div class="meta">${item.node.meta}</div>`;
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
function showDetail(node) { if (!node.detail) { detail.className="detail"; detail.innerHTML=`<p class="detail-label">${node.name}</p><h2>${node.meta}</h2><p>展開此節點以檢視子流程；在實際部署時，這裡可連接 case-management 系統，顯示即時隊列與 SLA。</p>`; return; } detail.className="detail"; detail.innerHTML=`<p class="detail-label">WORKFLOW STEP · ${node.status.toUpperCase()}</p><h2>${node.name}</h2><div class="detail-grid"><div><span>摘要</span>${node.detail}</div><div><span>控制點</span>完整 audit trail、四眼覆核、權限分離</div></div>`; }
window.addEventListener("resize", () => render());
window.addEventListener("keydown", e => { if (e.key === "Escape") { selectedId=null; detail.className="detail empty"; detail.innerHTML="<p class=\"detail-label\">選取節點</p><h2>點選一個流程節點</h2><p>查看負責人、SLA、升級規則與所需證據。</p>"; render(); }});
render();
