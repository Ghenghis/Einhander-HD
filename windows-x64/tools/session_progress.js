/* Reviewed live-test progress. Counts never promote semantic bindings. */
(() => {
  "use strict";
  const host = document.getElementById("view-research");
  const card = document.createElement("article"); card.className = "card mt"; card.hidden = true;
  const title = document.createElement("h2"); title.textContent = "Current Level 1 evidence review";
  const status = document.createElement("p"), stats = document.createElement("div"), findings = document.createElement("ul"), links = document.createElement("div"), updated = document.createElement("small");
  stats.className = "row"; links.className = "row mt"; updated.className = "muted";
  card.append(title, status, stats, findings, links, updated);
  host.insertBefore(card, host.children[1] || null);
  let pending = false;
  async function refresh() {
    if (pending) return;
    pending = true;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch("/files/tools/research-session-summary.json", { cache: "no-store", signal: controller.signal });
      if (!response.ok) return;
      const data = await response.json();
      status.textContent = data.status;
      stats.replaceChildren();
      for (const item of data.metrics || []) { const tag = document.createElement("span"); tag.className = "tag blue"; tag.textContent = `${item.value} ${item.label}`; stats.append(tag); }
      findings.replaceChildren();
      for (const item of data.findings || []) { const row = document.createElement("li"); row.textContent = item; findings.append(row); }
      links.replaceChildren();
      for (const item of data.evidence || []) {
        if (typeof item.url !== "string" || !item.url.startsWith("/dev/evidence/files/") || item.url.includes("..") || item.url.includes("\\")) continue;
        const link = document.createElement("a"); link.href = item.url; link.textContent = `${item.label} ↗`; link.target = "_blank"; link.rel = "noopener"; links.append(link);
      }
      updated.textContent = `Reviewed ${new Date(data.updated_at_utc).toLocaleString()} · ${data.scope || "Candidate evidence; gameplay acceptance remains separate"}`;
      card.hidden = false;
    } catch { /* The primary recorder connection status reports service failures. */ }
    finally { clearTimeout(timer); pending = false; }
  }
  refresh();
  setInterval(() => { if (!document.hidden && !host.hidden) refresh(); }, 15000);
})();
