/* PRIVATE opt-in (PSXRECOMP_HD_CLASS_MIPS=1 and PSXRECOMP_HD_CLASS_MIPS_DIR; default OFF; claude-einhander
 * renderer-v61-classmip v3, DESIGN-V3.md). PREPARED class-aware levels 1..log2(scale) come from hash-bound
 * native-authority sidecars listed in <dir>/index.txt; they are verified and loaded into a bounded cache at renderer
 * init (hd_facade_motion_init, before gameplay). The draw thread never builds levels (the builder is compiled out):
 * on the first non-resident draw of a cached key it checks the decoded level-0 identity + R1 and uploads the prepared
 * levels with verification (fail closed). Admission is the explicit sidecar list only (independent of the
 * facade/world experiment, whose own gate admits no alpha-structured drawn key: runs-ab/20261114T111427Z). Sampling
 * uses the levels in filter mode only. Any rejection leaves the slot on the original v61 path. No printing; counters
 * only (gl_renderer_class_mips_counters). v4 adds RGB edges for has-cutout class-sidecar keys (DESIGN-V4.md); v5 adds
 * a separate identity-bound RGB-ONLY sidecar kind (HDCMRG01, PSXRECOMP_HD_RGB_EDGES_DIR, DESIGN-V5.md) for listed
 * keys without a class sidecar: RGB edge renormalization only, no class/R1 authority, no GL upload. */
#define HDCM_NO_BUILDER
#include "hd_class_mips.inc"
#define HDCM_PRELOAD_BYTES ((size_t)96 * 1024 * 1024)   /* preload byte cap (fixed; the cache never grows in play) */
#define HDCM_INDEX_LINES 64
static int s_hd_class_mips = -1, s_hdcm_levels_on, s_hdcm_rgb_on, s_hdcm_class_dir_on, s_hdcm_rgb_dir_on;
static char s_hd_class_mips_dir[480], s_hd_rgb_edges_dir[480];
static HdcmCache s_hdcm_cache;
static HdcmRgbCache s_hdcm_rgb_cache;                 /* v5: fixed storage, no heap */
static int s_hdcm_preloaded;
static int hdcm_dir_ok(const char *d, size_t cap) { return d && *d && strlen(d) < cap; }
/* Opt-ins, each exactly "1", default OFF; every one limited to explicitly verified sidecar keys:
 *   PSXRECOMP_HD_CLASS_MIPS=1 + PSXRECOMP_HD_CLASS_MIPS_DIR      prepared class levels (class sidecars HDCMSC02)
 *   PSXRECOMP_HD_RGB_EDGES=1  + PSXRECOMP_HD_CLASS_MIPS_DIR      RGB edges for class-sidecar keys (has-cutout bit)
 *   PSXRECOMP_HD_RGB_EDGES=1  + PSXRECOMP_HD_RGB_EDGES_DIR       v5: RGB edges for RGB-ONLY sidecar keys (HDCMRG01,
 *                                                                identity + has-cutout only, no class authority)
 * A key with a class sidecar always uses it (class authority first); RGB-only sidecars apply to the rest. */
