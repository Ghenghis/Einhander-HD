static void s67_pump_after_push(const rab_telemetry *tel, int resync) {
    static uint64_t prev_underruns = 0;
    static uint64_t prev_generation = 0;
    extern int g_audio_unmute_resync;
    if (prev_generation != s_drc_generation) {
        prev_generation = s_drc_generation;
        prev_underruns = 0;
    }
    if (resync) {
        prev_underruns = tel->stats.underrun_events;
        g_audio_unmute_resync = 0;
    } else if (tel->stats.underrun_events > prev_underruns) {
        audio_trace_event(AUDIO_EV_UNDERRUN,
                          (uint32_t)(tel->stats.underrun_events - prev_underruns), 1);
        prev_underruns = tel->stats.underrun_events;
    }
    s_pump_tel = *tel;
    s_pump_tel_valid = 1;
    s_pump_tel_generation = s_drc_generation;
}
