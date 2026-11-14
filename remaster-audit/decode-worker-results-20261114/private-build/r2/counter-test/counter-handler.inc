/* PRIVATE v6 read-only diagnostics. Full four reason tables; reject contract drift. */
extern int gl_renderer_class_mips_counters(uint64_t *out, int cap);
static void handle_hd_class_mips(int id,const char *json) {
    enum { HEAD=14, REASONS=21, TOTAL=HEAD+4*REASONS };
    (void)json; uint64_t v[TOTAL+1]={0}; char values[TOTAL*21+1]; size_t pos=0;
    int count=gl_renderer_class_mips_counters(v,TOTAL+1);
    if(count!=TOTAL){send_fmt("{\"id\":%d,\"ok\":false,\"error\":\"hdcm-counter-contract\"}",id);return;}
    for(int i=0;i<count;i++) {
        int wrote=snprintf(values+pos,sizeof(values)-pos,"%s%llu",i?",":"",(unsigned long long)v[i]);
        if(wrote<0 || (size_t)wrote>=sizeof(values)-pos) { send_fmt("{\"id\":%d,\"ok\":false}",id); return; }
        pos+=(size_t)wrote;
    }
    values[pos]=0;
    send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"hdcm-v6-counters\",\"head_count\":14,\"reason_count\":21,\"table_count\":4,\"values\":[%s]}",id,values);
}

