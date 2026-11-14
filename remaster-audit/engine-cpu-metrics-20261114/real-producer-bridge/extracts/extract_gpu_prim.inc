/* Arming rate for perspective-correct UVs, per condition.
 *
 * perspective_triangles alone cannot answer "how much texture warp is left",
 * because it has no denominator: comparing it to gp0_draw mixes in untextured
 * mono and gouraud primitives that are correctly never armed, and comparing it
 * to a vertex-lookup count divided by three is the same error. `attempts`
 * counts exactly the textured triangles that reach this predicate, so
 * armed/attempts IS the perspective coverage, and the three reject counters
 * say which condition is spending it. Diagnostic only. */
static struct {
    uint64_t attempts;      /* textured triangles submitted                 */
    uint64_t armed;         /* got perspective-correct UVs                  */
    uint64_t no_correction; /* texture correction off                       */
    uint64_t no_source;     /* CPU-built primitive, no packet address       */
    uint64_t no_depth;      /* a vertex had no recorded Z, or Z == 0        */
} s_texcorr;

void gpu_texture_correction_stats(uint64_t *attempts, uint64_t *armed,
                                  uint64_t *no_correction,
                                  uint64_t *no_source, uint64_t *no_depth) {
    if (attempts)      *attempts      = s_texcorr.attempts;
    if (armed)         *armed         = s_texcorr.armed;
    if (no_correction) *no_correction = s_texcorr.no_correction;
    if (no_source)     *no_source     = s_texcorr.no_source;
    if (no_depth)      *no_depth      = s_texcorr.no_depth;
}

/* Enable perspective UVs only when every position word came from an exact
 * SWC2 projection store at that same DMA packet address. This preserves the
 * association through ordering-table reordering and rejects CPU-built UI. */
/* remix-provenance v2: one textured primitive's GP0 vertex words -> view
 * census (DATAFLOW only). Reads gp0 state; touches no renderer state. */
static void view_census_gp0(int kind, const int *idx, int n) {
    uint32_t words[4], addrs[4];
    for (int i = 0; i < n; i++) {
        words[i] = gp0_cmd_buf[idx[i]];
        addrs[i] = (gp0_cmd_source_addr == 0xFFFFFFFFu)
                       ? 0xFFFFFFFFu
                       : gp0_cmd_source_addr + (uint32_t)idx[i] * 4u;
    }
    pgxp_view_census_prim(kind, words, addrs, n);
}

static void prepare_texture_triangle(int i0, int i1, int i2) {
    if (s_view_census) {
        const int ti[3] = { i0, i1, i2 };
        view_census_gp0(PGXP_VIEW_CENSUS_TRI, ti, 3);
    }
    gr_set_perspective_triangle(0, 0.0f, 0.0f, 0.0f);
    s_texcorr.attempts++;
    if (!s_texture_correction_enabled) { s_texcorr.no_correction++; return; }
    if (gp0_cmd_source_addr == 0xFFFFFFFFu) { s_texcorr.no_source++; return; }
    int indices[3] = { i0, i1, i2 };
    uint16_t z[3];
    for (int i = 0; i < 3; i++) {
        uint32_t addr = (gp0_cmd_source_addr + (uint32_t)indices[i] * 4u) & 0x1FFFFCu;
        if (!gte_precision_load_word(addr, gp0_cmd_buf[indices[i]], NULL, NULL, &z[i]) ||
            z[i] == 0) {
            s_texcorr.no_depth++;
            return;
        }
    }
    float q[3] = { 1.0f / (float)z[0], 1.0f / (float)z[1], 1.0f / (float)z[2] };
    float qmax = q[0];
    if (q[1] > qmax) qmax = q[1];
    if (q[2] > qmax) qmax = q[2];
    if (qmax <= 0.0f) { s_texcorr.no_depth++; return; }
    s_texcorr.armed++;
    gr_set_perspective_triangle(1, q[0] / qmax, q[1] / qmax, q[2] / qmax);
}

