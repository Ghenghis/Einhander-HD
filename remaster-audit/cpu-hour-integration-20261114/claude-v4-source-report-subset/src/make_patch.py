#!/usr/bin/env python3
"""Anchored patch generator v3 (prepared levels, preload; DESIGN-V3.md) - was v2: PRIVATE opt-in class-aware HD mips with hash-bound NATIVE-authority sidecars for a
COPY of the frozen v61 renderer (claude-einhander). The input file is only read. Every anchor must occur exactly
once; every insertion is pure addition (removing the inserted blocks reproduces the input byte for byte - checked).
See DESIGN-V2.md (DESIGN.md's centre-pixel authority is superseded and was never built).

Behaviour contract of the patched copy:
  * PSXRECOMP_HD_CLASS_MIPS unset / != "1", or PSXRECOMP_HD_CLASS_MIPS_DIR unset: no inserted statement runs except
    the env read and one uniform-location lookup at program setup; HD_FS's new branch is skipped
    (u_hd_class_levels is never set, so it stays 0).
  * Enabled (v3): sidecars listed in <dir>/index.txt are verified into a bounded cache at renderer init. Only keys
    with a cached sidecar that passes draw-time admission (level-0 identity, R1) get PREPARED levels, uploaded with
    verification; nothing is built on the draw thread. Every rejection is counted by reason and leaves the slot on
    the ORIGINAL v61 path (incl. the world experiment's own glGenerateMipmap where it applies).
  * Admitted slots: MAX_LEVEL = log2(scale), facade_mips_ready set so glGenerateMipmap never replaces the chain;
    sampled with LINEAR_MIPMAP_LINEAR + class at round(lod) in filter mode only.
  * Point path (u_filter == 0) untouched: no mip filter is selected in point mode, u_hd_class_levels is 0 there, and
    every new shader branch requires u_hd_class_levels > 0 (and the class branch u_filter != 0).
"""
import hashlib
from pathlib import Path

V61_SRC = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/"
               "sampling-build-v61-view-metrics-r2/src/gpu_gl_renderer.c")
V61_SHA256 = "90c6a4e15d8e956ca7be28f1cd5219add1e1c2ee37f31fbd361711db0510e3a1"

