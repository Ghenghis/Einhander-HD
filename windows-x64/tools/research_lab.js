/* Read-only run recorder UI. Captured candidates never become verified controls. */
(() => {
  "use strict";
  const host = document.getElementById("view-research");
  const node = document.createElement("article");
  node.className = "card";
  node.id = "researchRecorder";
  node.innerHTML = `<div class="section-head"><div><h2>Research run recorder</h2><p>Collect missing evidence while you test a level, ship, weapon, or finish.</p></div><span class="tag blue" id="researchBadge">READ ONLY</span></div>
    <div class="form-grid"><label>Test scenario<select id="researchScenario"><option>Loading capture plan…</option></select></label><label>Run label<input id="researchRunLabel" maxlength="120" placeholder="Stage 1 · Aurora / Gold · Mk II"></label><label>Capture budget<select id="researchBudget"><option value="standard">Focused observation · 3 min / 32 MiB</option><option value="stage">Stage pass · up to 5 min / 128 MiB</option></select></label></div>
    <p id="researchScenarioNote" class="mt"></p><div class="row mt"><button id="researchStart" class="primary small" disabled>Start recording</button><button id="researchStop" class="small" disabled>Stop & finalize</button><button id="researchArm" class="small" disabled>Arm for future runs</button><button id="researchRefresh" class="small">Refresh recorder</button><button id="researchExport" class="small" disabled>Export recorder index</button></div>
    <div id="researchStatus" class="status-line" role="status">Checking recorder…</div><div id="researchLimits" class="caps"></div>
    <div class="divider"></div><h3>Mark a gameplay event</h3><p>Capture Before, perform one action in the game, then capture After. The matching Before marker is selected automatically. A point marker compares a broader observation window.</p>
    <div class="form-grid"><label>Capture task<select id="researchTask"><option value="">General observation</option></select></label><label>Event label<input id="researchEventLabel" maxlength="120" placeholder="Vulcan pickup, stock gun fired, boss claw opened…"></label><label>Event phase<select id="researchPhase"><option value="point">Point observation</option><option value="before">Before action</option><option value="after">After action</option></select></label><label>Matching Before marker<select id="researchPair"><option value="">Capture a Before marker first</option></select></label></div><button id="researchMark" class="small mt" disabled>Capture event</button>
    <div class="note mt">Recording reads diagnostic data. It does not write RAM, unlock ships, warp scenes, or confirm an address automatically. Source receipts, screenshots, and RAM observations have their own timestamps and capture limits.</div>
    <div class="grid mt"><div><h3>Current run</h3><div id="researchRun" class="record-list"></div></div><div><h3>Recent runs</h3><div id="researchHistory" class="record-list"></div></div></div>
    <details class="mt"><summary>Capture coverage & remaining work</summary><div id="researchCoverage" class="mt"></div><div id="researchGapSummary" class="note mt"></div><label class="mt">Find a capture task<input id="researchTaskSearch" type="search" placeholder="Ship, Gunpod, effect, boss, address…"></label><div id="researchTasks" class="record-list mt"></div></details><details class="mt"><summary>Last recorder receipt</summary><pre id="researchReceipt" class="log"></pre></details>`;
  host.prepend(node);
  for (const sibling of [...host.children].slice(1)) sibling.classList.add("mt");
  const el = (id) => document.getElementById(id);
  const state = { data: null, pending: false, polling: false, catalogSignature: "", pairSignature: "", preferredPair: "", notice: null, generation: 0, lastAttempt: 0 };
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  function message(text, error = false) {
    el("researchStatus").textContent = text;
    el("researchStatus").style.color = error ? "var(--red)" : "var(--cyan)";
  }
  function notice(text, error = false) { state.notice = { text, error, until: Date.now() + 12000 }; message(text, error); }
  async function request(body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/dev/research", {
        method: body ? "POST" : "GET", cache: "no-store",
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined, signal: controller.signal,
      });
      const data = await response.json();
      if (response.status === 404) {
        const error = new Error("Recorder backend is not active. Restart the local development bridge to load the installed capture service.");
        error.activationPending = true; throw error;
      }
      if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
      return data;
    } finally { clearTimeout(timeout); }
  }
  function controls() {
    const running = !!state.data?.status?.running;
    const configured = running || state.data?.status?.armed;
    const unavailable = !state.data || state.data.status?.activation_pending;
    el("researchStart").disabled = state.pending || unavailable || running;
    el("researchStop").disabled = state.pending || !running;
    el("researchMark").disabled = state.pending || !running;
    el("researchArm").disabled = state.pending || unavailable;
    el("researchArm").textContent = state.data?.status?.armed ? "Disarm future recording" : "Arm for future runs";
    el("researchScenario").disabled = state.pending || configured;
    el("researchRunLabel").disabled = state.pending || configured;
    el("researchBudget").disabled = state.pending || configured;
    el("researchExport").disabled = !state.data;
  }
  function scenarios() { return state.data?.catalog?.scenarios || []; }
  function tasks() { return state.data?.catalog?.tasks || []; }
  function scenarioNote() {
    const selected = scenarios().find((s) => s.id === el("researchScenario").value);
    el("researchScenarioNote").textContent = selected?.description || selected?.goal || "Record a controlled test and mark each important action.";
    const current = el("researchTask").value;
    el("researchTask").replaceChildren(new Option("General observation", ""));
    for (const task of tasks()) {
      if (selected?.task_ids?.length && !selected.task_ids.includes(task.id)) continue;
      el("researchTask").add(new Option(task.label || task.title || task.id, task.id));
    }
    if ([...el("researchTask").options].some((o) => o.value === current)) el("researchTask").value = current;
  }
  function renderTasks() {
    const query = el("researchTaskSearch").value.trim().toLowerCase();
    el("researchTasks").replaceChildren();
    for (const task of tasks().filter((t) => !query || JSON.stringify(t).toLowerCase().includes(query))) {
      const card = document.createElement("div"); card.className = "record";
      const title = document.createElement("strong"); title.textContent = task.label || task.title || task.id;
      const detail = document.createElement("p"); detail.textContent = task.description || task.goal || (Array.isArray(task.missing) ? task.missing.join(" ") : task.missing) || "Event evidence and independent confirmation required.";
      const stateLine = document.createElement("small"); stateLine.textContent = `${task.priority || ""} · ${task.category || task.domain || "Research"} · ${task.status || "unverified"}`;
      const details = document.createElement("details"); details.className = "mt";
      const summary = document.createElement("summary"); summary.textContent = "Evidence & confirmation criteria"; details.append(summary);
      for (const [label, key] of [["Known", "known"], ["Needed", "missing"], ["Capture", "evidence_required"], ["Confirm", "confirmation_criteria"]]) {
        const values = task[key]; if (!values?.length) continue;
        const heading = document.createElement("p"); heading.className = "mt"; heading.textContent = `${label}:`;
        const list = document.createElement("ul");
        for (const value of Array.isArray(values) ? values : [values]) { const item = document.createElement("li"); item.textContent = value; list.append(item); }
        details.append(heading, list);
      }
      card.append(title, detail, stateLine, details); el("researchTasks").append(card);
    }
    if (!el("researchTasks").children.length) el("researchTasks").textContent = "No capture tasks match this search.";
  }
  function render() {
    const data = state.data, status = data.status || {};
    const selected = el("researchScenario").value;
    const signature = JSON.stringify(data.catalog);
    if (signature !== state.catalogSignature) {
      state.catalogSignature = signature;
      el("researchScenario").replaceChildren();
      for (const scenario of scenarios()) el("researchScenario").add(new Option(scenario.label || scenario.title || scenario.id, scenario.id));
      if (scenarios().some((s) => s.id === selected)) el("researchScenario").value = selected;
      scenarioNote(); renderTasks();
      const gaps = data.catalog?.gap_summary;
      el("researchGapSummary").replaceChildren();
      const summary = document.createElement("p");
      summary.textContent = gaps ? `${gaps.missing_task_count} missing · ${gaps.candidate_task_count} candidate · ${gaps.verified_task_count} verified. ${gaps.headline || ""}` : "Capture tasks require evidence review before they can be called verified.";
      el("researchGapSummary").append(summary);
      const list = document.createElement("ul");
      for (const blocker of gaps?.blockers || []) { const item = document.createElement("li"); item.textContent = blocker; list.append(item); }
      el("researchGapSummary").append(list);
    }
    if (status.running && status.scenario && el("researchScenario").value !== status.scenario) { el("researchScenario").value = status.scenario; scenarioNote(); }
    if (status.armed && !status.running && status.armed_config?.scenario && el("researchScenario").value !== status.armed_config.scenario) { el("researchScenario").value = status.armed_config.scenario; scenarioNote(); }
    if (status.armed && !status.running) {
      el("researchBudget").value = status.armed_config?.limits?.duration_seconds === 300 ? "stage" : "standard";
      el("researchRunLabel").value = status.armed_config?.label || "";
    }
    if (status.running) {
      el("researchBudget").value = status.limits?.duration_seconds === 300 ? "stage" : "standard";
      el("researchRunLabel").value = status.label || "";
    }
    el("researchBadge").textContent = status.activation_pending ? "BRIDGE RESTART REQUIRED" : status.running ? "RECORDING" : status.armed ? "ARMED · WAITING" : "READ ONLY";
    const counters = status.counters || {};
    const limits = status.limits || data.catalog?.default_limits || {};
    el("researchLimits").textContent = Object.entries(limits).map(([k,v]) => `${k.replaceAll("_", " ")}: ${v}`).join(" · ");
    el("researchRun").innerHTML = status.id
      ? `<div class="record"><strong>${esc(status.label || status.id)}</strong><p>${esc(status.scenario)} · ${Math.floor(status.elapsed_seconds || 0)} s · ${esc(status.running ? "recording" : status.stop_reason || "finalized")}</p><pre class="log">${esc(JSON.stringify(counters, null, 2))}</pre></div>`
      : `<div class="empty-state">No run is recording. Start when the game is connected.</div>`;
    const native = status.native_capture;
    if (status.running && native?.last) {
      const nativeStatus = document.createElement("div"); nativeStatus.className = "record"; nativeStatus.id = "researchNativeStatus";
      const counts = native.last.counts || {}, caps = native.last.caps || {}, sampling = native.last.sampling;
      const number = (value) => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
      const sourceLimit = number(native.last.limits?.max_sources || limits.native_max_sources);
      const sourceCount = number(counts.sources);
      const summary = document.createElement("p");
      summary.textContent = `Native capture: ${native.last.active ? "recording" : native.last.reason || "inactive"} · ${sourceCount}${sourceLimit ? ` / ${sourceLimit}` : ""} sources · ${number(counts.records)} receipt rows · ${number(counts.events)} snapshots. ${Object.entries(caps).filter(([, hit]) => hit).map(([key]) => `${key} cap reached`).join(" · ")}`;
      nativeStatus.append(summary);
      if (sampling) {
        const policy = document.createElement("p"); policy.className = "mt";
        policy.textContent = sampling.policy === "lru_identity_phase_uv_quadrant_lease_rate"
          ? `Draw sampling follows recent texture identities, query/draw phases and broad UV areas. Older sample slots are replaced. Limit: ${Math.round(number(sampling.rate_per_second) * 100) / 100} rows/s; burst: ${number(sampling.burst)}.`
          : `Draw sampling policy: ${sampling.policy || "unspecified"}.`;
        const counters = document.createElement("p"); counters.id = "researchNativeSampling";
        counters.textContent = `Draw samples: ${number(sampling.rows)} · sample slots replaced: ${number(sampling.evictions)} · skipped repeats: ${number(sampling.repeat_skips)} · skipped by rate limit: ${number(sampling.rate_skips)} · skipped for reserved storage: ${number(sampling.budget_skips)} · skipped after row cap: ${number(sampling.record_cap_skips)}.`;
        nativeStatus.append(policy, counters);
      } else {
        const unavailable = document.createElement("p"); unavailable.className = "mt";
        unavailable.textContent = "Detailed sampling counters are unavailable in this runtime."; nativeStatus.append(unavailable);
      }
      const samplingNote = document.createElement("small"); samplingNote.id = "researchSamplingNote";
      samplingNote.textContent = "Sampling can omit a source query or a submitted draw. A missing row does not prove an object was absent or that a draw failed.";
      nativeStatus.append(samplingNote);
      const quotaFilled = caps.sources === true || sourceLimit > 0 && sourceCount >= sourceLimit;
      if (quotaFilled || native.last.source_file_budget_paused || native.last.evidence_budget_paused) {
        const warning = document.createElement("div"); warning.id = "researchSourceWarning"; warning.className = "note mt"; warning.setAttribute("role", "status");
        warning.textContent = quotaFilled
          ? "Raw source quota filled. Continuing draw receipts are sampled and do not provide complete raw texture/CLUT coverage. Stop and start a new segment linked to this run for additional sources."
          : native.last.source_file_budget_paused
            ? "Raw source files paused to preserve event snapshot slots. Continuing draw receipts do not mean complete raw texture/CLUT coverage. Start a new linked capture segment for additional sources."
            : "Evidence storage is reserved for remaining snapshots. New source files and draw receipts may pause. Start a new linked capture segment for additional source coverage.";
        nativeStatus.append(warning);
      }
      el("researchRun").append(nativeStatus);
    }
    const pairs = status.open_pairs || [], pairSignature = JSON.stringify(pairs);
    if (pairSignature !== state.pairSignature) {
      state.pairSignature = pairSignature;
      const selectedPair = el("researchPair").value;
      el("researchPair").replaceChildren(new Option("Choose a Before marker", ""));
      for (const pair of pairs) el("researchPair").add(new Option(`${pair.label} · frame ${pair.frame}`, pair.id));
      if (pairs.some((p) => p.id === selectedPair)) el("researchPair").value = selectedPair;
    }
    if (state.preferredPair && pairs.some((p) => p.id === state.preferredPair)) {
      el("researchPair").value = state.preferredPair;
      state.preferredPair = "";
    }
    if (!state.pending && state.notice?.until > Date.now()) message(state.notice.text, state.notice.error);
    else if (!state.pending) message(status.running
      ? `Recording ${status.id}. ${native?.supported === false || native?.ok === false ? "Native source receipts unavailable; read the receipt for limited capture scope." : native?.last?.active === false ? `Native capture stopped (${native.last.reason || "limit"}); RAM observations continue. Stop and start a focused run for further native evidence.` : "Mark events while you play."}`
      : status.armed && status.watch_status === "waiting_for_runtime" ? "Armed and waiting for the game to connect. Recording limits still apply; no game is started by this panel."
        : status.last_error || (status.armed ? "Armed for the next runtime connection. Disarm to change scenario or budget." : "Recorder ready. No game will be started by this panel."), !!status.last_error && !(status.armed && status.watch_status === "waiting_for_runtime"));
    el("researchHistory").replaceChildren();
    for (const run of (data.history || []).slice(0, 8)) {
      const card = document.createElement("div"); card.className = "record";
      const title = document.createElement("strong"); title.textContent = run.label || run.id;
      const text = document.createElement("p"); text.textContent = `${run.scenario || "research"} · ${run.stop_reason || run.status || "captured; review required"}`;
      card.append(title, text);
      const url = run.manifest_url;
      if (typeof url === "string" && /^\/(?:files|dev\/research\/files)\/[^\\]*\.json$/.test(url) && !url.includes("..")) {
        const link = document.createElement("a"); link.href = url; link.textContent = "Open run manifest ↗"; link.target = "_blank"; link.rel = "noopener"; card.append(link);
      }
      el("researchHistory").append(card);
    }
    if (!el("researchHistory").children.length) el("researchHistory").textContent = "Recorded runs will appear here.";
    const coverage = data.coverage || {};
    const count = Object.values(coverage).reduce((sum, row) => sum + (Number(row.runs) || 0), 0);
    const events = Object.values(coverage).reduce((sum, row) => sum + (Number(row.marked_events) || 0), 0);
    el("researchCoverage").textContent = `${scenarios().length} scenarios · ${tasks().length} capture tasks · ${count} archived runs · ${events} marked events. Captured evidence still requires independent review; recording never promotes a task to verified.`;
    controls();
  }
  async function refresh() {
    if (state.polling || state.pending) return;
    state.polling = true;
    state.lastAttempt = Date.now();
    const generation = state.generation;
    try { const data = await request(); if (generation === state.generation) { state.data = data; render(); } }
    catch (error) {
      if (error.activationPending && generation === state.generation) {
        try {
          const response = await fetch("/files/tools/research_catalog.json", { cache: "no-store" });
          if (!response.ok) throw new Error("Capture plan unavailable");
          state.data = { catalog: await response.json(), status: { running: false, armed: false, activation_pending: true, last_error: error.message }, coverage: {}, history: [] };
          render();
        } catch { message(`Recorder: ${error.message}`, true); }
      } else message(`Recorder: ${error.message}`, true);
    }
    finally { state.polling = false; controls(); }
  }
  async function submit(body) {
    if (state.pending) return;
    ++state.generation;
    state.pending = true; controls(); message("Collecting recorder receipt…");
    try {
      const result = await request(body);
      el("researchReceipt").textContent = JSON.stringify(result, null, 2);
      if (body.action === "mark" && body.phase === "before" && result.pair_id) {
        state.preferredPair = result.pair_id;
        el("researchPhase").value = "after";
      }
      notice(body.action === "mark" ? "Event captured. Its candidate changes still require review." : body.action === "stop" ? "Run finalized. Review its manifest and remaining capture tasks." : body.action === "arm" ? body.enabled ? "Recording armed for the next game connection. No game was started." : "Recording stopped and disarmed." : "Recording started. Play normally and mark important events.");
      if (result.status && state.data) { state.data.status = result.status; render(); }
    } catch (error) { notice(`Recorder: ${error.message}`, true); }
    finally { state.pending = false; controls(); await refresh(); }
  }
  function runSettings() {
    return { scenario: el("researchScenario").value, label: el("researchRunLabel").value.trim(),
      ...(el("researchBudget").value === "stage" ? { limits: { duration_seconds: 300, max_disk_bytes: 128*1024*1024, native_max_sources: 256, native_max_records: 20000, native_max_events: 32, native_max_frames: 18000, native_max_bytes: 112*1024*1024 } } : {}) };
  }
  el("researchStart").onclick = () => submit({ action: "start", ...runSettings() });
  el("researchStop").onclick = () => submit({ action: "stop" });
  el("researchArm").onclick = () => submit({ action: "arm", enabled: !state.data?.status?.armed, ...runSettings() });
  el("researchMark").onclick = () => {
    const phase = el("researchPhase").value, pair = el("researchPair").value, label = el("researchEventLabel").value.trim();
    if (!label) return message("Name the gameplay event before capturing it.", true);
    if (phase === "after" && !pair) return message("Capture and select a Before marker before capturing After.", true);
    submit({ action: "mark", label, phase, ...(phase === "after" ? { pair_id: pair } : {}), ...(el("researchTask").value ? { task_id: el("researchTask").value } : {}) });
  };
  el("researchScenario").onchange = scenarioNote;
  el("researchPair").onchange = () => {
    const pair = state.data?.status?.open_pairs?.find((p) => p.id === el("researchPair").value);
    if (pair) { el("researchPhase").value = "after"; el("researchEventLabel").value = pair.label || ""; el("researchTask").value = pair.task_id || ""; }
  };
  el("researchTaskSearch").oninput = renderTasks;
  el("researchRefresh").onclick = refresh;
  el("researchExport").onclick = () => {
    if (!state.data) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(state.data, null, 2) + "\n"], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "einhander-research-index.json"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  refresh();
  setInterval(() => { if (!document.hidden && (!host.hidden || state.data?.status?.running) && (!state.data?.status?.activation_pending || Date.now()-state.lastAttempt > 15000)) refresh(); }, 3000);
  async function effectsCoverage() {
    const card = document.createElement("article"); card.className = "card mt";
    document.getElementById("view-weapons").append(card);
    const title = document.createElement("h2"); title.textContent = "Firepower & effects production"; card.append(title);
    try {
      const response = await fetch("/files/tools/effects_catalog.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json(), summary = data.summary || {};
      const counts = document.createElement("p"); counts.textContent = `${summary.palette_key_variants_audited || 0} palette variants audited · ${summary.installed_variant_keys || 0} installed · ${summary.verified_weapon_specific_effect_bindings || 0} verified weapon-effect bindings.`; card.append(counts);
      const note = document.createElement("div"); note.className = "note"; note.textContent = "Source families are documented. Muzzle flashes, projectiles, impacts, explosions, and animation order need event-specific mapping before replacement art can be installed safely."; card.append(note);
      const action = document.createElement("button"); action.className = "small mt"; action.textContent = "Open effects capture plan";
      action.onclick = () => { document.getElementById("tab-research").click(); const scenario = scenarios().find((s) => /effect|weapon/i.test(s.id)); if (scenario && !state.data?.status?.running) { el("researchScenario").value = scenario.id; scenarioNote(); } node.scrollIntoView({ block: "start", behavior: "instant" }); }; card.append(action);
      const details = document.createElement("details"); details.className = "mt"; const heading = document.createElement("summary"); heading.textContent = "Review technical families & capture checklist"; details.append(heading);
      for (const item of [...(data.families || []), ...(data.next_capture_checklist || [])]) {
        const row = document.createElement("div"); row.className = "record mt";
        const name = document.createElement("strong"); name.textContent = item.name || item.id;
        const text = document.createElement("p"); text.textContent = item.interpretation || item.task || "Unassigned source family"; row.append(name, text); details.append(row);
      }
      card.append(details);
    } catch (error) { const message = document.createElement("p"); message.textContent = `Effects catalog unavailable: ${error.message}`; card.append(message); }
  }
  effectsCoverage();
})();
