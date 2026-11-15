/* s67 combined getters: BEGIN */
/* One locked snapshot serves every getter, so out.* and the gap fields of
 * audio_stats come from the same moment. Callers run on the main/emulation
 * thread (debug_server_poll safe point, runtime_perf_diag_tick), never inside
 * the audio callback and never while holding the audio lock: the acquisition
 * is not recursive. Without an open device there is no audio thread. */
static void s67_audio_out_snapshot(rab_telemetry *tel)
{
    if (sdl_audio_device) {
        psx_sdl_audio_lock(sdl_audio_device);
        rab_get_telemetry(&s_drc, tel);
        psx_sdl_audio_unlock(sdl_audio_device);
    } else {
        rab_get_telemetry(&s_drc, tel);
    }
}

extern "C" int psx_audio_out_stats_ex(double *fill_ms, double *target_ms,
                                      uint64_t *underruns,
                                      uint64_t *overflow_drops, double *correction,
                                      int *legacy, int *host_rate,
                                      uint64_t *gaps, uint64_t *max_gap_frames,
                                      uint64_t *cur_gap_frames, uint64_t *gap_epoch,
                                      uint64_t *gap_epoch_base_underruns,
                                      uint64_t *bridge_generation, int *gap_ok)
{
    *gaps = 0; *max_gap_frames = 0; *cur_gap_frames = 0; *gap_epoch = 0;
    *gap_epoch_base_underruns = 0;
    *bridge_generation = s_drc_generation;
    *gap_ok = 0;
    *legacy = audio_legacy_mode() ? 1 : 0;
    *host_rate = g_audio_host_rate;
    if (*legacy || !s_drc_ready) {
        *fill_ms = sdl_audio_device
                   ? (double)psx_sdl_audio_queued_size(sdl_audio_device)
                     / (44100.0 * 4.0) * 1000.0
                   : 0.0;
        *target_ms = 0.0; /* push queue — no DRC fill target */
        *underruns = g_legacy_underruns;
        *overflow_drops = 0;
        *correction = 0.0;
        return sdl_audio_device != 0;
    }
    rab_telemetry tel;
    s67_audio_out_snapshot(&tel);
    *fill_ms = tel.stats.last_fill_ms;
    *target_ms = s_drc.cfg.target_ms;
    *underruns = tel.stats.underrun_events;
    *overflow_drops = tel.stats.overflow_drops;
    *correction = tel.stats.last_correction;
    *gaps = tel.gap.gaps;
    *max_gap_frames = tel.gap.max_gap_frames;
    *cur_gap_frames = tel.gap.cur_gap_frames;
    *gap_epoch = tel.gap_epoch;
    *gap_epoch_base_underruns = tel.gap_epoch_base_underruns;
    *gap_ok = 1;
    return 1;
}

/* Old signature and return values unchanged (two callers). */
extern "C" int psx_audio_out_stats(double *fill_ms, double *target_ms,
                                   uint64_t *underruns,
                                   uint64_t *overflow_drops, double *correction,
                                   int *legacy, int *host_rate)
{
    uint64_t g, mx, cu, ep, base, gen; int ok;
    return psx_audio_out_stats_ex(fill_ms, target_ms, underruns, overflow_drops,
                                  correction, legacy, host_rate,
                                  &g, &mx, &cu, &ep, &base, &gen, &ok);
}

/* Gap-proposal getter kept for compatibility; same single snapshot. */
extern "C" int psx_audio_out_gap_stats(uint64_t *gaps, uint64_t *max_gap_frames,
                                       uint64_t *cur_gap_frames, uint64_t *gap_epoch)
{
    double f, t, c; uint64_t u, o, base, gen; int l, r, ok;
    (void)psx_audio_out_stats_ex(&f, &t, &u, &o, &c, &l, &r,
                                 gaps, max_gap_frames, cur_gap_frames, gap_epoch,
                                 &base, &gen, &ok);
    return ok;
}
/* s67 combined getters: END */