GLUE = r'''/* PRIVATE opt-in (PSXRECOMP_HD_CLASS_MIPS=1 and PSXRECOMP_HD_CLASS_MIPS_DIR; default OFF; claude-einhander
 * renderer-v61-classmip v3, DESIGN-V3.md). PREPARED class-aware levels 1..log2(scale) come from hash-bound
 * native-authority sidecars listed in <dir>/index.txt; they are verified and loaded into a bounded cache at renderer
 * init (hd_facade_motion_init, before gameplay). The draw thread never builds levels (the builder is compiled out):
 * on the first non-resident draw of a cached key it checks the decoded level-0 identity + R1 and uploads the prepared
 * levels with verification (fail closed). Admission is the explicit sidecar list only (independent of the
 * facade/world experiment, whose own gate admits no alpha-structured drawn key: runs-ab/20261114T111427Z). Sampling
 * uses the levels in filter mode only. Any rejection leaves the slot on the original v61 path. No printing; counters
 * only (gl_renderer_class_mips_counters). */
#define HDCM_NO_BUILDER
#include "hd_class_mips.inc"
#define HDCM_PRELOAD_BYTES ((size_t)96 * 1024 * 1024)   /* preload byte cap (fixed; the cache never grows in play) */
#define HDCM_INDEX_LINES 64
static int s_hd_class_mips = -1, s_hdcm_levels_on, s_hdcm_rgb_on;
static char s_hd_class_mips_dir[480];
static HdcmCache s_hdcm_cache;
static int s_hdcm_preloaded;
/* Any sidecar feature on: PSXRECOMP_HD_CLASS_MIPS=1 (class levels) and/or PSXRECOMP_HD_RGB_EDGES=1 (v4 RGB edge
 * renormalization), each exactly "1", both REQUIRING PSXRECOMP_HD_CLASS_MIPS_DIR (the verified sidecar list): every
 * opt-in stays limited to explicitly verified sidecar keys. */
static int hd_class_mips_enabled(void) {
    if (s_hd_class_mips < 0) {
        const char *levels = getenv("PSXRECOMP_HD_CLASS_MIPS");
        const char *rgb = getenv("PSXRECOMP_HD_RGB_EDGES");
        const char *dir = getenv("PSXRECOMP_HD_CLASS_MIPS_DIR");
        s_hdcm_levels_on = levels && strcmp(levels, "1") == 0;
        s_hdcm_rgb_on = rgb && strcmp(rgb, "1") == 0;
        s_hd_class_mips = (s_hdcm_levels_on || s_hdcm_rgb_on) && dir && *dir &&
                          strlen(dir) < sizeof s_hd_class_mips_dir;
        if (s_hd_class_mips) memcpy(s_hd_class_mips_dir, dir, strlen(dir) + 1);
        else s_hdcm_levels_on = s_hdcm_rgb_on = 0;
    }
    return s_hd_class_mips;
}
static struct {
    uint64_t preload_ok, preload_bytes, preload_ticks;
    uint64_t attempted, admitted, levels_uploaded, bytes, ticks, rgb_edge_slots, rgb_opaque_skipped;
    uint64_t preload_rejected[HDCM_REASONS];         /* indexed by HDCM_E_* */
    uint64_t rejected[HDCM_REASONS];                 /* indexed by HDCM_E_* */
} s_hdcm_diag;
/* Diagnostics accessor for a future TCP verb: preload_ok, preload_bytes, preload_ticks, attempted, admitted,
 * levels_uploaded, bytes, ticks, rgb_edge_slots, rgb_opaque_skipped, then preload_rejected[HDCM_REASONS], then
 * rejected[HDCM_REASONS]. Returns the number of values written. */
int gl_renderer_class_mips_counters(uint64_t *out, int cap);
int gl_renderer_class_mips_counters(uint64_t *out, int cap) {
    const uint64_t head[10] = {s_hdcm_diag.preload_ok, s_hdcm_diag.preload_bytes, s_hdcm_diag.preload_ticks,
                               s_hdcm_diag.attempted, s_hdcm_diag.admitted, s_hdcm_diag.levels_uploaded,
                               s_hdcm_diag.bytes, s_hdcm_diag.ticks, s_hdcm_diag.rgb_edge_slots,
                               s_hdcm_diag.rgb_opaque_skipped};
    int n = 0;
    for (int i = 0; out && i < 10 && n < cap; i++) out[n++] = head[i];
    for (int i = 0; out && i < HDCM_REASONS && n < cap; i++) out[n++] = s_hdcm_diag.preload_rejected[i];
    for (int i = 0; out && i < HDCM_REASONS && n < cap; i++) out[n++] = s_hdcm_diag.rejected[i];
    return n;
}
/* Renderer init only (before gameplay). Each listed sidecar is size-checked before any allocation, read once and
 * fully verified by hdcm_cache_add (self-hash, level hashes, classes, M4, key, caps). */
static void hd_class_mips_preload(void) {
    if (!hd_class_mips_enabled() || s_hdcm_preloaded) return;
    s_hdcm_preloaded = 1;
    hdcm_cache_init(&s_hdcm_cache, HDCM_PRELOAD_BYTES);
    const uint64_t t0 = SDL_GetPerformanceCounter();
    char path[600];
    snprintf(path, sizeof path, "%s/index.txt", s_hd_class_mips_dir);
    FILE *idx = fopen(path, "rb");
    if (!idx) { ++s_hdcm_diag.preload_rejected[HDCM_E_NOFILE]; return; }
    char line[96];
    for (int lines = 0; lines < HDCM_INDEX_LINES && fgets(line, sizeof line, idx); lines++) {
        unsigned th = 0, ph = 0;
        if (sscanf(line, "%8x-%8x", &th, &ph) != 2) continue;
        snprintf(path, sizeof path, "%s/%08X-%08X.hdcm", s_hd_class_mips_dir, th, ph);
        FILE *f = fopen(path, "rb");
        if (!f) { ++s_hdcm_diag.preload_rejected[HDCM_E_NOFILE]; continue; }
        long n = -1;
        if (fseek(f, 0, SEEK_END) == 0) n = ftell(f);
        if (n <= 0 || fseek(f, 0, SEEK_SET) != 0 || !hdcm_cache_fits(&s_hdcm_cache, (size_t)n)) {
            fclose(f);
            ++s_hdcm_diag.preload_rejected[n <= 0 ? HDCM_E_SIZE : HDCM_E_ALLOC];
            continue;
        }
        uint8_t *buf = (uint8_t *)malloc((size_t)n);
        const size_t got = buf ? fread(buf, 1, (size_t)n, f) : 0;
        fclose(f);
        if (!buf || got != (size_t)n) {
            free(buf);
            ++s_hdcm_diag.preload_rejected[buf ? HDCM_E_SIZE : HDCM_E_ALLOC];
            continue;
        }
        const int rc = hdcm_cache_add(&s_hdcm_cache, th, ph, buf, (size_t)n);  /* owns buf, or frees it */
        if (rc != HDCM_OK) { ++s_hdcm_diag.preload_rejected[rc]; continue; }
        ++s_hdcm_diag.preload_ok;
        s_hdcm_diag.preload_bytes += (uint64_t)n;
    }
    fclose(idx);
    s_hdcm_diag.preload_ticks += SDL_GetPerformanceCounter() - t0;
}
/* Upload one prepared level to the bound texture and verify it by its level dimensions (glGetTexLevelParameteriv,
 * as the facade path already does): the GL error state is NOT consumed, so the renderer's existing error
 * observability is unchanged. 0 = verified. */
static int hd_class_mips_gl_upload(void *ctx, int L, int lw, int lh, const uint8_t *rgba) {
    (void)ctx;
    glTexImage2D(GL_TEXTURE_2D, L, GL_RGBA8, lw, lh, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
    GLint got_w = 0, got_h = 0;
    glGetTexLevelParameteriv(GL_TEXTURE_2D, L, GL_TEXTURE_WIDTH, &got_w);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, L, GL_TEXTURE_HEIGHT, &got_h);
    return got_w == lw && got_h == lh ? 0 : -1;
}
/* Draw thread, non-resident path, right after hd_tex_object() uploaded level 0 (px is the live decode lease; the
 * slot texture is bound on unit zero). Bounded work: cache lookup, one level-0 hash, one R1 pass, verified uploads
 * of prepared bytes. No allocation, no file access, no level building. */
static void hd_class_mips_admit_slot(HdTexSlot *slot, const HdTexturePixels *px,
                                     const HdTextureSourceMatch *m, const HdTextureDrawQuery *q) {
    if (!slot || !px || !px->rgba || !m || !q || slot->class_mip_levels || slot->rgb_edges ||
        slot->facade_mips_ready || slot->facade_mips_failed) return;
    ++s_hdcm_diag.attempted;
    const uint64_t t0 = SDL_GetPerformanceCounter();
    const HdcmSidecar *sc = hdcm_cache_find(&s_hdcm_cache, m->texture_hash, m->palette_hash);
    int rc = sc ? HDCM_OK : HDCM_E_NOFILE, uploaded = 0, touched = 0;
    size_t extra = 0;
    if (rc == HDCM_OK)
        rc = hdcm_sidecar_admit(sc, m->texture_hash, m->palette_hash,
                                (uint32_t)m->upload_width_words * (4u >> q->depth), m->upload_height,
                                px->rgba, px->stride, px->width, px->height);
    if (rc == HDCM_OK && (slot->w != px->width || slot->h != px->height)) rc = HDCM_E_HD_DIMS;
    if (rc == HDCM_OK && s_hdcm_levels_on) {
        touched = 1;
        rc = hdcm_upload_prepared(sc, hd_class_mips_gl_upload, NULL, &uploaded, &extra);
    }
    if (rc != HDCM_OK) {
        /* Fail closed: a partial chain is never admitted. Restore the original v61 sampling state: BASE 0 and
         * GL's default MAX_LEVEL, so the experiment's own glGenerateMipmap later regenerates EVERY level from
         * level 0 (overwriting any partial prepared level); slot flags stay untouched. */
        if (touched) {
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_BASE_LEVEL, 0);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 1000);
        }
        ++s_hdcm_diag.rejected[rc];
        return;
    }
    if (s_hdcm_levels_on) {
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_BASE_LEVEL, 0);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, (GLint)sc->levels);
        slot->class_mip_levels = sc->levels;
        slot->facade_mips_ready = 1;                          /* glGenerateMipmap never replaces this chain */
        slot->facade_mip_levels = (unsigned)sc->levels + 1u;
        slot->facade_mip_bytes = extra;
        s_hd_facade_motion.resident_mip_bytes += extra;
        s_hdcm_diag.levels_uploaded += (uint64_t)uploaded;
        s_hdcm_diag.bytes += extra;
    }
    if (s_hdcm_rgb_on) {
        /* v4: RGB edges only where the hash-bound sidecar says level 0 has cutout texels (opaque pages skip the
         * extra fetches entirely) */
        slot->rgb_edges = (sc->flags & HDCM_FLAG_HAS_CUTOUT) ? 1u : 0u;
        if (slot->rgb_edges) ++s_hdcm_diag.rgb_edge_slots;
        else ++s_hdcm_diag.rgb_opaque_skipped;
    }
    ++s_hdcm_diag.admitted;
    s_hdcm_diag.ticks += SDL_GetPerformanceCounter() - t0;
}
/* Per draw, program in use, slot texture bound on unit zero. A slot with prepared class levels samples them in
 * filter mode only (point mode keeps NEAREST and u_hd_class_levels 0). With the facade/world experiment active the
 * experiment already selected LINEAR_MIPMAP_LINEAR; otherwise this selects it for the admitted slot. The v61
 * base-filter cache is not disturbed: it only skips its own redundant LINEAR/NEAREST writes. */
static void hd_class_mips_sampling(HdTexSlot *slot, int facade_active) {
    const int cl = (s_hdcm_levels_on && s_tex_filter && slot && slot->class_mip_levels) ? (int)slot->class_mip_levels : 0;
    if (cl && !facade_active) glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
    p_glUniform1i(s_hd_uClassLevels, cl);
    /* v4: RGB edges for verified has-cutout slots in filter mode only; HD_FS keeps class/STP authority unchanged and
     * picks the level-0 branch (class levels 0, facade off) or the lod<1 class branch (class levels > 0) */
    p_glUniform1i(s_hd_uRgbEdges, (s_hdcm_rgb_on && s_tex_filter && slot && slot->rgb_edges) ? 1 : 0);
}

'''

