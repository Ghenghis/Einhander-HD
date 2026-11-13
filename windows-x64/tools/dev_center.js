"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const AREAS = [
  [
    "overview",
    "01",
    "Overview",
    "PROJECT COMMAND",
    "Development control center",
    "Player tuning, visual evidence, and remaster production in one workspace.",
  ],
  [
    "player",
    "02",
    "Player & defense",
    "FLIGHT SYSTEMS",
    "Tune the pilot. Keep control.",
    "Read current values, apply explicit byte writes, and run time-limited holds.",
  ],
  [
    "weapons",
    "03",
    "Weapons & equipment",
    "ARMORY",
    "Every shot, accounted for.",
    "Inspect ammunition and track the research needed for persistent loadouts and equipment.",
  ],
  [
    "stages",
    "04",
    "Stages & encounters",
    "MISSION LAB",
    "Build a reproducible encounter.",
    "Bookmark scenes for research and testing. Stage and boss warps require verified routing.",
  ],
  [
    "graphics",
    "05",
    "Graphics & proof",
    "RENDER LAB",
    "See what actually changed.",
    "Inspect native output, texture coverage, and captured comparisons before calling it 4K.",
  ],
  [
    "skins",
    "06",
    "Skin studio",
    "VISUAL PRODUCTION",
    "A new identity for every craft.",
    "Explore vivid player and enemy finishes, then build versioned texture-pack workspaces.",
  ],
  [
    "research",
    "07",
    "Research & capture",
    "RESEARCH DESK",
    "Evidence behind every control.",
    "Record test runs, pair gameplay events with evidence, and search documented addresses.",
  ],
  [
    "automation",
    "08",
    "Input & automation",
    "TEST OPERATIONS",
    "Repeat the journey.",
    "Virtual controller, native attract mode, Robin, and diagnostic commands.",
  ],
  [
    "console",
    "09",
    "Console & history",
    "ENGINEERING",
    "A clear record of every action.",
    "Inspect debug responses, verified changes, and export a session record.",
  ],
];
const state = {
  catalog: null,
  status: null,
  skins: null,
  evidence: null,
  activity: [],
  busy: false,
  active: "overview",
  bookmarks: [],
  art: null,
};
try {
  state.bookmarks = JSON.parse(
    localStorage.getItem("ein.scene.bookmarks") || "[]",
  );
} catch {
  state.bookmarks = [];
}
if (!Array.isArray(state.bookmarks)) state.bookmarks = [];
let toastTimer;
function toast(message, error = false) {
  $("toast").textContent = message;
  $("toast").classList.toggle("error", error);
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 6500);
}
function record(label, result) {
  state.activity.unshift({
    at: new Date().toISOString(),
    action: label,
    result,
  });
  state.activity = state.activity.slice(0, 100);
  $("consoleOutput").textContent = JSON.stringify(result, null, 2);
  renderActivity();
}
async function api(path, body, timeout = 7000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      const error = new Error(
        data.error || `Request failed (${response.status})`,
      );
      error.details = data;
      throw error;
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}
async function action(label, path, body, success) {
  try {
    const data = await api(path, body);
    if (data.data?.ok === false) {
      const error = new Error(data.data.error || "Engine rejected the command");
      error.details = data;
      throw error;
    }
    record(label, data);
    toast(success || `${label} completed`);
    await refreshStatus();
    return data;
  } catch (e) {
    record(label, e.details || { ok: false, error: e.message });
    toast(`${label}: ${e.message}`, true);
    return null;
  }
}
async function debug(command, label) {
  const result = await action(label || command.cmd, "/cmd", {
    line: JSON.stringify(command),
  });
  return result?.data;
}
function download(name, data) {
  const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function selectArea(id, focus = false) {
  const area = AREAS.find((a) => a[0] === id) || AREAS[0];
  state.active = area[0];
  $("navigation")
    .querySelectorAll("[role=tab]")
    .forEach((b) => {
      const selected = b.dataset.area === state.active;
      b.setAttribute("aria-selected", String(selected));
      b.tabIndex = selected ? 0 : -1;
    });
  document
    .querySelectorAll(".view")
    .forEach((v) => (v.hidden = v.id !== `view-${state.active}`));
  $("viewKicker").textContent = area[3];
  $("viewTitle").textContent = area[4];
  $("viewDescription").textContent = area[5];
  $("breadcrumb").textContent = `/ ${area[2]}`;
  history.replaceState(null, "", `#${state.active}`);
  if (focus) $(`tab-${state.active}`).focus();
}
$("navigation").innerHTML = AREAS.map(
  (a, i) =>
    `<button type="button" role="tab" id="tab-${a[0]}" data-area="${a[0]}" aria-controls="view-${a[0]}" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}"><span>${a[1]}</span>${a[2]}</button>`,
).join("");
$("navigation").addEventListener("click", (e) => {
  const b = e.target.closest("[data-area]");
  if (b) selectArea(b.dataset.area);
});
$("navigation").addEventListener("keydown", (e) => {
  if (
    ![
      "ArrowDown",
      "ArrowUp",
      "ArrowRight",
      "ArrowLeft",
      "Home",
      "End",
    ].includes(e.key)
  )
    return;
  e.preventDefault();
  let i = AREAS.findIndex((a) => a[0] === state.active);
  i =
    e.key === "Home"
      ? 0
      : e.key === "End"
        ? AREAS.length - 1
        : (i +
            (["ArrowDown", "ArrowRight"].includes(e.key) ? 1 : -1) +
            AREAS.length) %
          AREAS.length;
  selectArea(AREAS[i][0], true);
});
window.addEventListener("hashchange", () => selectArea(location.hash.slice(1)));
const page = (id, html) =>
  `<section class="view" id="view-${id}" role="tabpanel" aria-labelledby="tab-${id}" ${id !== "overview" ? "hidden" : ""}>${html}</section>`;
const button = (label, command, extra = {}) =>
  `<button class="small" data-command="${esc(JSON.stringify({ cmd: command, ...extra }))}" data-live disabled>${label}</button>`;
const roadmap = [
  [
    "Reliable controls",
    "Correct read protocol, explicit byte widths, readback, conditional undo, and expiring holds.",
    "Implemented",
    "",
  ],
  [
    "Windowed quality",
    "Windowed presets for 1440p and UHD widths. Record dimensions and actual frame pacing.",
    "Measure",
    "blue",
  ],
  [
    "Skin collection",
    "Fourteen player and enemy finish directions, authored detail maps, versioned presets, and source-resolution labels.",
    "Production",
    "blue",
  ],
  [
    "Effects first",
    "Map explosion, muzzle flash, and projectile textures; preserve alpha and blend modes.",
    "Needs mapping",
    "amber",
  ],
  [
    "Loadout mastery",
    "Identify gun IDs, hardpoints, durability, equipment timers, and pickup ownership through traces.",
    "Research",
    "amber",
  ],
  [
    "Encounter launcher",
    "Verify stage transitions and boss entry state before enabling mission or boss selection.",
    "Research",
    "amber",
  ],
];
const steps = (items) =>
  items
    .map(
      (t, i) =>
        `<div class="milestone"><span class="step">${i + 1}</span><div><strong>${t}</strong></div></div>`,
    )
    .join("");
$("views").innerHTML = [
  page(
    "overview",
    `<div class="grid four"><div class="card metric"><div class="caps">Runtime link</div><div class="value" id="metricLink">—</div><div class="detail" id="metricLinkDetail">Read-only connection probe</div></div><div class="card metric"><div class="caps">Catalog controls</div><div class="value" id="metricFields">—</div><div class="detail">Explicit width + readback</div></div><div class="card metric"><div class="caps">Active holds</div><div class="value" id="metricLocks">0</div><div class="detail">Expire automatically</div></div><div class="card metric"><div class="caps">Texture inventory</div><div class="value" id="metricTextures">—</div><div class="detail">Files alone do not prove coverage</div></div></div><div class="grid mt"><article class="card"><div class="section-head"><h2>From remaster to proof</h2><span class="tag blue">DELIVERY PLAN</span></div><p>A quality bar for each part of the experience. Completed work needs observable evidence.</p><div class="timeline">${roadmap.map((r, i) => `<div class="milestone"><span class="step">${i + 1}</span><div><strong>${r[0]}</strong><p>${r[1]}</p></div><span class="tag ${r[3]}">${r[2]}</span></div>`).join("")}</div></article><div class="stack"><article class="card"><div class="section-head"><h2>Captured, not assumed</h2><button class="small quiet" data-go="graphics">Open render lab ↗</button></div><figure class="preview" id="overviewPreview"><div class="empty">Fresh render evidence will appear here.<br><small>Output dimensions and texture detail are reported separately.</small></div></figure><p class="mt">Review the actual capture, replacement coverage, and matched scene before judging quality.</p></article><article class="card"><h2>Quick access</h2><p>Everyday controls without the engineering noise.</p><div class="row"><button data-go="player" class="primary small">Player & defense</button><button data-go="skins" class="small">Explore skins</button><button data-go="automation" class="small">Watch native demo</button></div><div class="status-line" id="stopReason">No continuous controls started by this workspace.</div></article></div></div>`,
  ),
  page(
    "player",
    `<div class="note blue">Holds refresh selected values for up to five minutes. Release all controls stops holds, Robin, and injected input. Undo restores bytes only when they still match the last write.</div><div class="grid mt" id="playerFields"><div class="empty-state wide">Loading the field catalog…</div></div><article class="card mt"><div class="section-head"><h2>Active holds</h2><button class="small" id="undoLatest" data-live disabled>Undo latest write</button></div><div id="lockList" class="record-list"><div class="muted">No holds active.</div></div></article>`,
  ),
  page(
    "weapons",
    `<div class="grid" id="weaponFields"><div class="empty-state wide">Loading ammunition catalog…</div></div><div class="grid mt"><article class="card"><div class="section-head"><h2>Equipment systems</h2><span class="tag amber">RESEARCH REQUIRED</span></div><div id="equipmentResearch"></div></article><article class="card"><h2>Permanent loadout acceptance</h2><p>Weapon retention needs more than a frozen ammunition counter. Prove the behavior on each playable craft.</p><div class="timeline">${steps(["Identify each weapon ID and hardpoint capacity.", "Trace pickup, swap, death, and stage-transition writes.", "Separate ammo, durability, and pickup lifetime fields.", "Test locks across equip, discard, and respawn."])}</div><div class="note">Unlimited ammo, permanent equipment, shields, and weapon selection are different systems. Unsupported controls stay in research.</div></article></div>`,
  ),
  page(
    "stages",
    `<div class="grid"><article class="card"><div class="section-head"><h2>Scene bookmarks</h2><span class="tag blue">METADATA ONLY</span></div><p>Save a named observation with the live frame and field values. Bookmarks do not restore or warp the game.</p><div class="form-grid"><label>Stage / mission<input id="bookmarkStage" maxlength="64" placeholder="e.g. Stage 1 · city"></label><label>Boss / encounter<input id="bookmarkBoss" maxlength="64" placeholder="Encounter name or reference"></label></div><label class="mt">Research note<textarea id="bookmarkNote" rows="3" maxlength="800" placeholder="Which pickup, gun, or enemy was visible?"></textarea></label><div class="row mt"><button class="primary" id="bookmarkSave" data-live disabled>Bookmark current scene</button><button id="bookmarkExport">Export bookmarks</button></div><p class="status-line">Saved in this browser; export to keep a project copy.</p></article><article class="card"><div class="section-head"><h2>Stage & boss routing</h2><span class="tag amber">NOT MAPPED</span></div><div id="stageResearch"></div><div class="note">Mission and boss launch require verified overlay loading, spawn state, and camera setup. A single stage byte is insufficient.</div></article><article class="card wide"><h2>Observation log</h2><div id="bookmarkList" class="record-list mt"></div></article></div>`,
  ),
  page(
    "graphics",
    `<div class="grid four"><div class="card metric"><div class="caps">Recorded output</div><div class="value" id="renderOutput" style="font-size:21px">—</div><div class="detail">From capture metadata</div></div><div class="card metric"><div class="caps">Replacement pack</div><div class="value" id="renderPack">—</div><div class="detail">Inventory; not pixel coverage</div></div><div class="card metric"><div class="caps">GPU</div><div class="value" style="font-size:18px" id="renderGpu">Unmeasured</div><div class="detail">Actual detected hardware</div></div><div class="card metric"><div class="caps">4K quality claim</div><div class="value" style="font-size:18px;color:var(--amber)" id="renderClaim">Needs proof</div><div class="detail">Output, art, and pacing separately</div></div></div><div class="grid mt"><article class="card"><div class="section-head"><h2>Native output capture</h2><button id="captureFrame" class="primary small" data-live disabled>Capture present</button></div><figure class="preview" id="livePreview"><div class="empty">Capture the engine's presented framebuffer.</div></figure><div class="status-line" id="captureStatus">No capture requested in this browser session.</div><div class="row">${button("GPU state", "gpu_state")}${button("Frame pacing", "frame_perf")}${button("Geometry", "geom_correction")}</div></article><article class="card"><h2>Windowed quality presets</h2><p>The in-game developer panel exposes windowed render presets. Save and restart the runtime to measure the result.</p><div class="timeline"><div class="milestone"><span class="step">Q</span><div><strong>2560px workspace</strong><p>2560 × 1440 at 16:9; 2560 × 1920 at 4:3. Actual aspect support depends on the active game mod.</p></div><span class="tag blue">WINDOWED</span></div><div class="milestone"><span class="step">U</span><div><strong>3840px review</strong><p>3840 × 2160 at 16:9; 3840 × 2880 at 4:3. Verify pacing and monitor fit before regular play.</p></div><span class="tag blue">WINDOWED</span></div></div><div class="note">Higher output resolution does not create missing detail. Explosions and weapon fire need mapped replacements with the original transparency.</div><div class="row mt"><button id="refreshEvidence" class="small">Refresh evidence</button><button id="exportEvidence" class="small">Export report</button></div></article><article class="card wide"><div class="section-head"><h2>Visual evidence library</h2><span class="tag dim">SOURCE CAPTURES</span></div><div id="resolutionNote" class="note mt">Reading the capture verdict…</div><div id="evidenceGallery" class="grid"><div class="empty-state wide">No verified evidence loaded yet.</div></div><div id="comparisonArea" hidden class="mt"><h3>Exact-source texture comparison</h3><p class="muted" id="comparisonNote">These are texture atlases, not synchronized gameplay.</p><label>Texture identity<select id="comparisonSelect"></select></label><div class="compare" id="comparison"><img id="compareAfter" alt="Restored replacement for the selected texture"><div class="overlay" id="compareOverlay"><img id="compareBefore" alt="Stock source for the selected texture"></div></div><div class="compare-labels"><span>STOCK</span><span>HD REPLACEMENT</span></div><label>Reveal stock / HD<input id="compareSlider" type="range" min="0" max="100" value="50"></label></div></article></div>`,
  ),
  page(
    "skins",
    `<div class="note blue">Artwork preview → texture mapping → alpha validation → isolated pack → matched in-game capture. A preview is not an installed game skin.</div><article class="card mt"><div class="section-head"><div><h2>Finish library</h2><p>Distinct finishes designed to read against dark industrial stages.</p></div><span class="tag blue" id="skinCount">ART PRODUCTION</span></div><div class="form-grid mt"><label>Finish category<select id="finishCategory"><option value="all">All styles</option><option value="gold">Gold and Gilt</option><option value="neon">Neon and Cyberpunk</option><option value="vibrant">Vibrant and Elemental</option></select></label><label>Find a finish<input id="finishSearch" type="search" placeholder="Color, material, or name"></label></div><div id="skinArtGallery" class="skin-gallery mt"><div class="empty-state wide">Eight skin artworks are being prepared. Native source dimensions will appear on each image.</div></div></article><div class="grid mt"><article class="card"><h2>Create a pack workspace</h2><p>Prepare a versioned manifest without changing the installed HD pack. Templates record the finish and mappings still needed.</p><div class="form-grid"><label>Pack name<input id="skinName" maxlength="48" pattern="[A-Za-z0-9_-]+" placeholder="My_ship_collection"></label><label>Art direction<select id="skinStyle"><option value="">Loading styles…</option></select></label></div><button id="skinCreate" class="primary mt">Create workspace</button><div class="status-line" id="skinCreateStatus">Templates do not activate replacements.</div></article><article class="card"><h2>Production checklist</h2><div class="timeline">${steps(["Identify source hash, palette, class, and UV island.", "Apply finish to the original ship or weapon layout.", "Preserve every alpha byte and effect blend behavior.", "Compare stock and modded on the same frame."])}</div><p>Ship armor, enemy identification, weapon skins, and luminous effects remain separate categories.</p></article><article class="card wide"><div class="section-head"><h2>Local workspaces</h2><button id="skinRefresh" class="small">Refresh packs & art</button></div><div id="skinPackList" class="record-list"></div></article><article class="card wide"><h2>Import a mapped candidate</h2><p>Select a known texture and import an edited PNG into a draft workspace. Exact dimensions and source alpha bytes must match. Artwork concepts need UV mapping before this step.</p><div class="form-grid"><label>Target workspace<input id="importWorkspace" maxlength="48" pattern="[A-Za-z0-9_-]+" placeholder="Existing_workspace_name"></label><label>Find source texture<input id="sourceSearch" type="search" placeholder="Hash, dimensions, or method"></label><label>Installed source texture<select id="importKey"><option value="">Loading source catalog…</option></select></label><label>Candidate PNG<input id="importPng" type="file" accept="image/png"></label><div><a id="sourceDownload" href="#" target="_blank" rel="noopener">Inspect source PNG ↗</a><p class="mt" id="sourceDimensions">Choose a known texture identity.</p><p id="sourceCount" class="muted"></p></div></div><button id="importCandidate" class="mt">Validate & import to draft</button><div class="status-line" id="importStatus">Imported candidates remain inactive until engine verification.</div></article></div>`,
  ),
  page(
    "research",
    `<article class="card"><div class="section-head"><h2>Documented RAM fields</h2><input id="addressSearch" class="search" type="search" placeholder="Search address, field, or evidence" aria-label="Search address library"></div><p>Live readback confirms bytes; it does not by itself prove their gameplay interpretation.</p><div id="addressList" class="address-list"></div></article><article class="card mt"><div class="section-head"><h2>Open research</h2><span class="tag amber">NO UNVERIFIED WRITES</span></div><div id="allResearch"></div></article>`,
  ),
  page(
    "automation",
    `<div class="grid"><article class="card"><div class="section-head"><h2>Native attract mode</h2><span class="tag blue">GAME-RECORDED INPUT</span></div><p>At the title screen, release input and wait for the game's own demonstration.</p><div class="row"><button class="primary small" data-demo="watch" data-live disabled>Watch native demo</button><button class="small" data-demo="exit" data-live disabled>Exit demo · Start</button><button class="small" data-demo="release">Release input</button></div><div class="status-line" id="demoStatus">Native attract control is idle.</div></article><article class="card"><h2>Savestate diagnostics</h2><p>Restore has a known VRAM texture-corruption risk. Verify captures after loading.</p><div class="row"><label>Slot<input id="stateSlot" type="number" min="0" max="9" value="0"></label><button class="small" id="saveState" data-live disabled>Save snapshot</button>${button("Status", "savestate_status")}</div><label class="check mt"><input id="allowRestore" type="checkbox">Enable known-risk restore for this test</label><button class="danger small mt" id="loadState" disabled>Restore snapshot</button></article><article class="card"><h2>Virtual controller</h2><p>Presses expire after the selected number of game frames.</p><div class="pad" id="pad"></div><label class="mt">Hold duration in frames<input id="padFrames" type="number" min="1" max="120" value="12"></label></article><article class="card"><div class="section-head"><h2>Robin · autoplay</h2><span class="tag dim" id="botBadge">IDLE</span></div><p>Enemy-aware play: Robin finds enemies in the game's own draw data, lines up with the locked target, and evades incoming fire. Pad input only: no invincibility, no memory writes, and no automatic Continue.</p><div class="form-grid"><label>Name<input id="botName" value="Robin" maxlength="24"></label><label>Decisions / second<input id="botHz" type="number" min="1" max="20" value="20"></label></div><div class="form-grid mt">${[
      ["botFire", "Fire (main gun; pod when aligned)"],
      ["botWeave", "Positioning"],
      ["botDodge", "Aim and evade"],
    ]
      .map(
        ([id, label]) =>
          `<label class="check"><input id="${id}" type="checkbox" checked>${label}</label>`,
      )
      .join(
        "",
      )}</div><div class="row mt"><button id="botStart" class="primary small" data-live disabled>Start Robin</button><button id="botStop" class="small danger">Stop Robin</button></div><div class="status-line mt" id="botStatus">Robin is idle.</div><pre class="log mt" id="botLog">No bot log loaded.</pre></article></div>`,
  ),
  page(
    "console",
    `<article class="card"><div class="section-head"><h2>Engine console</h2><span class="tag amber">ADVANCED</span></div><p>One JSON command to the local debug server. Raw writes bypass catalog undo and readback.</p><div class="row">${button("GPU", "gpu_state")}${button("Pad", "pad_status")}${button("Geometry", "geom_correction")}${button("Memory card", "memcard_status")}${button("Frame timing", "frame_perf")}</div><label class="mt">JSON command<textarea id="rawCommand" class="mono" rows="3">{"cmd":"gpu_state"}</textarea></label><div class="row mt"><button id="rawSend" class="primary" data-live disabled>Send command</button><button id="exportSession">Export session</button><button id="consoleUndo" data-live disabled>Undo latest write</button></div><pre class="log mt" id="consoleOutput">No commands sent.</pre></article><div class="grid mt"><article class="card"><h2>Verified write history</h2><div id="writeHistory" class="record-list mt"></div></article><article class="card"><h2>Session activity</h2><div id="activityLog" class="record-list mt"><div class="muted">Actions will appear here.</div></div></article></div>`,
  ),
].join("");
function renderFields() {
  const fields = state.catalog?.fields || [];
  for (const category of ["player", "weapons"]) {
    const target = category === "player" ? "playerFields" : "weaponFields";
    $(target).innerHTML =
      fields
        .filter((f) => f.category === category)
        .map(
          (f) =>
            `<article class="card field-card"><div class="field-head"><div><h2>${esc(f.label)}</h2><div class="address">${esc(f.address)} · u${f.width * 8} · little-endian</div></div><span class="tag ${f.evidence === "verified_ram" ? "" : "blue"}">${f.evidence === "verified_ram" ? "Mapped" : "Documented"}</span></div><div class="field-current" id="value-${esc(f.id)}">— <small>not read</small></div><p class="field-note">${esc(f.note)}</p><form class="field-form" data-field="${esc(f.id)}"><label>Set value · ${f.min}–${f.max}<input aria-label="${esc(f.label)} value" name="value" type="number" min="${f.min}" max="${f.max}" step="1" value="${f.default}" required></label><button type="submit" class="primary" data-live disabled>Apply & verify</button></form>${f.lockable ? `<div class="lock-row"><span id="hold-${f.id}">No hold active</span><button class="small" data-lock="${f.id}" data-live disabled>Hold · 5 min</button></div>` : '<div class="lock-row">Continuous holds need lifecycle verification.</div>'}</article>`,
        )
        .join("") ||
      '<div class="empty-state wide">No mapped controls in this category.</div>';
  }
  document.querySelectorAll("form[data-field]").forEach((form) =>
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await action(
        "Write + readback",
        "/dev/write",
        { field: form.dataset.field, value: Number(form.elements.value.value) },
        "Write completed; inspect readback and history.",
      );
    }),
  );
  document.querySelectorAll("[data-lock]").forEach((b) =>
    b.addEventListener("click", async () => {
      const field = b.dataset.lock;
      const existing = (state.status?.locks || []).find(
        (l) => l.field === field,
      );
      const form = document.querySelector(`form[data-field="${field}"]`);
      if (!existing && !form.reportValidity()) return;
      await action(existing ? "Release hold" : "Hold value", "/dev/lock", {
        field,
        value: Number(form.elements.value.value),
        enabled: !existing,
        ttl_seconds: 300,
      });
    }),
  );
  $("metricFields").textContent = fields.filter((f) => f.writable).length;
  renderResearch();
  renderAddresses();
  updateLiveValues();
}
function researchRows(items) {
  return (
    items
      .map(
        (r) =>
          `<div class="research-item"><div class="row spread"><h3>${esc(r.label)}</h3><span class="tag amber">Research</span></div><p>${esc(r.reason || r.note)}</p>${r.address ? `<code class="mono muted">Candidate ${esc(r.address)}</code>` : ""}</div>`,
      )
      .join("") || "<p>No additional entries in this category.</p>"
  );
}
function renderResearch() {
  const entries = state.catalog?.research || [];
  $("equipmentResearch").innerHTML = researchRows(
    entries.filter((r) =>
      /weapon|equipment|shield|pod|timer|gun/i.test(
        `${r.id} ${r.category} ${r.label}`,
      ),
    ),
  );
  $("stageResearch").innerHTML = researchRows(
    entries.filter((r) =>
      /stage|boss|mission|enemy/i.test(`${r.id} ${r.category} ${r.label}`),
    ),
  );
  $("allResearch").innerHTML = researchRows(entries);
}
function renderAddresses() {
  const search = $("addressSearch").value.toLowerCase();
  const fields = (state.catalog?.fields || []).filter((f) =>
    JSON.stringify(f).toLowerCase().includes(search),
  );
  $("addressList").innerHTML =
    fields
      .map(
        (f) =>
          `<div class="address-entry"><strong>${esc(f.label)}</strong><code>${esc(f.address)}</code><span>u${f.width * 8}</span><small>${esc(f.note)}<br>Source: ${esc(f.source || f.evidence)}</small></div>`,
      )
      .join("") || '<div class="empty-state">No matching fields.</div>';
}
function updateLiveValues() {
  const connected = Boolean(state.status?.connected);
  $("connectionText").textContent = connected
    ? "Game connected"
    : "Game offline · bridge ready";
  $("connectionDot").classList.toggle("on", connected);
  $("metricLink").textContent = connected ? "ONLINE" : "OFFLINE";
  $("metricLinkDetail").textContent = connected
    ? "Live RAM values available"
    : "Launch a debug-enabled game";
  document
    .querySelectorAll("[data-live]")
    .forEach((b) => (b.disabled = !connected));
  $("loadState").disabled = !connected || !$("allowRestore").checked;
  for (const f of state.catalog?.fields || []) {
    const v = state.status?.values?.[f.id];
    const el = $(`value-${f.id}`);
    if (el)
      el.innerHTML = v?.ok
        ? `${esc(v.value)} <small>${esc(v.hex)}</small>`
        : "— <small>unavailable</small>";
    const lock = (state.status?.locks || []).find((l) => l.field === f.id);
    const hold = $(`hold-${f.id}`);
    if (hold)
      hold.textContent = lock
        ? `Held at ${lock.value} · ${Math.ceil(lock.expires_in)}s remaining`
        : "No hold active";
    const btn = document.querySelector(`[data-lock="${f.id}"]`);
    if (btn) btn.textContent = lock ? "Release hold" : "Hold · 5 min";
  }
  const locks = state.status?.locks || [];
  $("metricLocks").textContent = locks.length;
  $("lockList").innerHTML = locks.length
    ? locks
        .map(
          (l) =>
            `<div class="record row spread"><strong>${esc(l.field)} = ${esc(l.value)}</strong><span>${Math.ceil(l.expires_in)}s · ${esc(l.status)}</span></div>`,
        )
        .join("")
    : '<div class="muted">No holds active.</div>';
  if (state.status?.last_stop_reason)
    $("stopReason").textContent = state.status.last_stop_reason;
  const writes = state.status?.history || [];
  $("writeHistory").innerHTML = writes.length
    ? writes
        .slice(0, 15)
        .map(
          (w) =>
            `<div class="record"><div class="row spread"><strong>${esc(w.field)} · ${esc(w.before)} → ${esc(w.after)}</strong><span class="tag ${w.verified ? "" : "amber"}">${w.undone ? "Undone" : w.verified ? "Read back" : "Unverified"}</span></div><time>${esc(w.at)}</time></div>`,
        )
        .join("")
    : '<div class="muted">No catalog writes in this bridge session.</div>';
}
async function refreshStatus() {
  if (state.busy) return;
  state.busy = true;
  try {
    state.status = await api("/dev/status", undefined, 12000);
    updateLiveValues();
    $("lastUpdate").textContent =
      `LAST PROBE ${new Date().toLocaleTimeString()} · READ ONLY`;
  } catch (e) {
    state.status = { connected: false };
    updateLiveValues();
    $("connectionText").textContent = "Bridge unavailable";
    $("lastUpdate").textContent = `Probe failed: ${e.message}`;
  } finally {
    state.busy = false;
  }
}
function renderActivity() {
  $("activityLog").innerHTML =
    state.activity
      .slice(0, 15)
      .map(
        (a) =>
          `<div class="record"><strong>${esc(a.action)}</strong><br><time>${esc(a.at)}</time>${a.result?.ok === false ? `<p class="pending">${esc(a.result.error)}</p>` : ""}</div>`,
      )
      .join("") || '<div class="muted">Actions will appear here.</div>';
}
function renderBookmarks() {
  $("bookmarkList").innerHTML = state.bookmarks.length
    ? state.bookmarks
        .slice()
        .reverse()
        .map(
          (b) =>
            `<div class="record"><div class="row spread"><strong>${esc(b.stage || "Unlabeled stage")} / ${esc(b.boss || "Scene observation")}</strong><time>${esc(b.at)}</time></div><p>${esc(b.note)}</p><span class="mono muted">Frame ${esc(b.frame ?? "unavailable")} · metadata bookmark</span></div>`,
        )
        .join("")
    : '<div class="empty-state">No scene observations yet.</div>';
}
async function refreshSkins() {
  try {
    state.skins = await api("/dev/skins");
    const selectedStyle = $("skinStyle").value;
    $("skinStyle").innerHTML = (state.skins.styles || [])
      .map((s) => `<option value="${esc(s.id)}">${esc(s.label)}</option>`)
      .join("");
    if ([...$("skinStyle").options].some((o) => o.value === selectedStyle))
      $("skinStyle").value = selectedStyle;
    $("skinPackList").innerHTML = (state.skins.packs || []).length
      ? state.skins.packs
          .map(
            (p) =>
              `<div class="record"><strong>${esc(p.name || p.id)}</strong> <span class="tag amber">${esc(p.status || "Template")}</span><p class="mono muted">${esc(p.path || p.manifest_path || "Local workspace")}<br>${esc(p.note || "Mapping and in-game validation still required.")}</p></div>`,
          )
          .join("")
      : '<div class="empty-state">No custom pack workspaces. Create one above.</div>';
    renderSourceOptions();
  } catch (e) {
    $("skinCreateStatus").textContent = `Skin workspace API: ${e.message}`;
  }
  try {
    state.art = await api("/files/tools/skin_collection/collection.json");
    renderArt();
  } catch {
    /* Artwork may still be in production. */
  }
}
function renderSourceOptions() {
  const query = $("sourceSearch").value.trim().toLowerCase();
  const all = state.skins?.source_assets || [];
  const found = all.filter((s) =>
    `${s.key} ${s.width}x${s.height} ${s.method}`.toLowerCase().includes(query),
  );
  const visible = found.slice(0, 60);
  $("importKey").innerHTML =
    '<option value="">Select a source texture</option>' +
    visible
      .map(
        (s) =>
          `<option value="${esc(s.key)}">${esc(s.key)} · ${s.width}×${s.height}</option>`,
      )
      .join("");
  $("sourceCount").textContent =
    `${found.length} matching identities; showing ${visible.length} of ${all.length}. Filter by hash or dimensions to narrow the list.`;
  $("sourceDownload").removeAttribute("href");
}
function renderArt() {
  if (!state.art?.skins?.length) return;
  $("skinCount").textContent = `${state.art.skins.length} FINISHES`;
  const selectedCategory = $("finishCategory").value;
  const query = $("finishSearch").value.toLowerCase();
  const artworks = state.art.skins.filter(
    (s) =>
      (selectedCategory === "all" || s.category === selectedCategory) &&
      `${s.name} ${s.description}`.toLowerCase().includes(query),
  );
  $("skinArtGallery").innerHTML = artworks
    .map(
      (s) =>
        `<article class="card skin-card">${s.preview ? `<a href="${esc(localAssetURL(s.image || s.preview))}" target="_blank" rel="noopener"><img src="${esc(localAssetURL(s.preview))}" alt="${esc(s.name)} · ${esc(s.description)}" loading="lazy"></a>` : ""}<div class="skin-swatch">${(s.palette || []).map((c) => (/^#[\da-f]{6}$/i.test(c) ? `<span style="background:${c}"></span>` : "")).join("")}</div><div class="skin-info"><div class="row spread"><h3>${esc(s.name)}</h3><span class="tag blue">${esc(s.role || "Ship")}</span></div><p>${esc(s.description)}</p><div class="row spread"><span class="mono muted" style="font-size:11px">${esc(s.width)} × ${esc(s.height)} · ${esc(s.resolution_note || "Source artwork")}</span><span class="tag amber">ART · UNMAPPED</span></div><a class="small" href="${esc(localAssetURL(s.image || s.preview))}" target="_blank" rel="noopener">Open source image ↗</a></div></article>`,
    )
    .join("");
  $("skinArtGallery")
    .querySelectorAll(".skin-info")
    .forEach((info, index) => {
      const artwork = artworks[index];
      const use = document.createElement("button");
      use.className = "small primary mt";
      use.textContent = "Use this art direction";
      use.addEventListener("click", () => {
        $("skinStyle").value = artwork.id;
        $("skinName").value = artwork.id;
        window.openSkinArea?.("authoring");
        $("skinCreate").scrollIntoView({ block: "center" });
        $("skinName").focus({ preventScroll: true });
        toast(
          `${artwork.name} selected for a draft. Create a workspace to save.`,
        );
      });
      info.append(use);
    });
}
$("finishCategory").onchange = renderArt;
$("finishSearch").oninput = renderArt;
function evidenceImage(i) {
  return localAssetURL(i.url || i.image_url || i.path);
}
function localAssetURL(value) {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//")
  )
    return "";
  try {
    const url = new URL(value, location.origin);
    return url.origin === location.origin &&
      /^(\/files\/|\/dev\/evidence\/files\/|\/dev\/skins\/source\/)/.test(
        url.pathname,
      )
      ? url.pathname + url.search
      : "";
  } catch {
    return "";
  }
}
async function refreshEvidence() {
  try {
    state.evidence = await api("/dev/evidence");
    const e = state.evidence;
    const images = (e.images || e.captures || []).filter((i) =>
      evidenceImage(i),
    );
    $("evidenceGallery").innerHTML = images.length
      ? images
          .map(
            (i) =>
              `<figure class="preview"><a href="${esc(evidenceImage(i))}" target="_blank" rel="noopener"><img src="${esc(evidenceImage(i))}" loading="lazy" alt="${esc(i.label || i.name || "Recorded render evidence")}"></a><figcaption>${esc(i.label || i.name)} · ${esc(i.width || "?")} × ${esc(i.height || "?")}<br>${esc(i.note || i.description || "Review report for scope.")}</figcaption></figure>`,
          )
          .join("")
      : '<div class="empty-state wide">Evidence capture has not completed. Refresh after the isolated render test.</div>';
    if (images.length) {
      const i =
        images.find((x) => /stage|gameplay/i.test(x.label || x.name || "")) ||
        images[0];
      $("overviewPreview").innerHTML =
        `<img src="${esc(evidenceImage(i))}" alt="${esc(i.label || i.name)}"><figcaption>${esc(i.label || i.name)} · ${esc(i.width || "?")} × ${esc(i.height || "?")}</figcaption>`;
    }
    const summary = e.summary || e.report || e;
    $("renderGpu").textContent =
      summary.gpu?.name ||
      summary.gpu_name ||
      summary.gpu?.observed?.split(",")[0]?.replace("NVIDIA GeForce ", "") ||
      "See report";
    const count =
      summary.pack?.entries ??
      summary.pack?.entry_count ??
      summary.pack_entries ??
      e.pack?.entries ??
      e.installed_pack?.count;
    if (Number.isFinite(count)) {
      $("renderPack").textContent = count.toLocaleString();
      $("metricTextures").textContent = count.toLocaleString();
    }
    const largest = e.resolution_verdict?.largest_measured_window;
    const capture = images.find((i) => i.width && i.height);
    $("renderOutput").textContent = largest
      ? largest.join("×")
      : capture
        ? `${capture.width}×${capture.height}`
        : "Unmeasured";
    $("resolutionNote").textContent =
      e.resolution_verdict?.reason ||
      "Output dimensions and new artwork detail require independent verification.";
    $("renderClaim").textContent = e.resolution_verdict?.uhd_3840x2160_verified
      ? "Output verified"
      : "UHD unverified";
    const comparisons = e.texture_comparisons || [];
    if (comparisons.length) {
      $("comparisonSelect").innerHTML = comparisons
        .map((c) => `<option value="${esc(c.id)}">${esc(c.label)}</option>`)
        .join("");
      $("comparisonArea").hidden = false;
      renderComparison();
    }
  } catch (e) {
    $("evidenceGallery").innerHTML =
      `<div class="empty-state wide">Evidence API unavailable: ${esc(e.message)}</div>`;
  }
}
function renderComparison() {
  const comparison = state.evidence?.texture_comparisons?.find(
    (c) => c.id === $("comparisonSelect").value,
  );
  if (!comparison) return;
  const stock = comparison.images.find((i) => i.kind === "stock");
  const restored = comparison.images.find((i) => i.kind === "restored");
  if (!stock || !restored) return;
  $("compareBefore").src = stock.url;
  $("compareAfter").src = restored.url;
  $("compareBefore").style.imageRendering = "pixelated";
  $("comparisonNote").textContent =
    `${comparison.label} · ${stock.width}×${stock.height} → ${restored.width}×${restored.height}. ${comparison.method}. ${comparison.scope}`;
}
document.addEventListener("click", (e) => {
  const go = e.target.closest("[data-go]");
  if (go) selectArea(go.dataset.go);
  const cmd = e.target.closest("[data-command]");
  if (cmd) debug(JSON.parse(cmd.dataset.command));
  const demo = e.target.closest("[data-demo]");
  if (demo)
    action("Native demo", "/demo", { action: demo.dataset.demo }).then((r) => {
      if (r?.demo) $("demoStatus").textContent = r.demo.message;
    });
});
$("refresh").onclick = refreshStatus;
$("emergency").onclick = async () => {
  await action(
    "Release all controls",
    "/dev/emergency",
    {},
    "Control release requested; check the response.",
  );
  await refreshAutomation();
};
for (const id of ["undoLatest", "consoleUndo"])
  $(id).onclick = () => action("Conditional undo", "/dev/undo", {});
