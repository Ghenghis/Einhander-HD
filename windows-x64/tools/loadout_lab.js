/* Identity and coverage browser. Catalog facts never imply a RAM unlock or
 * an independently mapped weapon texture. Art remains separate from bindings. */
(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const escape = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const localURL = (value) =>
    typeof value === "string" &&
    value.startsWith("/files/tools/skin_collection/") &&
    !value.startsWith("//")
      ? value
      : "";
  let catalog = null,
    artwork = null,
    bossArtwork = null;
  const article = document.createElement("article");
  article.className = "card mt";
  article.id = "equipmentCoverage";
  article.innerHTML = `<div class="section-head"><div><h2>Ships, guns & equipment</h2><p>Craft identity, built-in weapons, and detachable Gunpods are separate production assets.</p></div><button class="small" id="refreshLoadouts">Refresh coverage</button></div><div id="loadoutCoverageStatus" class="note blue">Loading the source-backed roster…</div><div class="section-head mt"><h2>Player craft</h2><span class="tag dim">PER-CRAFT CAPACITY</span></div><div id="shipRoster" class="grid"></div><div class="section-head mt"><h2>Detachable Gunpods</h2><span class="tag blue">SHARED EQUIPMENT IDENTITIES</span></div><div id="gunpodRoster" class="grid three"></div><div class="section-head mt"><h2>Model-specific finish studies</h2><span class="tag amber">ARTWORK ≠ UV BINDING</span></div><div id="equipmentArtGallery" class="skin-gallery"></div><div class="note mt">A hull finish does not identify a built-in gun or a pickup Gunpod. Shared mechanical atlases stay stock by default. Independent gun, equipment, boss-part, and craft unlock controls require validated identities and behavior.</div><div id="loadoutSources" class="mt muted"></div>`;
  byId("view-skins").append(article);
  const sourcePanel = document.createElement("article");
  sourcePanel.className = "card wide";
  sourcePanel.id = "loadoutSummary";
  sourcePanel.innerHTML = `<div class="section-head"><h2>Craft & equipment reference</h2><button class="small" id="openEquipmentCoverage">Open model coverage ↗</button></div><p id="loadoutQuickFacts">Loading verified starter craft and Gunpod capacities…</p><div class="note">The current developer controls do not include a verified ship unlocker or gun-type selector. Gallery flags do not establish ship unlock behavior.</div>`;
  byId("weaponFields").parentElement.insertBefore(
    sourcePanel,
    byId("weaponFields"),
  );
  // Keep this large production workspace navigable as its library grows.
  const studio = byId("view-skins");
  const gallery = byId("skinArtGallery").closest("article");
  gallery.id = "finishCollection";
  const authoring = byId("skinName").closest(".grid");
  authoring.id = "packAuthoring";
  const subareas = [
    ["materials", "Live materials", byId("materialLab")],
    ["finishes", "Finish library", gallery],
    ["equipment", "Ships & equipment", article],
    ["authoring", "Pack authoring", authoring],
  ];
  const nav = document.createElement("div");
  nav.className = "row mt";
  nav.setAttribute("role", "tablist");
  nav.setAttribute("aria-label", "Skin production sections");
  for (const [id, label, panel] of subareas) {
    const b = document.createElement("button");
    b.className = "small";
    b.type = "button";
    b.id = `skin-tab-${id}`;
    b.dataset.skinArea = id;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-controls", panel.id);
    b.textContent = label;
    nav.append(b);
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", b.id);
  }
  studio.insertBefore(nav, studio.children[1]);
  function openArea(id, focus = false) {
    for (const [key, , panel] of subareas) {
      const selected = id === key;
      panel.hidden = !selected;
      const button = byId(`skin-tab-${key}`);
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
      button.classList.toggle("primary", selected);
    }
    try {
      sessionStorage.setItem("ein.skin.area", id);
    } catch {}
    if (focus) byId(`skin-tab-${id}`).focus();
  }
  window.openSkinArea = openArea;
  nav.onclick = (e) => {
    const b = e.target.closest("[data-skin-area]");
    if (b) openArea(b.dataset.skinArea);
  };
  nav.onkeydown = (e) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const current = nav.querySelector("[aria-selected=true]").dataset.skinArea;
    let i = subareas.findIndex((a) => a[0] === current);
    i =
      e.key === "Home"
        ? 0
        : e.key === "End"
          ? subareas.length - 1
          : (i + (e.key === "ArrowRight" ? 1 : -1) + subareas.length) %
            subareas.length;
    openArea(subareas[i][0], true);
  };
  let initial = "materials";
  try {
    const saved =
      new URLSearchParams(location.search).get("skinArea") ||
      sessionStorage.getItem("ein.skin.area");
    if (subareas.some((a) => a[0] === saved)) initial = saved;
  } catch {}
  openArea(initial);
  byId("openEquipmentCoverage").onclick = () => {
    document.querySelector('[data-area="skins"]').click();
    openArea("equipment");
  };
  const evidenceLabel = (e) =>
    typeof e === "string" ? e.replace(/_/g, " ") : e?.status || "See source";
  const enemySection = document.createElement("section");
  enemySection.className = "mt";
  enemySection.innerHTML =
    '<h2>Enemy model coverage</h2><p id="enemyCoverageSummary">Verifying named enemy models from original gallery references…</p><details><summary>Browse named families and variants</summary><label class="mt">Find enemy model<input id="enemySearch" type="search" placeholder="Name, designation, or kind"></label><div id="enemyFamilyList" class="grid three mt"></div></details><div class="note mt">Gallery views, named model groups, and runtime enemy types are different counts. Hulls, weapons, boss parts, projectiles, and repeated views are tracked separately.</div>';
  article.insertBefore(
    enemySection,
    byId("equipmentArtGallery").previousElementSibling,
  );
  const shipHeading = byId("shipRoster").previousElementSibling;
  const podHeading = byId("gunpodRoster").previousElementSibling;
  const artHeading = byId("equipmentArtGallery").previousElementSibling;
  article.insertBefore(artHeading, shipHeading);
  article.insertBefore(byId("equipmentArtGallery"), shipHeading);
  const filters = document.createElement("div");
  filters.className = "form-grid mt";
  filters.innerHTML =
    '<label>Find a finish study<input id="equipmentArtSearch" type="search" placeholder="Ship or weapon name"></label><label>Asset category<select id="equipmentArtCategory"><option value="all">All designs</option><option value="hull">Ships</option><option value="gunpod">Gunpods</option><option value="boss">Boss studies</option></select></label>';
  article.insertBefore(filters, byId("equipmentArtGallery"));
  const referenceDetails = document.createElement("details");
  referenceDetails.className = "mt";
  const referenceTitle = document.createElement("summary");
  referenceTitle.textContent =
    "Craft specifications, weapon roster, and enemy coverage";
  referenceDetails.append(referenceTitle);
  for (const item of [
    shipHeading,
    byId("shipRoster"),
    podHeading,
    byId("gunpodRoster"),
    enemySection,
    byId("loadoutSources"),
  ])
    referenceDetails.append(item);
  article.append(referenceDetails);
  byId("equipmentArtSearch").value = (
    new URLSearchParams(location.search).get("asset") || ""
  ).slice(0, 64);
  byId("equipmentArtSearch").oninput = renderArtwork;
  byId("equipmentArtCategory").onchange = renderArtwork;
  let enemyCatalog = null;
  function renderEnemies() {
    const summary = enemyCatalog?.summary;
    if (!summary) return;
    byId("enemyCoverageSummary").textContent =
      `${summary.gallery_enemy_entries} original gallery views · ${summary.normalized_family_groups} conservatively grouped model/designation families · ${summary.mapped_families} observed runtime family mapped across ${summary.mapped_texture_keys} texture keys. This includes bosses and ground units; it is not an exhaustive count of enemy aircraft. Gold and crimson material options are staged for the mapped family.`;
    const query = byId("enemySearch").value.toLowerCase();
    const rows = (enemyCatalog.families || []).filter((f) =>
      JSON.stringify(f).toLowerCase().includes(query),
    );
    byId("enemyFamilyList").innerHTML =
      rows
        .map(
          (f) =>
            `<div class="record"><div class="row spread"><strong>${escape(f.name)}</strong><span class="tag dim">${escape(f.kind || "model")}</span></div><p class="mt">${escape(evidenceLabel(f.evidence))}</p><span class="tag amber">INDEPENDENT BINDING UNVERIFIED</span></div>`,
        )
        .join("") || "<p>No matching model groups.</p>";
  }
  byId("enemySearch").oninput = renderEnemies;
  function originalReference(entity) {
    const path = entity.art_reference?.local_path?.replace(/\\/g, "/") || "";
    const filename = path.split("/").pop();
    if (
      !path.includes("/dev-center-evidence/identity-references/") ||
      !/^[A-Za-z0-9_-]+\.png$/.test(filename)
    )
      return "";
    return `<details class="mt"><summary>Original game design reference</summary><figure class="preview mt"><img src="/dev/evidence/files/identity-references/${filename}" alt="Original game gallery reference for ${escape(entity.name)}" loading="lazy"><figcaption>Original gallery illustration; texture binding and current gameplay appearance are separate checks.</figcaption></figure></details>`;
  }
  function render() {
    const ships = catalog?.ships || [],
      pods = catalog?.gunpods || [];
    const starters = ships.filter(
      (s) =>
        s.availability === "starter" ||
        s.availability === "standard" ||
        s.starter === true,
    );
    byId("loadoutCoverageStatus").textContent =
      `${ships.length} cataloged craft · ${pods.length} Gunpod identities · 14 reusable finish palettes. Starter facts and reported secret content have separate evidence labels. In-game bindings and unlock writes are tracked independently.`;
    byId("shipRoster").innerHTML = ships
      .map(
        (s) =>
          `<article class="card"><div class="row spread"><h3>${escape(s.name)}</h3><span class="tag ${/secret|unlock/i.test(s.availability) ? "amber" : "blue"}">${escape((s.availability || "Catalog").replace(/_/g, " "))}</span></div><p class="mt">${escape(s.description || "Distinct craft identity; model-specific texture binding remains under review.")}</p><div class="record-list"><div class="record"><strong>Gunpod capacity</strong><br>${escape(s.carried_gunpods ?? "Unverified")} carried · ${escape(s.active_gunpods ?? "Unverified")} active</div><div class="record"><strong>Built-in weapon</strong><br>${escape(typeof s.built_in_weapon === "string" ? s.built_in_weapon : s.built_in_weapon?.name || "See original source")}</div><div class="record"><strong>Unlock / availability</strong><br>${escape(s.unlock?.requirement || s.unlock?.status || s.availability || "Not verified")}</div></div><p class="mt">Evidence: ${escape(evidenceLabel(s.evidence))}<br>Independent hull / gun binding: not yet validated.</p></article>`,
      )
      .join("");
    byId("shipRoster")
      .querySelectorAll("article")
      .forEach((card, index) =>
        card.insertAdjacentHTML("beforeend", originalReference(ships[index])),
      );
    byId("gunpodRoster").innerHTML = pods
      .map(
        (p) =>
          `<div class="record"><div class="row spread"><strong>${escape(p.name)}</strong><span class="tag ${/secret|reported/i.test(p.availability) ? "amber" : "dim"}">${escape((p.availability || "Common").replace(/_/g, " "))}</span></div><p class="mt">${escape(p.description || "Detachable equipment; owned separately from the hull and built-in gun.")}</p><span class="caps">${escape(evidenceLabel(p.evidence))}</span></div>`,
      )
      .join("");
    [...byId("gunpodRoster").children].forEach((card, index) =>
      card.insertAdjacentHTML("beforeend", originalReference(pods[index])),
    );
    byId("loadoutQuickFacts").textContent = starters.length
      ? starters
          .map(
            (s) =>
              `${s.name}: ${s.carried_gunpods ?? "?"} carried / ${s.active_gunpods ?? "?"} active Gunpods`,
          )
          .join(" · ")
      : "See source roster for each craft’s carried and active Gunpods.";
    const refs = catalog?.references || [];
    byId("loadoutSources").replaceChildren();
    for (const ref of refs) {
      if (!/^https:\/\//.test(ref.url || "")) continue;
      const a = document.createElement("a");
      a.href = ref.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = ref.title || ref.id || "Source";
      a.style.marginRight = "16px";
      byId("loadoutSources").append(a);
    }
    renderArtwork();
  }
  function renderArtwork() {
    const equipmentImages =
      artwork?.items ||
      artwork?.assets ||
      artwork?.artworks ||
      artwork?.equipment ||
      [];
    const allImages = equipmentImages.concat(bossArtwork?.items || []);
    const query = byId("equipmentArtSearch").value.toLowerCase();
    const category = byId("equipmentArtCategory").value;
    const images = allImages.filter(
      (a) =>
        `${a.name} ${a.entity_id}`.toLowerCase().includes(query) &&
        (category === "all" ||
          a.hull_or_gunpod === category ||
          a.category === category ||
          (category === "boss" && /boss/.test(a.category || ""))),
    );
    byId("equipmentArtGallery").innerHTML = images.length
      ? images
          .map(
            (a) =>
              `<article class="card skin-card">${localURL(a.preview || a.image || a.url) ? `<a href="${escape(localURL(a.image || a.preview || a.url))}" target="_blank" rel="noopener"><img src="${escape(localURL(a.preview || a.image || a.url))}" alt="${escape(a.name)} finish study" loading="lazy"></a>` : ""}<div class="skin-info"><div class="row spread"><h3>${escape(a.name || a.entity_id)}</h3><span class="tag blue">${escape((a.category || a.hull_or_gunpod || "Equipment").replace(/_/g, " "))}</span></div><p>${escape(a.description || "Identity reference for an authored finish; concept art is not an installed game texture.")}</p><div class="mono muted">${escape(a.width || a.dimensions?.[0] || "?")} × ${escape(a.height || a.dimensions?.[1] || "?")}</div><span class="tag amber mt">CONCEPT · UNMAPPED</span></div></article>`,
          )
          .join("")
      : '<div class="empty-state wide">Model-specific artwork is in production from original manual and game gallery references. Refresh coverage as new studies are saved.</div>';
    if (artwork) {
      const progress = document.createElement("p");
      progress.className = "wide muted";
      progress.textContent = `${(artwork.completed ?? equipmentImages.length) + (bossArtwork?.completed || 0)} of ${(artwork.total ?? equipmentImages.length) + (bossArtwork?.total || 0)} reference-based studies saved · ${images.length} shown. All are concept artwork; independent runtime bindings remain unverified. Boss geometry, animation, attacks and physics have not been modified.`;
      byId("equipmentArtGallery").prepend(progress);
    }
  }
  async function refresh() {
    try {
      const r = await fetch("/files/tools/loadout_catalog.json");
      if (!r.ok)
        throw new Error("Roster source catalog is still being verified");
      catalog = await r.json();
      render();
    } catch (e) {
      byId("loadoutCoverageStatus").textContent = e.message;
    }
    try {
      const r = await fetch("/files/tools/skin_collection/equipment-art.json");
      if (r.ok) {
        artwork = await r.json();
        renderArtwork();
      }
    } catch {
      /* Source studies can still be in production. */
    }
    try {
      const r = await fetch(
        "/files/tools/skin_collection/bosses/boss-art.json",
      );
      if (r.ok) {
        bossArtwork = await r.json();
        renderArtwork();
      }
    } catch {
      /* Boss concepts require separately verified source references. */
    }
    try {
      const r = await fetch("/files/tools/enemy_catalog.json");
      if (r.ok) {
        enemyCatalog = await r.json();
        renderEnemies();
      }
    } catch {
      /* Catalog publication may still be in progress. */
    }
  }
  byId("refreshLoadouts").onclick = refresh;
  refresh();
})();
