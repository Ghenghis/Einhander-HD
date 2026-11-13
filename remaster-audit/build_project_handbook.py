"""Build the offline project handbook from reviewed notes and bounded source inventories.

No game, model, network, deployment, or private-data export. Run from any cwd.
Literal environment references are an inventory, not a claim that every dynamic
configuration name or effective default has been resolved.
"""
from __future__ import annotations
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/handbook'


def repo(path, label=None):
    return f'<a href="../../{escape(path, quote=True)}">{escape(label or path)}</a>'


def command(text):
    return '<pre><code>' + escape(text.strip()) + '</code></pre>'


CSS = '''
:root{color-scheme:light dark;--bg:#f8f8f5;--ink:#202821;--muted:#566359;--line:#cad2c8;--paper:#fff;--accent:#285c42}
@media(prefers-color-scheme:dark){:root{--bg:#121714;--ink:#e3e9e2;--muted:#a6b5a8;--line:#38473b;--paper:#1c241f;--accent:#a4cfb2}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,Segoe UI,sans-serif}
a{color:var(--accent);text-underline-offset:.18em}a:hover{text-decoration-thickness:2px}
.shell{display:grid;grid-template-columns:240px minmax(0,980px);gap:48px;max-width:1350px;margin:auto;padding:36px 28px 80px}
nav{position:sticky;top:24px;align-self:start;font-size:14px}nav a{display:block;padding:5px 0}nav [aria-current=page]{font-weight:750}
nav strong{display:block;font-size:19px;margin-bottom:12px}main{min-width:0}h1{font-size:32px;line-height:1.2;margin:12px 0 16px}h2{font-size:23px;margin-top:40px}h3{font-size:18px;margin-top:26px}
.eyebrow,.meta,footer{font-size:13px;color:var(--muted)}.lead{font-size:19px;max-width:75ch}.notice{border-left:4px solid var(--accent);padding:10px 18px;background:var(--paper)}
pre{background:var(--paper);padding:16px;overflow:auto;border:1px solid var(--line);font-size:13px;line-height:1.55}code{font-family:Consolas,monospace;font-size:.9em;overflow-wrap:anywhere}
li{margin:7px 0}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted)}.scroll{overflow:auto}
details{border-top:1px solid var(--line);padding:12px 0}summary{cursor:pointer;font-weight:650}input{font:inherit;width:100%;padding:12px;border:1px solid var(--line);background:var(--paper);color:var(--ink);margin:12px 0}video,audio{width:100%;max-width:820px}footer{border-top:1px solid var(--line);margin-top:48px;padding-top:18px}
@media(max-width:850px){.shell{display:block;padding:20px 18px 50px}nav{position:static;border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:28px}nav a{display:inline-block;margin-right:18px}h1{font-size:28px}}
@media print{nav,input{display:none}.shell{display:block;max-width:none;padding:0}body{background:white;color:black}details{break-inside:avoid}details>*{display:block}}
'''

NAV = [
    ('index', 'Status and scope'), ('runtime', 'Runtime architecture'),
    ('configuration', 'Configuration inventory'), ('build-release', 'Build and release'),
    ('tests', 'Tests and their limits'), ('evidence', 'Runs and media evidence'),
    ('artwork', 'Artwork and pack import'), ('robin-dev-center', 'Robin and Dev Center'),
    ('findings', 'Performance and defects'), ('handoff', 'Codex to Claude handoff')]