$("addressSearch").oninput = renderAddresses;
$("bookmarkSave").onclick = () => {
  if (!state.status?.connected)
    return toast("A live runtime is required.", true);
  state.bookmarks.push({
    at: new Date().toISOString(),
    stage: $("bookmarkStage").value.trim(),
    boss: $("bookmarkBoss").value.trim(),
    note: $("bookmarkNote").value.trim(),
    frame: state.status.game?.ws?.cur_frame,
    values: state.status.values,
  });
  state.bookmarks = state.bookmarks.slice(-100);
  try {
    localStorage.setItem(
      "ein.scene.bookmarks",
      JSON.stringify(state.bookmarks),
    );
    toast("Scene metadata saved in this browser.");
  } catch {
    toast("Storage unavailable. Export bookmarks to save.", true);
  }
  renderBookmarks();
};
$("bookmarkExport").onclick = () =>
  download("einhander-scene-bookmarks.json", state.bookmarks);
$("skinCreate").onclick = async () => {
  const name = $("skinName").value.trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$/.test(name))
    return toast(
      "Use 1–48 letters, digits, hyphens or underscores; begin with a letter or digit.",
      true,
    );
  const r = await action(
    "Create skin workspace",
    "/dev/skins",
    { action: "create", name, style: $("skinStyle").value },
    "Template created. Texture mapping is the next production step.",
  );
  if (r) {
    $("skinCreateStatus").textContent =
      "Workspace saved. Original game and installed pack are unchanged.";
    refreshSkins();
  }
};
$("skinRefresh").onclick = refreshSkins;
$("refreshEvidence").onclick = refreshEvidence;
$("exportEvidence").onclick = () =>
  download(
    "einhander-render-evidence.json",
    state.evidence || { status: "No evidence loaded" },
  );
