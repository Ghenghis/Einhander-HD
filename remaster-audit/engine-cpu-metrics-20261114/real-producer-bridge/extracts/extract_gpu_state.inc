static int s_texture_correction_enabled = 0;
/* remix-provenance v2: opt-in per-primitive view census. Arms the PGXP
 * transport for collection only; geometry/texture correction (and so every
 * draw) stay exactly as the user configured them. */
static int s_view_census = 0;
extern int gte_precision_load_word(uint32_t addr, uint32_t packed,
                                   int32_t *x16, int32_t *y16, uint16_t *z);

/* Arm the PGXP dataflow transport for any consumer. Exact NCLIP is an internal
 * sign source only; this does not enable geometry or texture correction. */
void gpu_pgxp_rederive_enable(void) {
    pgxp_set_enabled(s_texture_correction_enabled ||
                     gte_geometry_correction_enabled() ||
                     ws_precise_nclip_cfg ||
                     s_view_census);
}

void gpu_texture_correction_set(int enabled) {
    s_texture_correction_enabled = enabled ? 1 : 0;
    gpu_pgxp_rederive_enable();
}

int gpu_texture_correction_enabled(void) {
    return s_texture_correction_enabled;
}

/* Arm/disarm the view census. Allocation failure of the view payload fails
 * closed (census stays off). Disarming re-derives the transport from the
 * user's own geometry/texture/NCLIP modes, which are never changed here. */
void gpu_view_census_set(int enabled) {
    int want = enabled ? 1 : 0;
    pgxp_set_view_payload(want);
    if (want && !pgxp_view_payload()) want = 0;
    s_view_census = want;
    pgxp_view_census_set(want);
    gpu_pgxp_rederive_enable();
}

int gpu_view_census_enabled(void) {
    return s_view_census;
}

