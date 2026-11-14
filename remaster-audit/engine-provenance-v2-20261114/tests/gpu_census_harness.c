/* gpu_census_harness.c — compiles the ACTUAL v2 code cut from the generated
 * src/gpu.c and src/debug_server.c (run_host_test_v2.py writes the work/*.inc
 * extracts by anchor) against the real pgxp / gte / census translation units.
 * Only the surrounding file-scope state those extracts read is provided here
 * (gp0 command buffer and source address, the precise-NCLIP config flag) plus
 * recording stand-ins for the two renderer/telemetry calls they make
 * (gr_set_perspective_triangle, debug_server_send_fmt). Test harness only. */

#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pgxp.h"

/* gpu.c file-scope state read by the extracts */
uint32_t gp0_cmd_buf[16];
uint32_t gp0_cmd_source_addr = 0xFFFFFFFFu;
int ws_precise_nclip_cfg = 0;

extern int gte_geometry_correction_enabled(void);
extern int gte_precision_load_word(uint32_t addr, uint32_t packed,
                                   int32_t *x16, int32_t *y16, uint16_t *z);

/* renderer call made by prepare_texture_triangle: record every call */
int   g_persp_calls = 0;
int   g_persp_last_on = -1;
float g_persp_last_q[3];
void gr_set_perspective_triangle(int enabled, float q0, float q1, float q2) {
    g_persp_calls++;
    g_persp_last_on = enabled;
    g_persp_last_q[0] = q0; g_persp_last_q[1] = q1; g_persp_last_q[2] = q2;
}

/* debug_server.c reply sink: keep the last reply */
char g_reply[65536];
void debug_server_send_fmt(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(g_reply, sizeof(g_reply), fmt, ap);
    va_end(ap);
}
#define send_fmt debug_server_send_fmt
static void send_err(int id, const char *msg) {
    send_fmt("{\"id\":%d,\"ok\":false,\"error\":\"%s\"}", id, msg);
}

/* found through -I<extract dir> (the runner extracts per build / mutant) */
#include "extract_gpu_state.inc"
#include "extract_gpu_prim.inc"
#include "extract_json_get_int.inc"
#include "extract_tcp_handler.inc"

/* entry points for the C++ test */
void harness_prepare_texture_triangle(int i0, int i1, int i2) { prepare_texture_triangle(i0, i1, i2); }
void harness_view_census_quad(const int *qi) { view_census_gp0(PGXP_VIEW_CENSUS_QUAD, qi, 4); }
const char *harness_tcp(int id, const char *json) {
    g_reply[0] = 0;
    handle_pgxp_view(id, json);
    return g_reply;
}
void harness_texcorr(uint64_t *att, uint64_t *armed, uint64_t *off, uint64_t *nosrc, uint64_t *noz) {
    gpu_texture_correction_stats(att, armed, off, nosrc, noz);
}