$("compareSlider").oninput = (e) =>
  ($("compareOverlay").style.clipPath =
    `inset(0 ${100 - Number(e.target.value)}% 0 0)`);
$("importKey").onchange = () => {
  const source = state.skins?.source_assets?.find(
    (s) => s.key === $("importKey").value,
  );
  $("comparisonSelect").onchange = renderComparison;
  $("sourceDownload").href = source?.url || "#";
  $("sourceDimensions").textContent = source
    ? `${source.width} × ${source.height} · exact alpha preservation · semantic mapping unverified`
    : "Choose a known texture identity.";
};
$("sourceSearch").oninput = renderSourceOptions;
$("importCandidate").onclick = async () => {
  const file = $("importPng").files[0];
  const name = $("importWorkspace").value.trim();
  const key = $("importKey").value;
  if (!file || !name || !key)
    return toast("Choose a workspace, source identity, and PNG.", true);
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$/.test(name))
    return toast("Choose an existing workspace using its exact name.", true);
  if (file.size > 18 * 1024 * 1024)
    return toast("PNG exceeds the 18 MiB candidate limit.", true);
  const reader = new FileReader();
  reader.onload = async () => {
    const r = await action(
      "Validate skin candidate",
      "/dev/skins",
      {
        action: "import",
        name,
        key,
        png_base64: String(reader.result).split(",")[1],
      },
      "Candidate validated and saved to an inactive draft.",
    );
    $("importStatus").textContent = r
      ? "Imported to draft. In-game mapping remains unverified."
      : "Import failed. See the response in Console.";
    if (r) refreshSkins();
  };
  reader.onerror = () => toast("Could not read PNG.", true);
  reader.readAsDataURL(file);
};
$("captureFrame").onclick = async () => {
  const path = `dev_present_${Date.now()}.png`;
  $("captureStatus").textContent = "Requesting presented framebuffer…";
  $("captureFrame").disabled = true;
  try {
    const before = await api("/cmd", {
      line: JSON.stringify({ cmd: "present_shot_seq" }),
    });
    if (!before.data?.ok)
      throw new Error(before.data?.error || "Capture counter unavailable");
    const request = await api("/cmd", {
      line: JSON.stringify({ cmd: "present_shot", path }),
    });
    if (!request.data?.ok)
      throw new Error(request.data?.error || "Capture was rejected");
    let completed = false;
    for (let i = 0; i < 20; i++) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      const result = await api("/cmd", {
        line: JSON.stringify({ cmd: "present_shot_seq" }),
      });
      if (!result.data?.ok)
        throw new Error(result.data?.error || "Capture polling failed");
      if (result.data.seq !== before.data.seq) {
        if (result.data.wrote !== 1)
          throw new Error("Renderer completed capture without writing a PNG");
        record("Present capture completed", result.data);
        completed = true;
        break;
      }
    }
    if (!completed)
      throw new Error("No completed present capture within five seconds");
    const img = new Image();
    img.alt = "Current native engine presented framebuffer";
    img.onload = () => {
      $("livePreview").replaceChildren(img);
      $("captureStatus").textContent =
        `Captured ${img.naturalWidth} × ${img.naturalHeight} pixels. Output size does not prove texture detail.`;
    };
    img.onerror = () => {
      $("captureStatus").textContent =
        "Engine replied, but the output image could not be loaded.";
    };
    img.src = `/files/${path}?t=${Date.now()}`;
  } catch (e) {
    $("captureStatus").textContent = `Capture failed: ${e.message}`;
    record("Present capture", { ok: false, error: e.message });
    toast(e.message, true);
  } finally {
    $("captureFrame").disabled = !state.status?.connected;
  }
};
const BTN = {
  select: 0xfffe,
  start: 0xfff7,
  up: 0xffef,
  right: 0xffdf,
  down: 0xffbf,
  left: 0xff7f,
  l2: 0xfeff,
  r2: 0xfdff,
  l1: 0xfbff,
  r1: 0xf7ff,
  triangle: 0xefff,
  circle: 0xdfff,
  cross: 0xbfff,
  square: 0x7fff,
};
const pads = [
  ["select", "Select"],
  ["", ""],
  ["up", "↑"],
  ["", ""],
  ["start", "Start"],
  ["l1", "L1"],
  ["left", "←"],
  ["down", "↓"],
  ["right", "→"],
  ["r1", "R1"],
  ["l2", "L2"],
  ["triangle", "△"],
  ["square", "□"],
  ["cross", "×"],
  ["circle", "○"],
];
$("pad").innerHTML = pads
  .map(([id, label]) =>
    id
      ? `<button data-pad="${id}" aria-label="Press ${id}" data-live disabled>${label}</button>`
      : '<span class="blank"></span>',
  )
  .join("");