static int hd_class_mips_enabled(void) {
    if (s_hd_class_mips < 0) {
        const char *levels = getenv("PSXRECOMP_HD_CLASS_MIPS");
        const char *rgb = getenv("PSXRECOMP_HD_RGB_EDGES");
        const char *dir = getenv("PSXRECOMP_HD_CLASS_MIPS_DIR");
        const char *rdir = getenv("PSXRECOMP_HD_RGB_EDGES_DIR");
        const int dir_ok = hdcm_dir_ok(dir, sizeof s_hd_class_mips_dir);
        const int rdir_ok = hdcm_dir_ok(rdir, sizeof s_hd_rgb_edges_dir);
        s_hdcm_levels_on = levels && strcmp(levels, "1") == 0 && dir_ok;
        s_hdcm_rgb_on = rgb && strcmp(rgb, "1") == 0 && (dir_ok || rdir_ok);
        s_hdcm_class_dir_on = dir_ok && (s_hdcm_levels_on || s_hdcm_rgb_on);
        s_hdcm_rgb_dir_on = rdir_ok && s_hdcm_rgb_on;
        s_hd_class_mips = s_hdcm_levels_on || s_hdcm_rgb_on;
        if (s_hdcm_class_dir_on) memcpy(s_hd_class_mips_dir, dir, strlen(dir) + 1);
        if (s_hdcm_rgb_dir_on) memcpy(s_hd_rgb_edges_dir, rdir, strlen(rdir) + 1);
    }
    return s_hd_class_mips;
}
static struct {
    uint64_t preload_ok, preload_bytes, preload_ticks;
    uint64_t attempted, admitted, levels_uploaded, bytes, ticks, rgb_edge_slots, rgb_opaque_skipped;
    uint64_t rgbonly_preload_ok, rgbonly_admitted, rgbonly_opaque_bypass;
    uint64_t preload_rejected[HDCM_REASONS];         /* indexed by HDCM_E_* (class sidecars) */
    uint64_t rejected[HDCM_REASONS];                 /* indexed by HDCM_E_* (class sidecars) */
    uint64_t rgbonly_preload_rejected[HDCM_REASONS]; /* v5, RGB-only sidecars */
    uint64_t rgbonly_rejected[HDCM_REASONS];         /* v5, RGB-only sidecars */
} s_hdcm_diag;
/* Diagnostics accessor for a future TCP verb: preload_ok, preload_bytes, preload_ticks, attempted, admitted,
 * levels_uploaded, bytes, ticks, rgb_edge_slots, rgb_opaque_skipped, rgbonly_preload_ok, rgbonly_admitted,
 * rgbonly_opaque_bypass, then preload_rejected[], rejected[], rgbonly_preload_rejected[], rgbonly_rejected[] (each
 * HDCM_REASONS long, indexed by HDCM_E_*). Returns the number of values written. */
int gl_renderer_class_mips_counters(uint64_t *out, int cap);
int gl_renderer_class_mips_counters(uint64_t *out, int cap) {
    const uint64_t head[13] = {s_hdcm_diag.preload_ok, s_hdcm_diag.preload_bytes, s_hdcm_diag.preload_ticks,
                               s_hdcm_diag.attempted, s_hdcm_diag.admitted, s_hdcm_diag.levels_uploaded,
                               s_hdcm_diag.bytes, s_hdcm_diag.ticks, s_hdcm_diag.rgb_edge_slots,
                               s_hdcm_diag.rgb_opaque_skipped, s_hdcm_diag.rgbonly_preload_ok,
                               s_hdcm_diag.rgbonly_admitted, s_hdcm_diag.rgbonly_opaque_bypass};
    const uint64_t *tables[4] = {s_hdcm_diag.preload_rejected, s_hdcm_diag.rejected,
                                 s_hdcm_diag.rgbonly_preload_rejected, s_hdcm_diag.rgbonly_rejected};
    int n = 0;
    for (int i = 0; out && i < 13 && n < cap; i++) out[n++] = head[i];
    for (int t = 0; t < 4; t++)
        for (int i = 0; out && i < HDCM_REASONS && n < cap; i++) out[n++] = tables[t][i];
    return n;
}
/* Renderer init only (before gameplay). Each listed sidecar is size-checked before any allocation, read once and
 * fully verified by hdcm_cache_add (self-hash, level hashes, classes, M4, key, caps). */
static void hdcm_preload_class(void) {
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
}
/* v5 RGB-only sidecars (<rgb dir>/index.txt, at most HDCM_RG_CACHE_MAX lines; each <KEY>.hdrg must be exactly
 * HDCM_RG_BYTES, checked by fseek/ftell BEFORE reading into a fixed stack buffer; hdcm_rgb_cache_add verifies magic,
 * self-hash, dims, flags and the file-name key, and copies into fixed static storage: no heap at all). */
