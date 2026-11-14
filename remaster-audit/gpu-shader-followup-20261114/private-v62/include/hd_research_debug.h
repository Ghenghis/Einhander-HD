#ifndef PSXRECOMP_HD_RESEARCH_DEBUG_H
#define PSXRECOMP_HD_RESEARCH_DEBUG_H
#include "hd_research_request.h"
#include "hd_research_filter.h"
extern uint8_t *memory_get_ram_ptr(void);
static void handle_research_capture(int id,const char *json){
 HdResearchRequest request;GlResearchState state;GlResearchEvent event;char error[192],path[2048],extra[1024];const char *problem=hdr_parse_request(json,&request);
 if(problem){send_err(id,problem);return;}memset(&event,0,sizeof event);extra[0]=0;
 if(!strcmp(request.op,"start")){if(!gl_renderer_research_start(request.path,&request.limits,&state,error,sizeof error)){send_err(id,error);return;}}
 else if(!strcmp(request.op,"stop"))gl_renderer_research_stop(&state);
 else if(!strcmp(request.op,"mark")){
  if(!gl_renderer_research_mark(request.label,memory_get_ram_ptr(),HDR_RAM_BYTES,&event,&state,error,sizeof error)){send_err(id,error);return;}
  snprintf(extra,sizeof extra,",\"event_file\":\"%s\",\"event_index\":%u,\"event_frame\":%llu,\"event_host_mono_ms\":%llu,\"event_bytes\":%llu,\"values\":{\"lives\":%u,\"invincibility_countdown\":%u,\"ammo_upper_unverified\":%u,\"ammo_lower_unverified\":%u}",event.file,event.index,(unsigned long long)event.frame,(unsigned long long)event.host_mono_ms,(unsigned long long)event.bytes,event.lives,event.invincibility,event.ammo_upper,event.ammo_lower);
 }else if(!gl_renderer_research_get(&state)){send_err(id,"Research capture state unavailable");return;}
 if(!hdr_json_escape(state.path,path,sizeof path)){send_err(id,"Capture path cannot be serialized");return;}
 send_fmt("{\"id\":%d,\"ok\":true,\"contract\":\"" HD_RESEARCH_CONTRACT "\",\"op\":\"%s\",\"ready\":%s,\"active\":%s,\"reason\":\"%s\",\"path\":\"%s\",\"frame\":%llu,\"host_mono_ms\":%llu,\"start_frame\":%llu,\"start_ms\":%llu,"
 "\"counts\":{\"sources\":%u,\"records\":%u,\"events\":%u,\"files\":%u,\"bytes\":%llu},\"limits\":{\"max_sources\":%u,\"max_records\":%u,\"max_events\":%u,\"max_frames\":%u,\"max_seconds\":%u,\"max_bytes\":%llu},"
 "\"caps\":{\"sources\":%s,\"records\":%s,\"events\":%s},\"sampled_signatures\":%u,\"event_reserved_bytes\":%llu,\"event_reserved_files\":%u,\"source_file_budget_paused\":%s,\"evidence_budget_paused\":%s,"
 "\"sampling\":{\"policy\":\"lru_identity_phase_uv_quadrant_lease_rate\",\"rate_per_second\":%.4f,\"burst\":%u,\"rows\":%llu,\"evictions\":%llu,\"repeat_skips\":%llu,\"rate_skips\":%llu,\"budget_skips\":%llu,\"record_cap_skips\":%llu},"
 "\"source_filter_supported\":true,\"source_filter\":{\"policy\":\"%s\",\"key_count\":%u,\"keys_fnv1a32\":%u,\"skipped_source_draws\":%llu,\"scope\":\"raw_source_archives_only\"},"
 "\"coverage\":\"sampled_activation_forward\",\"repeat_sample_frames\":60,\"source_cache_bytes_max\":33554432,\"signature_slots_max\":512,\"source_files_uploads_only\":true,\"ram_writes\":false,\"gpu_readback\":false,\"cpu_vram_may_be_stale\":true,\"full_replay\":false%s}",
 id,request.op,state.ready?"true":"false",state.active?"true":"false",state.reason,path,(unsigned long long)state.frame,(unsigned long long)state.host_mono_ms,(unsigned long long)state.start_frame,(unsigned long long)state.start_ms,
 state.sources,state.records,state.events,state.files,(unsigned long long)state.bytes,state.limits.max_sources,state.limits.max_records,state.limits.max_events,state.limits.max_frames,state.limits.max_seconds,(unsigned long long)state.limits.max_bytes,
 state.limits.max_sources&&state.sources>=state.limits.max_sources?"true":"false",state.limits.max_records&&state.records>=state.limits.max_records?"true":"false",state.limits.max_events&&state.events>=state.limits.max_events?"true":"false",state.sampled_signatures,(unsigned long long)state.event_reserved_bytes,state.event_reserved_files,state.files+state.event_reserved_files+4>1024?"true":"false",state.limits.max_bytes&&state.bytes+state.event_reserved_bytes+1536>state.limits.max_bytes?"true":"false",
 state.sampler_rate,state.sampler_burst,(unsigned long long)state.sampler_rows,(unsigned long long)state.sampler_evictions,(unsigned long long)state.sampler_repeat_skips,(unsigned long long)state.sampler_rate_skips,(unsigned long long)state.sampler_budget_skips,(unsigned long long)state.sampler_record_cap_skips,hdr_source_policy_name(state.limits.source_policy),state.limits.source_key_count,state.source_keys_fnv1a32,(unsigned long long)state.source_filter_skips,extra);
}
#endif