$("pad").onclick = (e) => {
  const b = e.target.closest("[data-pad]");
  if (b) {
    if (!$("padFrames").reportValidity()) return;
    debug(
      {
        cmd: "press",
        buttons: BTN[b.dataset.pad],
        frames: Number($("padFrames").value),
      },
      `Pad ${b.dataset.pad}`,
    );
  }
};
$("botStart").onclick = async () => {
  if (!$("botHz").reportValidity()) return;
  // Enemy-aware controller uses read-only source geometry and finite pad input.
  // Its live prototype has not established a stage clear.
  const r = await action("Start Robin", "/bot", {
    action: "start",
    name: $("botName").value,
    movement: "combat_lane",
    threat_draw: true,
    hull_guard: true,
    fire_mode: "both",
    autofire: $("botFire").checked,
    weave: $("botWeave").checked,
    dodge: $("botDodge").checked,
    revive: false,
    invincible: false,
    tick: 1 / Number($("botHz").value),
  });
  if (r?.bot) renderBot(r.bot);
};
$("botStop").onclick = async () => {
  const r = await action("Stop Robin", "/bot", { action: "stop" });
  if (r?.bot) renderBot(r.bot);
};
const BOT_MODES = {
  observe: "Waiting for the player ship",
  "await fresh enemy observation": "Waiting for fresh enemy data",
  search: "Searching for a target",
  aim: "Lining up with the target",
  engage: "On target, firing",
  evade: "Evading incoming fire",
};
function botStatusText(bot) {
  if (!bot.running) return "Robin is idle.";
  if (bot.movement !== "combat_lane")
    return `Running an older movement mode (${bot.movement}); restart Robin to use enemy-aware play.`;
  const p = bot.position;
  if (!p) return "Running · waiting for the player ship to be drawn.";
  const c = p.combat || {};
  const parts = [BOT_MODES[c.mode] || c.mode || "Running"];
  if (c.target?.family) parts.push(`target: ${c.target.family}`);
  if (typeof c.target?.aim_error === "number")
    parts.push(`aim offset ${Math.abs(c.target.aim_error).toFixed(0)} px ${c.target.aim_error > 0 ? "below" : "above"}`);
  if (typeof c.visible_enemy_clusters === "number") parts.push(`${c.visible_enemy_clusters} enemies tracked`);
  parts.push(`ship at ${Math.round(p.x)}, ${Math.round(p.y)}`);
  return parts.join(" · ");
}
function renderBot(bot) {
  $("botBadge").textContent = bot.running ? "RUNNING" : "IDLE";
  $("botStatus").textContent = botStatusText(bot);
  $("botLog").textContent =
    (bot.log || []).map((l) => `${l.t} ${l.msg}`).join("\n") ||
    "No bot activity.";
}
async function refreshAutomation() {
  try {
    const [b, d] = await Promise.all([api("/bot/status"), api("/demo/status")]);
    renderBot(b.bot);
    $("demoStatus").textContent = d.demo.message;
  } catch {
    /* Connection state is reported by the primary runtime probe. */
  }
}
$("allowRestore").onchange = () => {
  $("loadState").disabled =
    !$("allowRestore").checked || !state.status?.connected;
};
$("saveState").onclick = () => {
  if ($("stateSlot").reportValidity())
    debug(
      { cmd: "savestate", op: "save", slot: Number($("stateSlot").value) },
      "Save snapshot",
    );
};
$("loadState").onclick = () => {
  if ($("allowRestore").checked && $("stateSlot").reportValidity())
    debug(
      { cmd: "savestate", op: "load", slot: Number($("stateSlot").value) },
      "Known-risk restore",
    );
};
$("rawSend").onclick = () => {
  try {
    const c = JSON.parse($("rawCommand").value);
    if (
      !c ||
      typeof c !== "object" ||
      Array.isArray(c) ||
      typeof c.cmd !== "string"
    )
      throw new Error("A command object with a cmd string is required.");
    debug(c, "Raw command");
  } catch (e) {
    toast(`Invalid command: ${e.message}`, true);
  }
};
$("exportSession").onclick = () =>
  download("einhander-dev-session.json", {
    exported_at: new Date().toISOString(),
    catalog: state.catalog,
    status: state.status,
    evidence: state.evidence,
    activity: state.activity,
    bookmarks: state.bookmarks,
  });
async function init() {
  selectArea(location.hash.slice(1));
  renderBookmarks();
  try {
    state.catalog = await api("/dev/catalog");
    renderFields();
  } catch (e) {
    $("playerFields").innerHTML =
      `<div class="empty-state wide">Field catalog unavailable: ${esc(e.message)}. Start the updated bridge.</div>`;
    $("weaponFields").innerHTML = $("playerFields").innerHTML;
  }
  await Promise.allSettled([
    refreshStatus(),
    refreshSkins(),
    refreshEvidence(),
  ]);
  await refreshAutomation();
  setInterval(() => {
    if (!document.hidden) {
      refreshStatus();
      if (state.active === "automation") refreshAutomation();
    }
  }, 4000);
}
init();
