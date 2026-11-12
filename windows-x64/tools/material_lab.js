/* Live GPU review for ein-material-v3. This previews texture material math,
 * not a captured game scene or new geometry. Stock remains the default. */
(() => {
  "use strict";
  const node = document.createElement("article");
  node.className = "card mt";
  node.id = "materialLab";
  node.innerHTML = `<div class="section-head"><div><h2>Live material lab</h2><p>Compare fourteen finishes and optional authored surface detail on identified texture atlases.</p></div><span class="tag blue">GPU PREVIEW</span></div>
    <div class="form-grid"><label>Player material<select id="materialProfile"><option value="">Loading profiles…</option></select></label><label>Enemy material<select id="materialEnemyProfile"><option value="stock">Stock</option></select></label><label>Exact texture identity<select id="materialTarget"><option value="">Loading targets…</option></select></label></div>
    <div class="form-grid mt"><label>Player surface detail<select id="materialDetail"><option value="none">None · original surface</option></select></label><label>Enemy surface detail<select id="materialEnemyDetail"><option value="none">None · original surface</option></select></label><label>Detail blend · <output id="materialDetailLabel">12%</output><input id="materialDetailStrength" type="range" min="0" max="35" value="12"></label><label>Detail density<input id="materialDetailScale" type="number" min="1" max="64" step="1" value="8"></label></div><div class="row mt"><span class="caps">Preview pairing</span><button id="materialPairCrimson" class="small">Aurora / Crimson</button><button id="materialPairGold" class="small">Aurora / Gold</button></div><div class="form-grid mt"><label>Atlas magnification · <output id="materialZoomLabel">1×</output><input id="materialZoom" type="range" min="1" max="32" value="1"></label><label>Atlas inspection center<input id="materialCenter" type="range" min="0" max="100" value="50"></label></div><div class="form-grid mt"><label>Finish strength · <output id="materialStrengthLabel">75%</output><input id="materialStrength" type="range" min="0" max="100" value="75"></label><label>Reveal original / material<input id="materialSplit" type="range" min="0" max="100" value="50"></label></div>
    <div class="row mt"><label class="check"><input id="materialStock" type="checkbox">Stock material only</label><label class="check"><input id="materialCompareDetail" type="checkbox">Compare detail layer only</label><button id="materialRefresh" class="small">Refresh lab</button><button id="materialExport" class="small" disabled>Export 4K atlas preview</button><button id="materialStage" class="small" disabled>Stage separate preset</button><button id="materialSave" class="primary small" disabled>Save for next launch</button><button id="materialApply" class="small" disabled>Apply colors to running game</button></div>
    <div class="status-line" id="materialSaved" role="status">Checking saved preset…</div><div class="note blue">Live apply changes player and enemy colors together. Save includes surface-detail layers for the next launch using Play-Saved-Skin.cmd. Detail and texture-scope changes require a restart.</div>
    <div class="compare-labels"><span>ORIGINAL TEXTURE</span><span>SELECTED MATERIAL</span></div>
    <canvas id="materialCanvas" width="3840" height="2160" aria-label="GPU atlas material comparison, not a gameplay screenshot" style="width:100%;display:block;border:1px solid var(--line);border-radius:8px;background:#090f18"></canvas>
    <div class="status-line" id="materialStatus" role="status">Initializing material preview…</div><div class="note" id="materialScope">The review canvas is 3840 × 2160; source-art detail is measured separately. A palette shader preserves existing shading. It does not add polygon depth, normal maps, or a new 4K texture. PSX alpha/STP metadata is shown as opaque paint here; actual blend modes need in-game review.</div><pre id="materialReceipt" class="log mt" hidden></pre>`;
  const studio = document.getElementById("view-skins");
  studio.insertBefore(node, studio.children[1]);
  const el = (id) => document.getElementById(id);
  const neonPair = document.createElement("button");
  neonPair.id = "materialPairNeon";
  neonPair.className = "small";
  neonPair.textContent = "Neon / Ultraviolet";
  el("materialPairGold").after(neonPair);
  const lab = {
    data: null,
    gl: null,
    program: null,
    texture: null,
    source: null,
    ready: false,
    loading: false,
    textureLoadVersion: 0,
    detailVersion: 0,
    detailTextures: new Map(),
    detailsReady: true,
    lost: false,
    busy: false,
    pairVersion: 0,
  };
  const VERTEX = `#version 300 es
    in vec2 a_position; uniform vec2 u_fit; out vec2 v_uv;
    void main(){ v_uv=a_position*.5+.5; gl_Position=vec4(a_position*u_fit,0.,1.); }`;
  let FRAGMENT = "";
  function fragment(kernels) {
    return `#version 300 es
    precision highp float;
    uniform sampler2D u_source;
    uniform float u_split,u_zoom,u_center;
    uniform vec2 u_native_size; uniform int u_compare_detail;
    in vec2 v_uv; out vec4 out_color;
    ${kernels.palette}
    ${kernels.detail}
    void main(){
      float center=mix(.5/u_zoom,1.-.5/u_zoom,u_center);
      vec2 uv=vec2(center+(v_uv.x-.5)/u_zoom,1.-v_uv.y);
      vec4 c=texture(u_source,uv);
      if(v_uv.x>u_split || u_compare_detail==1){
        vec3 base=hd_skin_material(c.rgb);
        c.rgb=v_uv.x>u_split?hd_skin_detail_material(base,c.rgb,uv*u_native_size):base;
      }
      // Source alpha encodes PSX transparency/STP classes, not display opacity.
      // Atlas review shows every nontransparent texel opaque. Native blend
      // modes are exercised by the separate runtime shader regression.
      out_color=vec4(c.rgb,c.a>0.?1.:0.);}`;
  }
  function status(message, error = false) {
    el("materialStatus").textContent = message;
    el("materialStatus").style.color = error ? "var(--red)" : "var(--cyan)";
  }
  function syncControls() {
    const ready = lab.ready && lab.detailsReady && !lab.lost && !lab.busy;
    el("materialStage").disabled = !ready;
    el("materialSave").disabled = !ready || !lab.data || !("saved_selection" in lab.data);
    el("materialApply").disabled = !ready || !lab.data?.live_supported?.bridge_available;
    el("materialExport").disabled = !ready;
    for (const id of ["materialPairGold", "materialPairCrimson", "materialPairNeon"]) el(id).disabled = !ready;
  }
  function showSaved(saved) {
    el("materialSaved").textContent = saved?.valid
      ? `Saved for next launch: ${saved.profile} / ${saved.enemy_profile} · detail ${saved.detail_map} / ${saved.enemy_detail_map}. The running game is unchanged.`
      : saved?.exists
        ? `Saved preset needs attention: ${saved.error || saved.status}`
        : "No saved preset yet. Choose finishes and save when ready.";
  }
  async function verifiedBitmap(url, receipt) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error("Texture PNG unavailable");
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength > 64 * 1024 * 1024)
      throw new Error("Texture PNG exceeds the native file limit");
    const digest = [
      ...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    ]
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    if (digest !== receipt.sha256)
      throw new Error("Texture PNG changed since its receipt");
    const image = await createImageBitmap(
      new Blob([bytes], { type: "image/png" }),
      { premultiplyAlpha: "none", colorSpaceConversion: "none" },
    );
    if (
      image.width !== receipt.width ||
      image.height !== receipt.height ||
      image.width > 4096 ||
      image.height > 4096
    ) {
      image.close();
      throw new Error("Texture PNG dimensions differ from the source receipt");
    }
    return image;
  }
  async function request(path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const r = await fetch(path, {
        method: body ? "POST" : "GET",
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      const data = await r.json();
      if (!r.ok || data.ok === false)
        throw new Error(data.error || `HTTP ${r.status}`);
      return data;
    } finally {
      clearTimeout(timer);
    }
  }
  function shader(gl, type, source) {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(s);
      gl.deleteShader(s);
      throw new Error(message);
    }
    return s;
  }
  function initializeGPU(kernels) {
    if (
      typeof kernels.palette !== "string" ||
      typeof kernels.detail !== "string"
    )
      throw new Error(
        "Shared renderer kernels are missing. Rebuild the material runtime.",
      );
    FRAGMENT = fragment(kernels);
    const gl = el("materialCanvas").getContext("webgl2", {
      alpha: true,
      preserveDrawingBuffer: true,
      antialias: false,
    });
    if (!gl)
      throw new Error(
        "WebGL 2 is unavailable. Source artwork can still be inspected in the gallery.",
      );
    const p = gl.createProgram(),
      vs = shader(gl, gl.VERTEX_SHADER, VERTEX),
      fs = shader(gl, gl.FRAGMENT_SHADER, FRAGMENT);
    gl.attachShader(p, vs);
    gl.attachShader(p, fs);
    gl.linkProgram(p);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS))
      throw new Error(gl.getProgramInfoLog(p));
    gl.useProgram(p);
    gl.uniform1i(
      gl.getUniformLocation(p, "u_compare_detail"),
      el("materialCompareDetail").checked ? 1 : 0,
    );
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const attr = gl.getAttribLocation(p, "a_position");
    gl.enableVertexAttribArray(attr);
    gl.vertexAttribPointer(attr, 2, gl.FLOAT, false, 0, 0);
    lab.gl = gl;
    lab.program = p;
    lab.texture = gl.createTexture();
    lab.neutralDetail = gl.createTexture();
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, lab.neutralDetail);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      1,
      1,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      new Uint8Array([128, 128, 128, 255]),
    );
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.activeTexture(gl.TEXTURE0);
  }
  function rgb(value) {
    if (Array.isArray(value) && value.length === 3)
      return value.map((v) => (v > 1 ? v / 255 : v));
    const hex = String(value || "#ffffff").replace("#", "");
    return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  }
  function profile() {
    const target = lab.data?.targets?.find(
      (t) => t.key === el("materialTarget").value,
    );
    const selector =
      target?.group === "enemy" ? "materialEnemyProfile" : "materialProfile";
    return lab.data?.profiles?.find((p) => p.id === el(selector).value);
  }
  function render() {
    if (!lab.ready || lab.lost) return;
    const gl = lab.gl,
      p = lab.program,
      chosen = profile();
    if (!chosen) return;
    gl.viewport(0, 0, 3840, 2160);
    gl.clearColor(0.035, 0.055, 0.085, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(p);
    const zoom = Number(el("materialZoom").value);
    gl.uniform1i(
      gl.getUniformLocation(p, "u_compare_detail"),
      el("materialCompareDetail").checked ? 1 : 0,
    );
    const aspect = lab.source.width / lab.source.height / zoom;
    gl.uniform1f(gl.getUniformLocation(p, "u_zoom"), zoom);
    gl.uniform1f(
      gl.getUniformLocation(p, "u_center"),
      Number(el("materialCenter").value) / 100,
    );
    gl.uniform2f(
      gl.getUniformLocation(p, "u_fit"),
      Math.min(1, aspect / (16 / 9)),
      Math.min(1, 16 / 9 / aspect),
    );
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, lab.texture);
    gl.uniform1i(gl.getUniformLocation(p, "u_source"), 0);
    gl.uniform3fv(
      gl.getUniformLocation(p, "u_skin_primary"),
      rgb(chosen.primary),
    );
    gl.uniform3fv(
      gl.getUniformLocation(p, "u_skin_accent"),
      rgb(chosen.accent),
    );
    gl.uniform1f(
      gl.getUniformLocation(p, "u_skin_strength"),
      Number(el("materialStrength").value) / 100,
    );
    gl.uniform1f(
      gl.getUniformLocation(p, "u_split"),
      Number(el("materialSplit").value) / 100,
    );
    gl.uniform1i(
      gl.getUniformLocation(p, "u_skin_enabled"),
      el("materialStock").checked || chosen.id === "stock" ? 0 : 1,
    );
    const target = lab.data.targets.find((t) => t.key === lab.source.key);
    const detailId = el(
      target?.group === "enemy" ? "materialEnemyDetail" : "materialDetail",
    ).value;
    const detailTexture = lab.detailTextures.get(detailId)?.texture;
    gl.uniform2f(
      gl.getUniformLocation(p, "u_native_size"),
      target?.native_width || 64,
      target?.native_height || 64,
    );
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, detailTexture || lab.neutralDetail);
    gl.uniform1i(gl.getUniformLocation(p, "u_skin_detail"), 1);
    gl.uniform1i(
      gl.getUniformLocation(p, "u_skin_detail_enabled"),
      !el("materialStock").checked && detailTexture ? 1 : 0,
    );
    gl.uniform1f(
      gl.getUniformLocation(p, "u_skin_detail_strength"),
      Number(el("materialDetailStrength").value) / 100,
    );
    gl.uniform1f(
      gl.getUniformLocation(p, "u_skin_detail_scale"),
      Number(el("materialDetailScale").value) || 8,
    );
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    const error = gl.getError();
    if (error !== gl.NO_ERROR) status(`GPU preview failed: GL ${error}`, true);
  }
  async function loadTexture() {
    const version = ++lab.textureLoadVersion;
    lab.ready = false;
    syncControls();
    const target = lab.data?.targets?.find(
      (t) => t.key === el("materialTarget").value,
    );
    if (!target) return;
    const url = target.url || target.source_url;
    if (typeof url !== "string" || !url.startsWith("/dev/skins/source/"))
      throw new Error("Material source must be a known local texture.");
    const img = await verifiedBitmap(url, target);
    if (
      version !== lab.textureLoadVersion ||
      el("materialTarget").value !== target.key ||
      lab.lost
    ) {
      img.close();
      return;
    }
    const sourceWidth = img.width,
      sourceHeight = img.height;
    const gl = lab.gl;
    gl.bindTexture(gl.TEXTURE_2D, lab.texture);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    img.close();
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    lab.source = {
      key: target.key,
      width: sourceWidth,
      height: sourceHeight,
    };
    lab.ready = true;
    render();
    syncControls();
    status(
      `GPU review ready · source ${sourceWidth} × ${sourceHeight} · viewport 3840 × 2160 · exact key ${target.key}. This is an atlas review, not gameplay.${target.default_selected === false ? " This shared mechanical atlas is excluded from default staging; component ownership is unpartitioned." : " Body-atlas ownership is observed; craft-specific and built-in-gun isolation still require validation."}`,
    );
  }
  async function refresh() {
    if (lab.loading) return;
    lab.loading = true;
    ++lab.textureLoadVersion;
    ++lab.detailVersion;
    lab.ready = false;
    lab.detailsReady = false;
    syncControls();
    status("Refreshing verified material sources…");
    try {
      if (!lab.gl)
        initializeGPU(
          await request("/files/tools/material-shader-kernels.json"),
        );
      lab.data = await request("/dev/materials");
      const selected = el("materialProfile").value;
      const enemySelected = el("materialEnemyProfile").value;
      const selectedTarget = el("materialTarget").value;
      el("materialProfile").replaceChildren();
      el("materialEnemyProfile").replaceChildren();
      for (const selector of ["materialProfile", "materialEnemyProfile"]) {
        const groups = new Map();
        for (const p of lab.data.profiles || []) {
          const option = new Option(p.label || p.name, p.id);
          if (p.id === "stock") {
            el(selector).append(option);
            continue;
          }
          const category = p.category || "Vibrant-Elemental";
          if (!groups.has(category)) {
            const group = document.createElement("optgroup");
            group.label = category;
            groups.set(category, group);
            el(selector).append(group);
          }
          groups.get(category).append(option);
        }
      }
      if ((lab.data.profiles || []).some((p) => p.id === selected))
        el("materialProfile").value = selected;
      if ((lab.data.profiles || []).some((p) => p.id === enemySelected))
        el("materialEnemyProfile").value = enemySelected;
      for (const id of ["materialDetail", "materialEnemyDetail"]) {
        const selectedDetail = el(id).value;
        el(id).replaceChildren(new Option("None · original surface", "none"));
        for (const map of lab.data.detail_maps || [])
          el(id).add(
            new Option(`${map.label} · ${map.width}×${map.height}`, map.id),
          );
        if ([...el(id).options].some((o) => o.value === selectedDetail))
          el(id).value = selectedDetail;
      }
      el("materialTarget").replaceChildren();
      for (const t of lab.data.targets || [])
        el("materialTarget").add(
          new Option(
            `${t.group || "atlas"} · ${t.label || t.key} · ${t.width}×${t.height}`,
            t.key,
          ),
        );
      if (lab.data.targets.some((t) => t.key === selectedTarget)) el("materialTarget").value = selectedTarget;
      await loadTexture();
      await loadDetails();
      if ("saved_selection" in lab.data) showSaved(lab.data.saved_selection);
      else el("materialSaved").textContent = "Restart the local development bridge to activate saved presets and live color controls. Atlas preview and separate staging remain available.";
    } catch (e) {
      status(`Material lab: ${e.message}`, true);
    } finally {
      lab.loading = false;
    }
  }
  el("materialRefresh").onclick = refresh;
  el("materialProfile").onchange = render;
  el("materialEnemyProfile").onchange = render;
  async function detailTexture(identity) {
    if (identity === "none") return null;
    const map = lab.data.detail_maps.find((m) => m.id === identity);
    if (!map || !map.url.startsWith("/files/tools/skin_collection/materials/"))
      throw new Error("Unknown local authored detail map");
    const existing = lab.detailTextures.get(identity);
    if (existing?.sha256 === map.sha256) return existing.promise;
    if (existing?.texture) lab.gl.deleteTexture(existing.texture);
    const entry = { texture: null, promise: null, sha256: map.sha256 };
    entry.promise = (async () => {
      const image = await verifiedBitmap(map.url, map);
      if (lab.lost || lab.detailTextures.get(identity) !== entry) {
        image.close();
        return null;
      }
      const gl = lab.gl,
        texture = gl.createTexture();
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        image,
      );
      image.close();
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.MIRRORED_REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.MIRRORED_REPEAT);
      gl.texParameteri(
        gl.TEXTURE_2D,
        gl.TEXTURE_MIN_FILTER,
        gl.LINEAR_MIPMAP_LINEAR,
      );
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.generateMipmap(gl.TEXTURE_2D);
      const error = gl.getError();
      if (error !== gl.NO_ERROR) {
        gl.deleteTexture(texture);
        throw new Error(`Detail GPU upload error ${error}`);
      }
      entry.texture = texture;
      return texture;
    })();
    lab.detailTextures.set(identity, entry);
    try {
      return await entry.promise;
    } catch (e) {
      if (lab.detailTextures.get(identity) === entry)
        lab.detailTextures.delete(identity);
      throw e;
    }
  }
  async function loadDetails() {
    const version = ++lab.detailVersion;
    lab.detailsReady = false;
    syncControls();
    status("Loading and checking selected surface-detail textures…");
    try {
      await Promise.all([
        detailTexture(el("materialDetail").value),
        detailTexture(el("materialEnemyDetail").value),
      ]);
      if (version !== lab.detailVersion || lab.lost) return;
      lab.detailsReady = true;
      render();
      status(
        `GPU review ready · source ${lab.source?.width} × ${lab.source?.height} · 3840 × 2160 atlas viewport. Authored layers: player ${el("materialDetail").selectedOptions[0].textContent}; enemy ${el("materialEnemyDetail").selectedOptions[0].textContent}. Gameplay remains unverified.`,
      );
    } catch (e) {
      if (version === lab.detailVersion)
        status(`Detail preview: ${e.message}`, true);
    } finally {
      if (version === lab.detailVersion) syncControls();
    }
  }
  el("materialDetail").onchange = loadDetails;
  el("materialEnemyDetail").onchange = loadDetails;
  el("materialDetailStrength").oninput = () => {
    el("materialDetailLabel").textContent =
      `${el("materialDetailStrength").value}%`;
    render();
  };
  el("materialDetailScale").oninput = () => {
    if (el("materialDetailScale").checkValidity()) render();
  };
  el("materialZoom").oninput = () => {
    el("materialZoomLabel").textContent = `${el("materialZoom").value}×`;
    render();
  };
  el("materialCenter").oninput = render;
  el("materialCompareDetail").onchange = () => {
    const labels = node.querySelectorAll(".compare-labels span");
    labels[0].textContent = el("materialCompareDetail").checked
      ? "PALETTE ONLY"
      : "ORIGINAL TEXTURE";
    labels[1].textContent = el("materialCompareDetail").checked
      ? "WITH AUTHORED DETAIL"
      : "SELECTED MATERIAL";
    render();
  };
  async function previewPair(enemy) {
    if (!lab.data) return;
    el("materialProfile").value = "aurora-teal";
    el("materialEnemyProfile").value = enemy;
    el("materialStock").checked = false;
    const target = lab.data.targets.find((t) => t.group === "enemy");
    if (target) {
      el("materialTarget").value = target.key;
      el("materialZoom").value = "16";
      el("materialZoomLabel").textContent = "16×";
      el("materialCenter").value = "9";
      await loadTexture();
    } else render();
  }
  async function previewDetailedPair(enemy, playerDetail, enemyDetail) {
    const version = ++lab.pairVersion;
    await previewPair(enemy);
    if (version !== lab.pairVersion || lab.lost) return;
    el("materialDetail").value = playerDetail;
    el("materialEnemyDetail").value = enemyDetail;
    await loadDetails();
  }
  el("materialPairGold").onclick = () =>
    previewDetailedPair("gold-obsidian", "titanium-teal-nanoceramic", "gold-obsidian-engraved").catch((e) => status(e.message, true));
  el("materialPairCrimson").onclick = () =>
    previewDetailedPair("crimson-red", "titanium-teal-nanoceramic", "crimson-gold-plating").catch((e) => status(e.message, true));
  neonPair.onclick = async () => {
    const version = ++lab.pairVersion;
    try {
      await previewPair("ultraviolet-grid");
      if (version !== lab.pairVersion || lab.lost) return;
      el("materialProfile").value = "neon-circuit";
      el("materialDetail").value = "neon-circuit-tracery";
      el("materialEnemyDetail").value = "ultraviolet-plasma-grid";
      await loadDetails();
    } catch (e) { status(e.message, true); }
  };
  el("materialTarget").onchange = () =>
    loadTexture().catch((e) => status(e.message, true));
  el("materialStrength").oninput = () => {
    el("materialStrengthLabel").textContent =
      `${el("materialStrength").value}%`;
    render();
  };
  el("materialSplit").oninput = render;
  el("materialStock").onchange = () => {
    if (el("materialStock").checked) {
      lab.detailsReady = true;
      syncControls();
      render();
    } else loadDetails();
  };
  function selection(action) {
    return {
      action,
      profile: el("materialStock").checked ? "stock" : el("materialProfile").value,
      strength: Number(el("materialStrength").value) / 100,
      enemy_profile: el("materialStock").checked ? "stock" : el("materialEnemyProfile").value,
      enemy_strength: Number(el("materialStrength").value) / 100,
      ...(action === "apply" ? {} : {
        detail_map: el("materialStock").checked ? "none" : el("materialDetail").value,
        enemy_detail_map: el("materialStock").checked ? "none" : el("materialEnemyDetail").value,
        detail_strength: Number(el("materialDetailStrength").value) / 100,
        enemy_detail_strength: Number(el("materialDetailStrength").value) / 100,
        detail_scale: Number(el("materialDetailScale").value),
        enemy_detail_scale: Number(el("materialDetailScale").value),
      }),
    };
  }
  async function submit(action) {
    if (lab.busy || !lab.ready || !lab.detailsReady || lab.lost) return;
    if (!el("materialDetailScale").checkValidity()) {
      el("materialDetailScale").reportValidity();
      return;
    }
    lab.busy = true;
    syncControls();
    try {
      const result = await request("/dev/materials", selection(action));
      el("materialReceipt").hidden = false;
      el("materialReceipt").textContent = JSON.stringify(result, null, 2);
      if (action === "save") showSaved(result.saved_selection);
      status(action === "apply"
        ? "Player and enemy colors acknowledged by the running engine. Detail layers are unchanged. This choice is not saved."
        : action === "save"
          ? "Preset saved and verified. Open Play-Saved-Skin.cmd for your next run; no game was started."
          : "Separate preset staged with exact texture scope. No game was started.");
    } catch (e) {
      status(`${action === "apply" ? "Live colors" : "Preset"}: ${e.message}`, true);
    } finally {
      lab.busy = false;
      syncControls();
    }
  }
  el("materialStage").onclick = () => submit("stage");
  el("materialSave").onclick = () => submit("save");
  el("materialApply").onclick = () => submit("apply");
  el("materialExport").onclick = () => {
    if (!lab.ready || !lab.detailsReady || lab.lost)
      return status("Wait for all selected textures to finish checking.", true);
    render();
    el("materialCanvas").toBlob((blob) => {
      if (!blob) return status("PNG export failed.", true);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${profile().id}-atlas-3840x2160-preview.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, "image/png");
  };
  el("materialCanvas").addEventListener("webglcontextlost", (e) => {
    e.preventDefault();
    lab.lost = true;
    ++lab.textureLoadVersion;
    ++lab.detailVersion;
    lab.detailsReady = false;
    lab.ready = false;
    syncControls();
    status(
      "GPU context lost. Reload this workspace to rebuild the material review.",
      true,
    );
  });
  // Exposed only for read-only local acceptance probes and source equation QA.
  window.einMaterialLab = {
    contract: "ein-material-v3",
    refresh,
    get ready() {
      return lab.ready;
    },
    get source() {
      return lab.source;
    },
    get shader() {
      return FRAGMENT;
    },
  };
  refresh();
})();