FS_CLASS = (
    '    "  /* PRIVATE opt-in class-aware levels: the class follows the RGB minification, from\\n"\n'
    '    "   * explicit cell-owned levels (never glGenerateMipmap); 0 = off (level-0 authority). */\\n"\n'
    '    "  if (u_filter != 0 && u_hd_class_levels > 0) {\\n"\n'
    '    "    vec2 cgx = facade_dx * vec2(hd_size), cgy = facade_dy * vec2(hd_size);\\n"\n'
    '    "    float clod = clamp(log2(max(max(length(cgx), length(cgy)), 1e-8)),\\n"\n'
    '    "                       0.0, float(u_hd_class_levels));\\n"\n'
    '    "    int lc = int(floor(clod + 0.5));\\n"\n'
    '    "    if (lc > 0) {\\n"\n'
    '    "      ivec2 lsz = textureSize(u_hd, lc);\\n"\n'
    '    "      ivec2 lpx = clamp(ivec2(floor(authority_pos * vec2(lsz))), ivec2(0), lsz - ivec2(1));\\n"\n'
    '    "      class_alpha = texelFetch(u_hd, lpx, lc).a;\\n"\n'
    '    "    }\\n"\n'
    '    "  }\\n"\n')

# (name, anchor, inserted text, position: "after" | "before")
EDITS = [
    ("gl-defines",
     "#ifndef GL_LINEAR_MIPMAP_LINEAR\n#define GL_LINEAR_MIPMAP_LINEAR 0x2703\n#endif\n",
     "#ifndef GL_TEXTURE_BASE_LEVEL\n#define GL_TEXTURE_BASE_LEVEL 0x813C\n#endif\n"
     "#ifndef GL_TEXTURE_MAX_LEVEL\n#define GL_TEXTURE_MAX_LEVEL 0x813D\n#endif\n", "after"),
    ("hd-fs-uniform",
     '    "uniform int u_hd_facade_motion; /* opt-in, exact facade RGB only */\\n"\n',
     '    "uniform int u_hd_class_levels; /* PRIVATE opt-in class-aware levels 1..n; 0 = off */\\n"\n'
     '    "uniform int u_hd_rgb_edges; /* PRIVATE opt-in v4 RGB edge renormalization; 0 = off */\\n"\n', "after"),
    ("hd-fs-rgb-helper",
     '    "  return vec4(rgb,stp>=0.5?1.0:127.0/255.0);\\n"\n    "}\\n"\n',
     '    "// PRIVATE opt-in v4 (root rgb-edge r4, reviewed): bilinear over VISIBLE level taps only, renormalized;\\n"\n'
     '    "// .a = summed visible weight. Same taps/clamp as GL_LINEAR + CLAMP_TO_EDGE; RGB only, never class/STP.\\n"\n'
     '    "vec4 hd_visible_rgb(vec2 pos, int level) {\\n"\n'
     '    "  ivec2 size = textureSize(u_hd, level);\\n"\n'
     '    "  vec2 p = pos * vec2(size) - vec2(0.5);\\n"\n'
     '    "  ivec2 b = ivec2(floor(p)); vec2 f = fract(p);\\n"\n'
     '    "  vec4 t0 = texelFetch(u_hd, clamp(b, ivec2(0), size - ivec2(1)), level);\\n"\n'
     '    "  vec4 t1 = texelFetch(u_hd, clamp(b + ivec2(1, 0), ivec2(0), size - ivec2(1)), level);\\n"\n'
     '    "  vec4 t2 = texelFetch(u_hd, clamp(b + ivec2(0, 1), ivec2(0), size - ivec2(1)), level);\\n"\n'
     '    "  vec4 t3 = texelFetch(u_hd, clamp(b + ivec2(1, 1), ivec2(0), size - ivec2(1)), level);\\n"\n'
     '    "  vec4 w = vec4((1.0 - f.x) * (1.0 - f.y), f.x * (1.0 - f.y), (1.0 - f.x) * f.y, f.x * f.y);\\n"\n'
     '    "  w *= vec4(t0.a > 0.0 ? 1.0 : 0.0, t1.a > 0.0 ? 1.0 : 0.0, t2.a > 0.0 ? 1.0 : 0.0, t3.a > 0.0 ? 1.0 : 0.0);\\n"\n'
     '    "  float n = dot(w, vec4(1.0));\\n"\n'
     '    "  return vec4((t0.rgb * w.x + t1.rgb * w.y + t2.rgb * w.z + t3.rgb * w.w) / max(n, 1e-8), n);\\n"\n'
     '    "}\\n"\n', "after"),
    ("hd-fs-rgb-edges",
     '    "  if(native_edge){c=hd_edge_sample(uv);class_alpha=c.a;}\\n"\n',
     '    "  /* PRIVATE opt-in v4 RGB edges (verified has-cutout sidecar keys, filter mode). Conflict fix vs v3:\\n"\n'
     '    "   * class levels > 0 (facade OR non-facade): only lod < 1, level 0/1 visible taps blended by lod;\\n"\n'
     '    "   * class levels 0: only the ordinary non-facade level-0 path. Opaque footprints keep hardware RGB. */\\n"\n'
     '    "  if (u_hd_rgb_edges != 0 && u_filter != 0 && !native_edge) {\\n"\n'
     '    "    if (u_hd_class_levels > 0) {\\n"\n'
     '    "      vec2 rgx = facade_dx * vec2(hd_size), rgy = facade_dy * vec2(hd_size);\\n"\n'
     '    "      float rlod = clamp(log2(max(max(length(rgx), length(rgy)), 1e-8)), 0.0, float(u_hd_class_levels));\\n"\n'
     '    "      if (rlod < 1.0) {\\n"\n'
     '    "        vec4 edge0 = hd_visible_rgb(rgb_pos, 0);\\n"\n'
     '    "        if (edge0.a < 0.999999) {\\n"\n'
     '    "          vec4 edge1 = hd_visible_rgb(rgb_pos, 1);\\n"\n'
     '    "          vec3 rgb1 = edge1.a > 1e-8 ? edge1.rgb : textureLod(u_hd, rgb_pos, 1.0).rgb;\\n"\n'
     '    "          vec3 rgb0 = edge0.a > 1e-8 ? edge0.rgb : rgb1;\\n"\n'
     '    "          c.rgb = mix(rgb0, rgb1, rlod);\\n"\n'
     '    "        }\\n"\n'
     '    "      }\\n"\n'
     '    "    } else if (u_hd_facade_motion == 0) {\\n"\n'
     '    "      vec4 edge0 = hd_visible_rgb(rgb_pos, 0);\\n"\n'
     '    "      if (edge0.a > 1e-8 && edge0.a < 0.999999) c.rgb = edge0.rgb;\\n"\n'
     '    "    }\\n"\n'
     '    "  }\\n"\n', "before"),
    ("hd-fs-class",
     '    "  float class_alpha = texelFetch(u_hd, authority_px, 0).a;\\n"\n', FS_CLASS, "after"),
    ("slot-field",
     "    float facade_anisotropy;\n} HdTexSlot;",
     "    unsigned class_mip_levels; /* PRIVATE opt-in class-aware levels (0 = none) */\n"
     "    unsigned rgb_edges;        /* PRIVATE opt-in v4 RGB edges for a verified has-cutout key */\n", "before-tail:} HdTexSlot;"),
    ("uniform-var",
     "static GLint s_hd_uFacadeMotion = -1;\n",
     "static GLint s_hd_uClassLevels = -1, s_hd_uRgbEdges = -1; /* PRIVATE opt-in class levels / v4 RGB edges */\n", "after"),
    ("glue",
     "/* Called with this slot's texture bound on texture unit zero. Level-zero\n", GLUE, "before"),
    ("hd-fs-rgb",
     '    "    } else c = texture(u_hd, (u_hd_off + suv) / u_hd_dim);\\n"\n',
     '    "    if (u_hd_class_levels > 0 && u_hd_facade_motion == 0) /* PRIVATE opt-in class levels */\\n"\n'
     '    "      c = textureGrad(u_hd, (u_hd_off + suv) / u_hd_dim, facade_dx, facade_dy);\\n"\n', "after"),
    ("draw-build",
     "        tex = resident_tex ? resident_tex : hd_tex_object(m.texture_hash, m.palette_hash, &px);\n"
     "        glBindTexture(GL_TEXTURE_2D, tex);\n",
     "        if(!resident_tex && hd_class_mips_enabled()) /* PRIVATE opt-in: sidecar-listed keys only */\n"
     "            hd_class_mips_admit_slot(hd_tex_find(m.texture_hash,m.palette_hash),&px,&m,&q);\n", "after"),
    ("preload-proto",
     "static void hd_facade_motion_init(void) {\n",
     "static void hd_class_mips_preload(void); /* PRIVATE opt-in (renderer-v61-classmip v3) */\n", "before"),
    ("preload-call",
     "    if(!s_hd_facade_motion.enabled && !s_hd_world_sampling)return;\n",
     "    hd_class_mips_preload(); /* PRIVATE opt-in: verified prepared sidecars, before gameplay */\n", "before"),
    ("draw-uniform",
     "            p_glUniform1i(s_hd_uFacadeMotion,facade_motion);\n",
     "            if(hd_class_mips_enabled()) hd_class_mips_sampling(sampling_slot,facade_motion); /* PRIVATE opt-in */\n",
     "after"),
    ("base-sampling",
     "            hd_base_sampling(sampling_slot);\n",
     "            if(hd_class_mips_enabled()) /* PRIVATE opt-in */\n"
     "                hd_class_mips_sampling(resident?resident:hd_tex_find(m.texture_hash,m.palette_hash),0);\n",
     "after"),
    ("uniform-location",
     '        s_hd_uFacadeMotion = p_glGetUniformLocation(s_hd_prog,"u_hd_facade_motion");\n',
     '        s_hd_uClassLevels = p_glGetUniformLocation(s_hd_prog,"u_hd_class_levels"); /* PRIVATE opt-in */\n'
     '        s_hd_uRgbEdges = p_glGetUniformLocation(s_hd_prog,"u_hd_rgb_edges"); /* PRIVATE opt-in v4 */\n',
     "after"),
]