def inventories():
    paths = subprocess.check_output(['rg', '--files', 'windows-x64/psxrecomp/runtime',
        'windows-x64/psxrecomp/recompiler', 'windows-x64/tools'], cwd=ROOT, text=True).splitlines()
    refs = {}
    for name in paths:
        path = ROOT / name
        if path.suffix not in ('.c', '.cpp', '.h', '.hpp', '.py', '.cmd', '.ps1', '.js'):
            continue
        if not any(part in path.parts for part in ('src', 'include', 'tools')):
            continue
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        for i, line in enumerate(lines):
            for key in set(re.findall(r'\b(?:PSX_[A-Z0-9_]+|PSXRECOMP_[A-Z0-9_]+|EIN_[A-Z0-9_]+)\b', line)):
                if key == 'EIN_EXACT_REGIONS_V1':  # File-format signature, not a setting.
                    continue
                # Only quoted literal configuration names, not C identifiers.
                if not re.search(r'[\'\"]' + re.escape(key) + r'[\'\"]', line):
                    continue
                refs.setdefault(key, []).append(dict(path=path.relative_to(ROOT).as_posix(),
                    line=i+1, context='\n'.join(lines[max(0, i-1):i+3])[:1000]))
    tests = []
    for name in ('runtime', 'recompiler'):
        p = ROOT / f'windows-x64/psxrecomp/{name}/CMakeLists.txt'
        lines = p.read_text().splitlines()
        for i, line in enumerate(lines):
            match = re.search(r'add_test\s*\(\s*NAME\s+([^\s)]+)', '\n'.join(lines[i:i+3]))
            if 'add_test' in line and match:
                tests.append(dict(name=match[1], path=p.relative_to(ROOT).as_posix(), line=i+1))
    return dict(sorted(refs.items())), tests


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    env, tests = inventories()
    evidence = ROOT / 'docs/media/gallery/stage1-idle-diagnostic-results.json'
    latest = json.loads(evidence.read_bytes()) if evidence.exists() else None
    (OUT / 'source-inventory.json').write_text(json.dumps(dict(generated_at_utc=stamp,
        base_revision=revision, environment_literal_references=env, registered_ctest_names=tests,
        scope='Runtime/recompiler source and include directories, plus Windows tools. Quoted literal names only; defaults and dynamic names are not inferred.'), indent=2)+'\n')
    pages = {}
    pages['index'] = '''
<p class="lead">Stage 1 and the full seven-stage remaster remain incomplete. Audio starvation, ordinary boss progression, artwork integration and release acceptance are open.</p>
<p class="notice">This handbook distinguishes working-tree code, private test executables, frozen artwork, published evidence and the installed user build. A passing private test does not install a fix or complete a stage.</p>
<h2>What is established</h2>
<ul><li>The full assembled facade entry-to-exit footage and stills are published. Their disclosed timer assistance and capture load are part of the evidence.</li>
<li>A core completion-timestamp defect is fixed in source: deferred CPU charges are published before GTE and multiply/divide deadlines. Regression and randomized comparisons pass.</li>
<li>One isolated routine, <code>0x3A998</code>, passed 3,685 live native/interpreter comparisons in the v40 executable. Its qualification does not transfer to another executable hash.</li>
<li>Real-GL fixtures verify selected rendering boundaries. The wider v41 retained-bracket path recorded zero escaped gaps, but its live pair did not establish a whole-game speed benefit.</li>
<li>Robin has source and policy improvements and observed movement/fire in earlier runs. Greif defeat and ordinary Stage 1 completion remain unverified.</li></ul>
<h2>What must still finish</h2>
<ol><li>Smooth gameplay, boss approach/fire and native FMV, with actual audio evidence.</li>
<li>Safe native-code routing and qualification; review the separate SYS-primary implementation.</li>
<li>Integrate and accept delivered Stage 1 art, palettes, HUD/menu phases and remaining source gaps.</li>
<li>Validate Robin’s perception, targeting, movement, evasion, death/Continue and full boss progression.</li>
<li>Acquire, author, integrate and test later stages, branches, endings, credits and unlockables.</li>
<li>Produce one versioned runtime/pack, rollback procedure and normal-launcher acceptance.</li></ol>
<p>There is no verified completion percentage or reliable final delivery date. Source-key counts, delivered PNGs and occupied workstreams measure different things and must not be added into a completion score.</p>
<h2>Start here</h2>
<p>Use the <a href="handoff.html">handoff</a> to resume work, <a href="findings.html">findings</a> to avoid rejected hypotheses, and <a href="evidence.html">evidence protocol</a> before measuring a change.</p>
<p><a href="../MASTER-ACTION-PLAN.html">Coordinator’s master action plan</a> is maintained separately. Proposed features and promotion gates there are not proof of completed work.</p>
<h2>Actual facade footage</h2>
<video controls preload="none" poster="../media/gallery/stage1-assembled-facade-poster.png"><source src="../media/gallery/stage1-assembled-facade-fly-past.mp4" type="video/mp4"></video>
<p>See <a href="../H24-IN-GAME-RESULTS.md">facade results</a> for the run’s assistance, source mapping and limitations.</p>
'''
    if latest:
        pages['index'] += f'''<h2>Latest audio diagnostic</h2><p>{latest['guest_fps']:.4f} guest frames/s; {latest['starved_sample_frames_delta']:,} output-starved sample frames in the bounded gameplay window. Idle skip made no gameplay skips. Audio remains failing.</p>
<audio controls preload="none" src="../media/gallery/stage1-idle-process-output.wav"></audio>
<p>The ten-second process capture includes a documented 90 ms observer-inserted silence at 6.05 seconds. Four other short gaps match the bridge’s underrun fade pattern. Independent sample alignment verifies the callback/process correspondence outside the observer hole, with localized peak differences retained. <a href="../media/gallery/stage1-idle-diagnostic-results.json">Result and provenance</a>.</p>'''
    pages['runtime'] = f'''
<p class="lead">The Windows build combines generated static code, runtime overlay DLLs and an authoritative RAM interpreter. All three share the guest clock and device model.</p>
<h2>Boot and executable identity</h2><p>The retail entry file <code>SCUS_942.43</code> loads <code>cdrom:\\SYS.EXE;1</code>. Captured gameplay text matches SYS, not the original loader image. Current generated SCUS code must retain its SCUS byte guards. Changing the guard reference to SYS without regenerating the corresponding static code would admit incorrect code.</p>
<p>The separate SYS-primary proposal keeps disc/boot identity, cards and rewind identity stable, waits for a qualified entry plus a full SYS text hash before admitting static SYS code, preserves per-function byte checks and falls back on mismatches. It is under isolated implementation; it is not installed or accepted.</p>
<h2>Dispatch and byte admission</h2><p>{repo('windows-x64/psxrecomp/runtime/src/overlay_loader.c')} tracks loaded candidates, ranges, current CRC matches, native execution, comparison budgets and fail-closed state. {repo('windows-x64/psxrecomp/runtime/src/dirty_ram_interp.c')} interprets changed or unavailable RAM code and handles delay slots, nested calls and safe device-service boundaries.</p>
<p>Exact-entry diagnostic admission no longer lets a broader unverified owner mask a focused candidate. This selection change is restricted to differential mode; normal bundle preference and byte validation remain intact.</p>
<h2>Cycles and causality</h2><p>{repo('windows-x64/psxrecomp/runtime/src/psx_cycles.c')} owns published guest time, deferred charges and device deadlines. Completion timestamps must include pending charges. The accepted fix publishes time at the boundary; an unconditional “effective time” shortcut was rejected because it can defer device effects across an instruction boundary. Keep the device-deadline regression intact.</p>
<h2>Rendering</h2><p>Guest GP0 commands enter GPU processing, then native/HD rendering. HD admission uses captured source words and palette identity; replacement RGB and categorical alpha/STP remain separate. The opt-in opaque batch combines compatible HD submissions. Filter caching avoids repeated nearest/linear state calls. Bracket retention avoids redundant FBO transitions only inside a guarded native/HD or HD/HD handler gap.</p>
<p>The v41 retained-gap marker is not an “active batch” flag. A kept gap must be consumed before the handler returns. Wide mode, native-edge paths and incompatible native queues exclude retention. <code>hr_kept_leaks</code> must stay zero.</p>
<h2>Audio</h2><p>The guest SPU produces nominal 44.1 kHz audio; the host callback consumes device-rate PCM. {repo('windows-x64/psxrecomp/runtime/src/recomp_audio_drc.h')} supplies a persistent band-limited fractional resampler and bounded fill controller: target/prefill 180 ms, ring 280 ms, 32 taps, 75 ms low-pass, correction cap 1%, slew 0.75 percentage points/s. These are source defaults, not a guarantee against long producer stalls.</p>
<p>Starved sample frames are not a count of audible gaps. A callback PCM dump proves what the bridge emitted; process loopback observes Windows process output; neither proves physical-DAC continuity. Do not hide starvation by replacing music or retiming evidence.</p>
<h2>Presentation and profiling</h2><p>The frontend selects vsync ownership or wall pacing. It does not deliberately apply both by default. During measured slow periods the pacer slept almost zero. Native phase samples at <code>0x1303C</code> include frame-end host work inside the game’s VSync wait, including present, debug polling, rewind and audio pumping. They are not pure native function cost.</p>
'''
    defaults = [
        ('PSXRECOMP_HD_OPAQUE_BATCH','0','Compatible opaque HD batching; normal launcher does not enable it.'),
        ('PSXRECOMP_HD_KEEP_BRACKET','0','Guarded framebuffer bracket retention; v41 private path only until promoted.'),
        ('PSXRECOMP_HD_FILTER_STATE_CACHE','0','Owned texture sampler-state cache; opt-in.'),
        ('PSXRECOMP_HD_CPU_PROFILE','0','HD wall-cost counters; instrumentation adds overhead.'),
        ('PSXRECOMP_HD_WORLD_SAMPLING','0','Source-specific RGB sampling experiment; categorical alpha remains unchanged.'),
        ('PSXRECOMP_HD_PAGE_FALLBACK','1 in Play-HD.cmd','Whole-page fallback enabled by the HD launcher.'),
        ('PSXRECOMP_HD_CPU_AUTHORITY','0 in Play-HD.cmd','Normal GPU authority; dual-raster/netplay changes readback semantics.'),
        ('PSXRECOMP_HD_DECODE_BUDGET_MB','256 in Play-HD.cmd','Launcher override, not a universal framework default.'),
        ('PSX_IDLE_SKIP','off for current Einhander config','Existing guarded loop enhancement. Rejects stores/MMIO and respects device deadlines.'),
        ('PSX_REWIND','configuration/environment dependent','Explicit 0 disables. Diagnostics must record effective state and cadence.'),
        ('PSX_REWIND_INTERVAL','15 source default','Requested frames between successful safe captures; not actual captures/s.'),
        ('PSX_REWIND_FMV_INTERVAL','4 source default','MDEC-based local classifier is integrated; legacy XA/depth24 rule is comparison-only.'),
        ('PSX_REWIND_FMV_LEGACY','0','Explicit private comparison toggle for the old XA/depth24 rule.'),
        ('PSX_REWIND_DEPTH','50 source default','Ring depth; current local options include 50/100/150/200.'),
        ('PSX_OVERLAY_DIFF','off','Diagnostic native/interpreter comparisons; not normal pacing acceptance.'),
        ('PSX_OVERLAY_AUTOCOMPILE_OFF','1 in private probes','Private runs capture first and compile after owned game closes.'),
        ('EIN_DEBUG_PORT','4370 in bridge','Private harnesses use isolated ports; latest route uses 4376.')]
    rows = ''.join('<tr><td><code>'+escape(k)+'</code></td><td>'+escape(v)+'</td><td>'+escape(d)+'</td></tr>' for k,v,d in defaults)
    refs_html = []
    for key, refs in env.items():
        content = ''.join(f'<p>{repo(r["path"])}:{r["line"]}</p>{command(r["context"])}' for r in refs)
        refs_html.append(f'<details data-search="{escape(key.lower())}"><summary>{escape(key)} <small>({len(refs)} references)</small></summary>{content}</details>')
    pages['configuration'] = f'''
<p class="lead">Record effective configuration from each prepared candidate and launch receipt. A launcher override, framework fallback and user preference are different sources of defaults.</p>
<p>The table below contains reviewed defaults relevant to current experiments. The searchable inventory contains {len(env)} quoted literal configuration names from runtime/recompiler source/include files and Windows tools. It includes probes and diagnostics. Dynamic names, generated code and external package settings are outside this inventory; unresolved defaults remain source expressions, not guessed values.</p>
<div class="scroll"><table><thead><tr><th>Setting</th><th>Reviewed default / override</th><th>Purpose</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Normal launcher</h2><p>{repo('windows-x64/Play-HD.cmd')} sets texture root, page fallback, decode budget and GPU authority. It clears dump/proof controls. It does not set opaque batching, keep-bracket, filter caching or idle skip. These remain experiments rather than installed defaults.</p>
<h2>Literal source inventory</h2><p><a href="source-inventory.json">Machine-readable references and registered tests</a>. Excerpts retain the source’s condition and neighboring expressions; they are not resolved semantic documentation for every flag.</p>
<label for="search">Find a configuration name</label><input id="search" type="search" placeholder="For example: REWIND, OVERLAY, HD_" autocomplete="off">
<div id="inventory">{''.join(refs_html)}</div>
<script>document.getElementById('search').addEventListener('input',function(){{let q=this.value.toLowerCase();for(let d of document.querySelectorAll('[data-search]'))d.hidden=!d.dataset.search.includes(q)}});</script>
'''
    pages['build-release'] = f'''
<p class="lead">The full game build needs the user’s own disc dump, BIOS and local configuration. A fresh-checkout end-to-end build has not yet been verified.</p>
<h2>Prerequisites and generation</h2><p>Read {repo('windows-x64/psxrecomp/docs/BUILDING.md')}, {repo('windows-x64/psxrecomp/docs/GAME_PROJECT_SETUP.md')} and {repo('windows-x64/psxrecomp/docs/LOCAL_CODEGEN_SDK.md')}. Framework and UI trees are inline copies; a recursive clone does not reconstruct their historical pins. Preserve licenses.</p>
{command('python windows-x64/psxrecomp/psxrecomp_cli.py --help\npython windows-x64/psxrecomp/psxrecomp_cli.py generate --help')}
<p>From <code>windows-x64</code>, after supplying local <code>game.toml</code>, disc and toolchain:</p>
{command('python psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . --disc "disc/Einhander (USA).cue"\ncmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release\ncmake --build build-release --target psx-runtime')}
<p>The game CMake file references a local <code>assets/psxrecomp.ico</code>. Supply it or make an intentional local configuration change. Generated game/BIOS C and machine configuration are excluded from public history. The commands above describe the configured workflow; they are not a report that clean-checkout generation passed.</p>
<h2>Private experiment build</h2><p>{repo('remaster-audit/build_stage1_sampling_probe.py')} rebuilds selected real runtime units and links pinned local objects. It validates the pinned inputs and writes an immutable <code>build.json</code>. Compilation is CPU-only; <code>--test</code> includes hidden real-GL checks and needs the shared GPU slot.</p>
{command('python remaster-audit/build_stage1_sampling_probe.py --output remaster-audit/dev-center-evidence/stage1-completion-20261112/FRESH-BUILD-NAME\npython remaster-audit/build_stage1_sampling_probe.py --output remaster-audit/dev-center-evidence/stage1-completion-20261112/FRESH-BUILD-NAME --test')}
<p>Replace <code>FRESH-BUILD-NAME</code> once. Never rebuild over an accepted immutable directory or edit a frozen parent through hardlinks. A pinned-object build is a local experiment, not a portable release procedure.</p>
<h2>Promotion procedure still to execute</h2><ol><li>Finish source review and relevant regressions; archive executable and source hashes.</li><li>Freeze one final artwork candidate with all pending imports resolved.</li><li>Qualify ordinary movement/fire/bosses, native menus/FMVs and audio in the actual normal configuration.</li><li>Prepare a versioned release directory and hash manifest. Preserve the previous installed executable, pack and writable user data.</li><li>Install only the reviewed version; retain a concrete rollback path.</li><li>Exercise normal launcher and Robin button from cold boot, then repeat the ordinary acceptance routes.</li><li>Publish measured results and scoped code commits. A successful push is delivery of those commits, not acceptance of an untested installed build.</li></ol>
<p>No v41 production runtime or new frozen pack has been installed by this work.</p>
'''
    test_rows = ''.join(f'<tr><td><code>{escape(t["name"])}</code></td><td>{repo(t["path"])}:{t["line"]}</td></tr>' for t in tests)
    pages['tests'] = f'''
<p class="lead">Run tests appropriate to the changed boundary. Keep fixture correctness, actual-game correctness and performance acceptance separate.</p>
<h2>Focused runtime checks</h2><p>Registered targets include <code>psx_timestamp_batch_test</code> and <code>psx_cycle_event_boundaries_test</code>. The timestamp test has 12 checks and 3,250 randomized published-versus-batched comparisons. The deadline test preserves instruction-level device causality. Run against a configured runtime-test build:</p>
{command('ctest --test-dir YOUR-CONFIGURED-TEST-BUILD -N\nctest --test-dir YOUR-CONFIGURED-TEST-BUILD -R "psx_timestamp_batch_test|psx_cycle_event_boundaries_test" --output-on-failure')}
<p><code>YOUR-CONFIGURED-TEST-BUILD</code> is a placeholder. Build/test options and available targets depend on the configured CMake tree; inspect <code>ctest -N</code> before claiming coverage.</p>
<h2>Exact-entry loader admission</h2><p>{repo('windows-x64/psxrecomp/runtime/tests/test_overlay_exact_unmask_runtime.py')} links the real loader with controlled fixtures. Before/after and four mutants establish diagnostic admission and routing; the interpreter is stubbed, so this is not real generated-code qualification.</p>
{command('python windows-x64/psxrecomp/runtime/tests/test_overlay_exact_unmask_runtime.py --mode tree')}
<p>Compare/mutant mode needs the retained before/fix review diff. The adopted CTest entry uses tree mode. A supplied build directory must be fresh; the runner’s own temporary directory cleanup is bounded.</p>
<h2>Real-GL fixture</h2><p>{repo('remaster-audit/test_stage1_sampling_gl.c')} includes {repo('remaster-audit/test_hd_opaque_batch_gl.h')} and emissive checks. The private v41 build passed 1,381 checks in world-off, filter-cache and keep-bracket modes and 1,383 in world-on mode. Those v41 binaries covered 15 boundary scenes. Fresh v42 and v43 builds cover 22 scenes plus actual source-alias readback and shutdown. All four GL modes pass: 1,525 checks for world-off/filter/keep, and 1,527 for world-on, with zero failures.</p>
<p>The source-alias case uses a real in-handler readback with queued HD geometry; shutdown compares CPU VRAM to an explicit-flush reference without GL calls after context deletion. These boundaries now have fresh compiled proof. No target called <code>fm_hd_opaque_batch_regression</code> is asserted here; use the actual private fixture runner.</p>
<h2>CPS differential comparison</h2><p>The isolated review harness compiles retained real generated shards and links the real loader, interpreter, clock, memory and I-cache model. It reproduces the old non-leaf/continuation failures and catches four altered shards. The full root rerun returned <code>RESULT: AS REQUIRED</code>. GTE arithmetic and devices are deterministic stubs; pending interrupts are not a full live machine.</p>
<p>The current phase-2 proposal rewrites physical entry aliases to KSEG0 inside the authoritative pass. That is a blocking review concern. A separate virtual-PC emitter correction and real escape cleanup tests are in progress. Do not integrate the earlier proposal as-is.</p>
<h2>Policy and media checks</h2>
{command('python -m unittest discover -s windows-x64/tools -p "test_robin_combat_policy.py"\npython remaster-audit/audio-evidence/process-loopback/test_synthetic.py\nremaster-audit/audio-evidence/process-loopback/build/process_loopback_capture.exe --self-test')}
<p>Combat policy and native threat collector passed 43 and 24 checks in their recorded runs. Process-helper self-test passed 115 checks; the evolving analyzer’s synthetic suite has separate receipts. Synthetic media tests cannot accept game audio.</p>
<h2>Registered CMake names</h2><p>Extracted literal names/templates from runtime and recompiler CMake files. Conditional/dynamic entries still require a configured <code>ctest -N</code>.</p>
<div class="scroll"><table><thead><tr><th>Name or template</th><th>Registration</th></tr></thead><tbody>{test_rows}</tbody></table></div>
'''
    pages['evidence'] = f'''
<p class="lead">Every result must be tied to its executable, candidate, settings, observer load, input route and cleanup proof.</p>
<h2>Private evidence root</h2><p><code>E = C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112</code>. This tree holds local disc-derived data and is ignored. Publish selected summaries and approved media under <code>docs/media/gallery</code>; never push raw RAM, VRAM words, palettes, disc/BIOS data, generated game code, cached DLLs or private saves.</p>
<h2>Quiet-window protocol</h2><ol><li>Prepare a fresh candidate first; verify immutable parent and runtime hashes.</li><li>Set CPU-QUIET and GPU-RESERVED, wait for no GPU holder and an empty ComfyUI queue, and obtain a fresh manual quiet ACK from Claude.</li><li>Verify the prior owned game exited and its isolated debug port closed. Use a retained Popen identity and exact path, not a name-wide process kill.</li><li>Launch the private game. Select its unique current window and foreground it during boot. Check fresh screenshots and related windows; an occluded dialog is not absent.</li><li>After timing starts, avoid UI switching, builds, exports, hashing or directory scans. Record only the declared bounded observers.</li><li>Capture after timing when possible. Stop the bounded aid and recorder, release input, close the owned game, retain exit/port/error proof.</li><li>Release CPU/GPU markers promptly and tell Claude. Do not silently restart the rejected process-suspending central gate.</li></ol>
{command('python remaster-audit/comfy-authoring/gpu_queue.py cpu-quiet "reason"\npython remaster-audit/comfy-authoring/gpu_queue.py reserve-and-wait "reason"\n# Obtain fresh manual quiet ACK, run one owned measurement, verify owned close.\npython remaster-audit/comfy-authoring/gpu_queue.py cpu-release\npython remaster-audit/comfy-authoring/gpu_queue.py release-reservation')}
<h2>World-route preparation and launch</h2><p>{repo('remaster-audit/run_stage1_world_flypast.py')} prepares a hash-pinned private candidate, uses native title/fighter/weapon/City gates, disables turbo, and discloses its timer-only aid. A no-fire assisted fly-past cannot establish ordinary combat or stage completion.</p>
{command('python remaster-audit/run_stage1_world_flypast.py --batch FRESH-RUN --candidate E/frozen-w3-lit-v1/candidate.json --runtime E/sampling-build-v41-wide-bracket/build.json --supersampling 2 --rewind 1 --native-menus --telemetry-only --capture-seconds 120 --cpu-profile 1 --runtime-perf 1 --retain-host-audio --prepare-only\npython remaster-audit/run_stage1_world_flypast.py --batch FRESH-RUN --rewind 1 --run-prepared')}
<p>In commands, replace <code>E/</code> with the full evidence root or its repository-relative equivalent. The example does not turn on batching or other experiments; choose each flag explicitly and record it. <code>--gpu-clock-profile</code>, <code>--phase-profile</code>, media/PC/dirty profiling and recordings are optional observers and change the measurement’s load.</p>
<h2>Receipts and decisions</h2><p>Retain <code>candidate.json</code>, <code>launch-candidate.json</code>, copied executed scripts, command receipts, one-Hz observations, stdout/stderr and <code>world-flypast-proof.json</code>. Record CPU/GPU quiet acknowledgement and foreground observation separately. A foreground observation is not continuous focus logging.</p>
<p>Compare explicit settings, especially opaque batching, render preference, rewind cadence, staged native cache and emissive/world sampling. Different initial audio fill and guest-frame progress mean an ordered pair is not an identical replay. A higher average alone does not prove a causal win.</p>
<h2>Actual audio</h2><p>Host tap 2 is callback PCM. Absolute sample-frame indexes anchor exact WAV excerpts copied after measurement. The strict process-loopback helper accepts an explicit owned PID and expected image, includes only that tree, and allows at most one verified direct Windows system console-host child with stable PID/creation time/path. It rejects other descendants. It does not capture microphone or system-wide audio.</p>
{command('python remaster-audit/audio-evidence/process-loopback/analyze_capture.py PATH/TO/process-output-after-measurement.wav --json-out PATH/TO/analysis.json')}
<p>Read WAV and timing sidecar together: observer gap fills, discontinuities and timestamp errors are separate from PCM silence candidates. The process device’s repeated device position is not a hardware-style clock; use validated QPC packet positions. Bracketing callback counters include helper setup/teardown, and weak envelope correlation cannot establish exact waveform alignment.</p>
'''
    pages['artwork'] = f'''
<p class="lead">Use native source identity and draw evidence to bind artwork. A visually plausible PNG or a matching filename alone does not establish a correct replacement.</p>
<h2>Pack and source format</h2><p>The canonical replacement directory is <code>einhander-texture-replacements</code>. Keys are uppercase <code>WORDS_CRC-CLUT_CRC</code> pairs, formatted <code>XXXXXXXX-XXXXXXXX.png</code>. Source pixels are 16-bit little-endian VRAM words; paletted modes also require the exact CLUT. Depth 0/1/2 denotes 4/8/16 bpp. Native width is source-word width × 4/2/1 respectively.</p>
<p>CRC identifies the native word/palette pair; SHA-256 pins complete file bytes and manifests. Full-upload registration and ExactRegions additionally preserve source geometry, page location, CLUT location and used UV rectangles. Check used draw context: a page may contain unrelated signs, HUD elements or actor parts.</p>
<h2>Alpha and compositing</h2><p>Replacement alpha is categorical: <code>0, 127, 255</code>, preserving transparent, semi-transparent/STP and opaque classes. Class-exact acceptance compares the native category at every native texel center. Arbitrary antialias alpha, an attractive screenshot or a matching image size is insufficient.</p>
<p>Partial-page revisions must retain parent pixels outside their owned region. W4 import planning found shared-page overwrites and replaced them with composites. A candidate can use hardlinks to immutable parent files, but every changed file must be replaced atomically; never write through a parent hardlink. Verify every parent hash after composition.</p>
<h2>Composer</h2><p>{repo('remaster-audit/build_stage1_frozen_candidate.py')} accepts a pinned parent, pinned manifests and image entries. An entry may carry <code>native_source</code> for a complete upload or <code>exact</code> source words, CLUT, shape, page coordinates, UV rectangle, depth and CLUT coordinates. Optional alpha/emissive/source handoffs are separately pinned. A fresh direct-child output directory is mandatory.</p>
{command('python remaster-audit/build_stage1_frozen_candidate.py --plan PATH/TO/reviewed-plan.json --output remaster-audit/dev-center-evidence/stage1-completion-20261112/FRESH-PACK')}
<h2>Current candidates and deliveries</h2><ul><li><code>E/frozen-w3-lit-v1/candidate.json</code>: frozen gameplay parent; 1,669 color PNGs, 837 authored entries and 226 exact regions in the recorded census. Two masks. The separate atlas-lit candidate has four masks. Do not conflate them.</li>
<li>W4 import plan v3 reports 635 rows / 634 unique keys, with carried, superseded and dropped entries distinguished. Coordinator reports 1,769 class-exact exports. These are delivered-plan checks, not root live acceptance.</li>
<li>Greif v4 exports include 1024/2048 options. Root’s current candidate choice is 1024 pending motion evidence. Astraea v2.1 remains an optional comparison set.</li>
<li>W3 HUD class repairs and W5/W6 lettering/fades are delivered. Five duplicate HUD choices and reconstructed fade CLUTs require explicit import decisions and source checks.</li>
<li>Historical fade-gap census changed from 157 to 133 keys / 58 CLUTs after a 24-key delivery. Counts are scoped census gaps, not all remaining textures.</li></ul>
<h2>In-game acceptance</h2><ol><li>Verify native words, CLUT, decode, UV and class categories.</li><li>Compose into a new candidate and verify lineage/unchanged keys.</li><li>Observe the actual mapped replacement draw before using footage as evidence.</li><li>Review entry, front, angled and exit motion at normal game speed, with obstruction/load disclosed.</li><li>Check palette phases, actor states, masks, seams and shared pages.</li><li>Measure ordinary gameplay/audio separately from recorder-heavy visual footage.</li><li>Install only after the final candidate and runtime pass release gates.</li></ol>
<p>Drache census: 218 keys, source pixels for 141 in that snapshot. The 128 post-Drache keys include Stage 2 material; nine had native sources in the earlier census. Do not call them all unfinished Stage 1 art or say no Stage 2 source exists.</p>
'''
    pages['robin-dev-center'] = f'''
<p class="lead">Robin is a pad-input controller hosted by the local Python bridge. Its button being present does not prove its policy can perceive, aim at or avoid every enemy.</p>
<h2>Service boundaries</h2><p>{repo('windows-x64/tools/ein_bridge.py')} serves the local development UI, proxies one JSON-line command at a time to the game’s TCP debug server, and hosts Robin in a background thread. Bridge HTTP default is 8090; game TCP default is 4370, overrideable by <code>EIN_DEBUG_PORT</code>. {repo('windows-x64/tools/dev_center.js')} is browser UI code, not the HTTP server.</p>
<p>Endpoints include <code>GET /health</code>, <code>GET /bot/status</code>, <code>POST /bot</code> with start/stop/config, and attract/demo controls. Development tools can deliberately write catalogued values; the ordinary acceptance harness places a separate command boundary in front of that capability.</p>
<h2>Perception and policy</h2><p>Read-only native hull/draw tracking feeds stage and combat policies. Movement options include simple lanes/weaves and calibrated draw/combat lanes. Hull coordinates are craft- and viewport-specific; the Mk.II controller cannot simply be reused for Mk.III or Astraea. Earlier RAM-position guesses failed live qualification and must not be reintroduced as facts.</p>
<p>{repo('windows-x64/tools/robin_combat_policy.py')} prioritizes fresh textured targets and weak-point candidates. {repo('windows-x64/psxrecomp/runtime/src/threat_draw_tracker.h')} collects supported draw families; the latest source separates Greif arm/mount geometry from the generic boss body. Body parts are not automatically contact hazards, and disappearance is not proof of zero HP. Projectile evasion remains independent.</p>
<p>Untextured beams/bullets and missing Drache families remain perception gaps. “Visually aware” currently means bounded verified draw evidence, not universal image understanding. The proposed RAM-aware Robin v2 and dodge planner are design work, not a shipped controller.</p>
<h2>Ordinary acceptance</h2><p>{repo('remaster-audit/run_robin_stage1_acceptance.py')} uses verified native menu gates, private writable data, bounded pad decisions, no turbo, no invulnerability hold, no guest RAM writes and no state loads. It records observations and needs independent stage-clear review. <code>--seconds</code> bounds a run; a local STOP file ends it.</p>
{command('python remaster-audit/run_robin_stage1_acceptance.py --help')}
<p>Explicitly use <code>--supersampling 2</code> for the normal-resolution gate; the tool’s historical default is 9. The normal Robin UI route does not automatically adopt private harness flags or experimental rendering defaults. Validate the actual launcher button after promotion.</p>
<h2>Remaining E2E routes</h2><p>Require actual movement, firing that hits targets, evasion, weapon/pod behavior, Greif defeat, post-boss/Drache progression, death, Continue, Game Over, results, restart and user-data flows. A timer-assisted source run can acquire material, but it cannot satisfy these ordinary acceptance gates.</p>
<h2>Computer-use recovery</h2><p>Inspect current windows and fresh screenshots. An editor or secondary dialog may be behind another window or minimized. Bring the intended app forward before deciding a control is missing. Accessibility text can be stale; never reuse old element indexes or coordinates after a state change. Leave user drafts untouched.</p>
'''
    pages['findings'] = '''
<p class="lead">Audio remains failing. Several changes have fixture or local correctness proof; none establishes complete smooth HD gameplay.</p>
<h2>Measured runs</h2><p>All rows below are bounded assisted no-fire routes unless marked otherwise. Averages hide shorter stalls. Output-starved sample frames are not audible-gap counts. Different initial buffers and route progress prevent causal ranking from these ordered runs.</p>
<div class="scroll"><table><thead><tr><th>Run</th><th>Guest fps</th><th>Starved sample frames</th><th>Scope / qualification</th></tr></thead><tbody>
<tr><td>v37 normal2, rewind15/FMV4</td><td>59.7900</td><td>10,640</td><td>Batching ON; not default unbatched control</td></tr>
<tr><td>v37 normal2, FMV15</td><td>59.9177</td><td>2,892</td><td>Batching ON; different initial fill</td></tr>
<tr><td>v37 normal2, rewind OFF</td><td>58.4351</td><td>121,451</td><td>Batching ON; rewind-off did not solve</td></tr>
<tr><td>v40 code OFF r1</td><td>38.2264</td><td>2,051,486</td><td>Batching OFF; cross-series configuration mismatch</td></tr>
<tr><td>v40 qualified cache staged r1</td><td>51.1439</td><td>809,019</td><td>Batching OFF; actual staged-routine use not queried</td></tr>
<tr><td>v37 current-host control</td><td>47.6677</td><td>1,159,599</td><td>Batching OFF; GPU clocks varied without causal proof</td></tr>
<tr><td>v40 native textures r2</td><td>60.0083</td><td>0</td><td>Timing passed; old audio helper refused child after timing</td></tr>
<tr><td>v40 matched batching OFF r2</td><td>49.4346</td><td>960,215</td><td>Same binary; foreground observed at boot</td></tr>
<tr><td>v40 matched batching ON r2</td><td>55.8619</td><td>351,434</td><td>2,083,186 primitives batched; still failing</td></tr>
<tr><td>v41 retention OFF r1</td><td>50.2861</td><td>894,319</td><td>Opaque/filter ON; NVML log exists</td></tr>
<tr><td>v41 retention ON r1</td><td>46.9680</td><td>1,207,145</td><td>Zero gap leaks; ON NVML log was not started</td></tr>
<tr><td>v41 idle ON r1</td><td>57.3576</td><td>217,156</td><td>No gameplay skips; all three render options ON; added observers</td></tr>
</tbody></table></div>
<p><a href="../STAGE1-AUDIO-RESULTS.md">Detailed audio history</a> and the linked result JSONs retain configuration and provenance. The v40 combined run and keep-bracket-only run are excluded from performance acceptance because of overlapping agent I/O or UI activity.</p>
<h2>Corrections and rejected explanations</h2><ul>
<li><strong>Cross-series batching confound.</strong> Earlier normal2 controls enabled opaque batching; later v40 controls disabled it. This was initially missed and corrected publicly. Do not blame the entire difference on the clock fix, host load or GPU power state.</li>
<li><strong>Dispatch-entry totals are not function cost.</strong> <code>0x26714</code> is a short epilogue; its attributed instructions include chained execution. Earlier 23–29% and large timing-gain estimates were withdrawn.</li>
<li><strong>Actual PC samples.</strong> A 95-second histogram had 389,193 samples, zero drops. A later 120-second histogram filled the 8,192-bucket table and dropped about 1.1%; current capacity is 32,768. The face loop near 3A998 and unlit loop near 3A6FC are real interpreted hot regions. Instruction frequencies are not CPU-time shares.</li>
<li><strong>Native 0x1303C attribution.</strong> The VSync loop contains frame-end host work. The slow ten-second sampler had roughly 39% interpreter, 34% GPU context, 26% native context. Those are observations of tagged contexts, not exact per-function cost.</li>
<li><strong>Idle skip.</strong> Current game VSync wait stores a timeout counter, making it ineligible for the existing no-store rule. Enabling the guarded feature produced two boot skips and zero additional gameplay skips. No safety-rule widening or blind MMIO polling skip was applied.</li>
<li><strong>GPU clocks.</strong> Read-only clocks varied. A P5 snapshot taken after a game exited is not evidence of in-game P5. No driver power/clock setting has been changed by this work.</li>
<li><strong>Audio correction cap.</strong> A synthetic steady-rate case improved at 1%; real same-source gameplay did not resolve, and either cap still starved under an injected 300 ms stall. Increasing correction is not a substitute for fixing producer stalls.</li>
<li><strong>Rewind.</strong> XA music incorrectly selects movie cadence, but almost no safe snapshot completed during the measured gameplay windows. The classifier bug is real; it does not establish that frequent successful rewind snapshots caused those stalls. The narrower classifier and actual capture counters are integrated in source commit 7be82c4. Live v43 gameplay recorded zero movie-classified frames over 6,686 frames, 2,732 attempts, one stored snapshot (2.716 ms serialization), and 2,731 unsafe-context refusals. Audio still starved.</li>
<li><strong>Process audio.</strong> Earlier eight silence candidates matched bridge fade fingerprints by inference; their callback dump ended before capture. The latest overlap has a documented 90 ms observer hole and four separate bridge-signature dropouts. Independent sample alignment confirms the supplied 4,256-frame callback offset across 18 interior windows; 14 match within one PCM unit throughout. The observer hole has callback audio present. Localized peak differences remain; whole-device continuity is not established.</li>
</ul>
<h2>Open defects and next proof</h2><ol><li>Producer starvation before/at boss and during firing: qualify alias-correct native hot code and isolate render work, then repeat ordinary combat and FMV with declared observers.</li><li>CPS validator: one-unit boundaries reproduce/fix continuation artifacts, but canonicalizing the authoritative entry alias is not acceptable. Preserve virtual PC in routing and test escape cleanup before integration.</li><li>SYS-primary: verify boot hash latch, title/RAM/framebuffer parity, mismatch fallback, code flips, restore/reset and identity. Never retarget SCUS text guards prematurely.</li><li>Robin: fill perception gaps and demonstrate actual boss clears with ordinary pad input.</li><li>Art/menus/later stages: integrate validated sources, resolve palette uncertainties, then verify every actual state and motion route.</li></ol>
'''
    pages['findings'] += '<h2>Rewind v43 live verification</h2><p>The 120-second run averaged 55.7528 fps with 367,648 starved sample frames. It verifies zero gameplay movie frames and actual stored-snapshot accounting, not a speed improvement. <a href="../media/gallery/stage1-rewind-classifier-results.json">Exact report</a>.</p>'
    pages['handoff'] = f'''
<p class="lead">Resume from the actual receipts. Whole-project completion, smooth audio and production installation are false.</p>
<h2>Revision and working state</h2><p>Documentation base revision: <code>{revision}</code>. That is the HEAD at generation, not the eventual commit containing this page. Use <code>git status --short</code> and <code>git log -5 --oneline</code> before editing. Preserve unrelated work; do not reset/stash the shared tree.</p>
<p>Commit <code>a426c9c</code> carries guarded HD→HD bracket retention/counters, expanded real-GL boundaries and bounded GPU/phase/idle plus overlapping audio observers. Commit <code>7be82c4</code> carries the narrower rewind classifier, actual capture counters, the 52-check real-unit CTest regression and updated private build/harness. Fresh v42/v43 GL receipts pass all four modes. New observer-only Devin onboarding and documentation/media are separate scoped changes; consult current Git status. An unrelated <code>tools/coordination/hermes-clear-events.mjs</code> belongs to Claude and must not be swept into a runtime commit.</p>
<h2>Local executable and artwork</h2><ul><li><code>E/sampling-build-v43-rewind/build.json</code>, executable SHA-256 <code>5f8ab5548614682eb1158c591e3838085f4f0b99d617af01a62eab4e6aa3ea4f</code>. Earlier retained-boundary-only v42: <code>a55ab7a7c588ce96371c4abede5f6022ef2e088157929c0395ede2a68219bee3</code>.</li>
<li><code>E/frozen-w3-lit-v1/candidate.json</code> is the frozen two-mask gameplay parent. Do not modify it.</li>
<li><code>E/published-ts-focus3A998-v1/hd-on_rewind-off</code> holds v40 qualification. Requalify on a new executable hash.</li>
<li><code>E/v41-idle-on-r1/hd-on_rewind-on</code> holds the latest cleanly closed diagnostic, process/callback audio, timing sidecar, analysis and automated NVML log.</li></ul>
<p><code>E</code> expands to <code>C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112</code>. Private paths are for the local handoff; they are not portable prerequisites or public downloads.</p>
<h2>Coordination state</h2><p>Hermes owner <code>codex-einhander</code>, peer <code>claude-einhander</code>, task <code>EIN-STAGE1-COMPLETION-20261112</code>. Latest game PID 22136 exited 0, errors[] and debug port closed. CPU-QUIET and GPU-RESERVED were released after the run. Refresh those facts before any next measurement.</p>
<p>The process-suspending central gate remains OFF after the earlier permission rejection. Manual quiet ACKs and resource markers are the current protocol. An inbox watcher proves watcher connectivity, not model activity. Keep useful bounded tasks active and check actual delivered receipts. No weekly usage percentage is available to root; do not invent a remaining budget.</p>
<h2>External work in flight</h2><ul><li>Alias-correct CPS revision and real nonlocal escape cleanup in <code>runtime-review/cps-unit-validation/v2-virtual-pc</code>; prior phase snapshots preserved.</li><li>Isolated SYS-primary implementation and bootstrap/fallback/identity checks.</li><li>Remaining two real-GL boundary scenes in an isolated copy: source alias readback and shutdown/re-init.</li><li>W4 import plan v3, Stage 1 art/source gaps, Drache work and static later-stage extraction.</li><li>Audio analyzer alignment of the latest callback/process overlap; opt-in HD audio design is separate from fixing stutter.</li><li>Robin v2 perception/planner design and coordinator master plan; not integrated.</li></ul>
<h2>Next ten actions, in dependency order</h2><ol>
<li>Measure untimed invalidation/upload bookkeeping and review the isolated exact-region index candidate; preserve wrap, CLUT, generation and restore behavior, then run the expanded actual fixture.</li>
<li>Compare the next measured renderer control and candidate with identical flags and observers; preserve audio evidence and avoid promotion from an average alone.</li>
<li>Finish the virtual-PC CPS review, preserving unsupported alias fallback and all trace/timing/memory checks; independently rerun the revised real-code and escape cases.</li>
<li>Integrate only the reviewed CPS revision and expectation changes; rebuild privately and requalify targeted hot routines on that exact executable.</li>
<li>Verify the integrated rewind classifier during native FMV and actual restore/load scenarios; keep snapshot safety gates and distinguish target cadence from stored captures.</li>
<li>Review SYS-primary without changing the SCUS guard/code pairing; exercise boot latch, code-flip fallback, restore/reset, cards and identity.</li>
<li>Run controlled ordinary combat/boss-fire and FMV checks, preserving actual output audio. Repeat only where variance or unresolved concerns justify it.</li>
<li>Compose W4 v3 into a fresh candidate, resolve HUD/CLUT duplicates, verify parent preservation/class exactness and inspect live motion.</li>
<li>Execute bounded, labelled capture-only progression to acquire remaining native sources, then ordinary Robin stage-clear routes separately.</li>
<li>Freeze and install one versioned accepted runtime/pack, verify rollback and normal launcher/Robin; continue Stage 2–7 coverage until all end states pass.</li></ol>
<h2>Stop conditions and recovery</h2><p>Stop an owned run when its local STOP marker, identity check, input boundary or resource lease fails. Preserve failed evidence and close only the owned process. Do not kill processes by broad name. Do not extend invulnerability, import unknown native code or relax byte/causality checks to manufacture success. If a UI appears blocked, inspect related/minimized windows and fresh screenshots before repeating input.</p>
<p>Durable machine state: {repo('remaster-audit/stage1-completion-20261112/execution-state.json')}. Coordinator continuation: {repo('coordination/CLAUDE-HANDOFF.md')}. These local/coordination notes may evolve independently; reconcile against actual receipts.</p>
'''
    pages['handoff'] += '<h2>Devin onboarding</h2><p>The user explicitly put Devin on hold until the user is home later today. Do not prompt or activate Devin meanwhile; Codex and Claude continue. The dedicated observer connector passed five policy checks and a real protocol smoke test, and the current native client loaded its worker. Actual model inbox acknowledgement remains unverified. On reactivation, synchronize against the then-current revision before any work; no shared edit authority is inferred from configuration. <a href="../../coordination/DEVIN-HANDOFF.md">Onboarding handoff</a>.</p>'
    for slug, title in NAV:
        nav = ''.join(f'<a href="{s}.html"'+(' aria-current="page"' if s==slug else '')+f'>{escape(t)}</a>' for s,t in NAV)
        html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · Einhänder HD</title><link rel="stylesheet" href="handbook.css"></head><body><div class="shell"><nav aria-label="Project handbook"><strong>Einhänder HD</strong>{nav}<a href="../GALLERY.md">Published gallery</a></nav><main><div class="eyebrow">ENGINEERING HANDBOOK · 13 NOVEMBER 2026</div><h1>{escape(title)}</h1>{pages[slug]}<footer>Generated {escape(stamp)} · source base {revision[:12]} · Status is bounded by the cited tests and evidence. <a href="source-inventory.json">Source inventory</a>.</footer></main></div></body></html>'''
        (OUT / f'{slug}.html').write_text(html, encoding='utf-8')
    (OUT / 'handbook.css').write_text(CSS, encoding='utf-8')
    print(json.dumps(dict(pages=len(pages), environment_names=len(env), registered_test_names=len(tests), base_revision=revision)))


if __name__ == '__main__':
    main()