static void hdcm_preload_rgb(void) {
    char path[600];
    snprintf(path, sizeof path, "%s/index.txt", s_hd_rgb_edges_dir);
    FILE *idx = fopen(path, "rb");
    if (!idx) { ++s_hdcm_diag.rgbonly_preload_rejected[HDCM_E_NOFILE]; return; }
    char line[96];
    for (int lines = 0; lines < HDCM_RG_CACHE_MAX && fgets(line, sizeof line, idx); lines++) {
        unsigned th = 0, ph = 0;
        if (sscanf(line, "%8x-%8x", &th, &ph) != 2) continue;
        snprintf(path, sizeof path, "%s/%08X-%08X.hdrg", s_hd_rgb_edges_dir, th, ph);
        FILE *f = fopen(path, "rb");
        if (!f) { ++s_hdcm_diag.rgbonly_preload_rejected[HDCM_E_NOFILE]; continue; }
        long n = -1;
        if (fseek(f, 0, SEEK_END) == 0) n = ftell(f);
        uint8_t buf[HDCM_RG_BYTES];
        size_t got = 0;
        if (n == (long)HDCM_RG_BYTES && fseek(f, 0, SEEK_SET) == 0) got = fread(buf, 1, sizeof buf, f);
        fclose(f);
        if (got != HDCM_RG_BYTES) { ++s_hdcm_diag.rgbonly_preload_rejected[HDCM_E_SIZE]; continue; }
        const int rc = hdcm_rgb_cache_add(&s_hdcm_rgb_cache, th, ph, buf, sizeof buf);
        if (rc != HDCM_OK) { ++s_hdcm_diag.rgbonly_preload_rejected[rc]; continue; }
        ++s_hdcm_diag.rgbonly_preload_ok;
        s_hdcm_diag.preload_bytes += HDCM_RG_BYTES;
    }
    fclose(idx);
}
static void hd_class_mips_preload(void) {
    if (!hd_class_mips_enabled() || s_hdcm_preloaded) return;
    s_hdcm_preloaded = 1;
    hdcm_cache_init(&s_hdcm_cache, HDCM_PRELOAD_BYTES);
    hdcm_rgb_cache_init(&s_hdcm_rgb_cache);
    const uint64_t t0 = SDL_GetPerformanceCounter();
    if (s_hdcm_class_dir_on) hdcm_preload_class();
    if (s_hdcm_rgb_dir_on) hdcm_preload_rgb();
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
    if (!sc && s_hdcm_rgb_dir_on) {
        /* v5 RGB-only kind, only for keys WITHOUT a class sidecar (class authority first; a class sidecar that fails
         * admission never falls back to RGB-only). Identity (key, native dims, HD dims, exact decoded level-0 hash)
         * and the has-cutout truth are verified against the live decode; no GL call, no level, alpha/STP/discard/
         * point/native edge untouched. Fully-opaque verified entries bypass (rgb_edges stays 0). */
        const HdcmRgbSidecar *rs = hdcm_rgb_cache_find(&s_hdcm_rgb_cache, m->texture_hash, m->palette_hash);
        int rrc = rs ? HDCM_OK : HDCM_E_NOFILE;
        if (rrc == HDCM_OK)
            rrc = hdcm_rgb_admit(rs, m->texture_hash, m->palette_hash,
                                 rs->nw, rs->nh,
                                 px->rgba, px->stride, px->width, px->height);
        if (rrc == HDCM_OK && (slot->w != px->width || slot->h != px->height)) rrc = HDCM_E_HD_DIMS;
        if (rrc != HDCM_OK) { ++s_hdcm_diag.rgbonly_rejected[rrc]; return; }
        slot->rgb_edges = (rs->flags & HDCM_RG_FLAG_HAS_CUTOUT) ? 1u : 0u;
        ++s_hdcm_diag.rgbonly_admitted;                       /* every verified RGB-only entry */
        if (!slot->rgb_edges) ++s_hdcm_diag.rgbonly_opaque_bypass;
        s_hdcm_diag.ticks += SDL_GetPerformanceCounter() - t0;
        return;
    }
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