def edits_for(text):
    """EDITS with real newlines converted to the input's own newline style (the v61 file is CRLF; C-string
    escapes written as backslash-n are characters, not newlines, and are left alone)."""
    nl = "\r\n" if "\r\n" in text else "\n"
    return [(n, a.replace("\n", nl), i.replace("\n", nl), p) for n, a, i, p in EDITS]


def patch(text):
    """Return (patched_text, receipts). `text` must be the exact decoded bytes (no newline translation).
    Raises AssertionError on any anchor that is not unique or if the result is not pure addition."""
    out = text
    receipts = []
    edits = edits_for(text)
    for name, anchor, ins, pos in edits:
        n = out.count(anchor)
        assert n == 1, f"anchor {name}: {n} occurrences"
        i = out.index(anchor)
        if pos == "after":
            at = i + len(anchor)
        elif pos == "before":
            at = i
        elif pos.startswith("before-tail:"):
            tail = pos.split(":", 1)[1]
            at = i + anchor.index(tail)
        else:
            raise ValueError(pos)
        out = out[:at] + ins + out[at:]
        receipts.append(dict(name=name, anchor_sha256=hashlib.sha256(anchor.encode()).hexdigest(),
                             inserted_sha256=hashlib.sha256(ins.encode()).hexdigest(),
                             inserted_lines=ins.count("\n"), line=out[:at].count("\n") + 1, anchor_count=n))
    # pure addition: removing every inserted block restores the input exactly
    back = out
    for (name, anchor, ins, pos) in reversed(edits):
        assert back.count(ins) == 1, f"inserted block {name} not unique"
        back = back.replace(ins, "", 1)
    assert back == text, "patch is not pure addition"
    return out, receipts


if __name__ == "__main__":
    raw = V61_SRC.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == V61_SHA256
    src = raw.decode("utf-8")
    p, r = patch(src)
    print(len(src.splitlines()), "->", len(p.splitlines()), "lines;", len(r), "insertions")
