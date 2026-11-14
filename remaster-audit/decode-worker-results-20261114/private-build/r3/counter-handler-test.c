#define main frozen_glue_main
#define gl_renderer_class_mips_counters actual_class_mips_counters
#include "glue_harness.c"
#undef main
#undef gl_renderer_class_mips_counters
#include <stdarg.h>
static int forced_count=-999, grown_contract=0;
int gl_renderer_class_mips_counters(uint64_t *out,int cap){
    if(grown_contract){int n=cap<99?cap:99;for(int i=0;i<n;i++)out[i]=(uint64_t)i;return n;}
    int n=actual_class_mips_counters(out,cap);
    return forced_count==-999?n:forced_count;
}
static void send_fmt(const char *format,...){
    va_list ap;va_start(ap,format);vprintf(format,ap);va_end(ap);putchar('\n');
}
#include "counter-handler.inc"
int main(void){
    memset(&s_hdcm_diag,0,sizeof s_hdcm_diag);
    handle_hd_class_mips(10,"{}");
    s_hdcm_diag.rgbonly_identity_used=UINT64_MAX;
    s_hdcm_diag.rgbonly_rejected[HDCM_E_IDENTITY]=UINT64_MAX;
    handle_hd_class_mips(11,"{}");
    memset(&s_hdcm_diag,0xff,sizeof s_hdcm_diag);
    handle_hd_class_mips(12,"{}");
    grown_contract=1;handle_hd_class_mips(13,"{}");grown_contract=0;
    for(int i=0;i<4;i++){forced_count=(int[]){-1,0,97,99}[i];handle_hd_class_mips(20+i,"{}");}
    return 0;
}
