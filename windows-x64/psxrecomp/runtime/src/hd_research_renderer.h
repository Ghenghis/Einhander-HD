/* Included by gpu_gl_renderer.c after source-cache helpers. CPU-only recorder
 * adapter; deliberately no render, flush, GPU readback, or guest write calls. */
#ifndef PSXRECOMP_HD_RESEARCH_RENDERER_H
#define PSXRECOMP_HD_RESEARCH_RENDERER_H
#include "hd_research_filter.h"
static GlResearchLimits s_hd_research_source_filter;
static uint64_t s_hd_research_source_filter_skips;
static unsigned hd_research_event_files_reserve(void){
 return s_hd_research.events<s_hd_research.limits.max_events?s_hd_research.limits.max_events-s_hd_research.events:0;
}
static uint64_t hd_research_event_bytes_reserve(void){
 uint64_t reserve=(uint64_t)hd_research_event_files_reserve()*HDR_EVENT_BYTES;
 /* Preserve the full configured snapshot allowance whenever it fits. Only
  * inherently impossible custom allowances use the historical partial reserve. */
 if(reserve>s_hd_research.limits.max_bytes)reserve=s_hd_research.limits.max_bytes*3/4;
 return reserve;
}
/* Raw sources consume four files. Reserve one file and the full binary bytes
 * for every remaining event BEFORE any source sidecar or JSON record is
 * written. Rejection is soft; event snapshots retain their separate channel. */
static int hd_research_evidence_room(uint64_t bytes,unsigned files){
 uint64_t reserve=hd_research_event_bytes_reserve();unsigned reserve_files=hd_research_event_files_reserve();
 return s_hd_research.active && s_hd_research.files<=HDRC_MAX_FILES &&
  files<=HDRC_MAX_FILES-s_hd_research.files && reserve_files<=HDRC_MAX_FILES-s_hd_research.files-files &&
  s_hd_research.bytes_written<=s_hd_research.limits.max_bytes &&
  bytes<=s_hd_research.limits.max_bytes-s_hd_research.bytes_written &&
  reserve<=s_hd_research.limits.max_bytes-s_hd_research.bytes_written-bytes;
}
static int hd_research_ready(void){return gr_backend()==GR_BACKEND_OPENGL && s_ctx && s_raster_ok && s_hd_state>0 && s_hd_pack && s_vram;}
int gl_renderer_research_get(GlResearchState *out){
 if(!out)return 0;if(s_hd_research.active)hdrc_tick(&s_hd_research,s_frame_count,psx_host_mono_ms());
 memset(out,0,sizeof(*out));out->ready=hd_research_ready();out->active=s_hd_research.active;
 snprintf(out->path,sizeof out->path,"%s",s_hd_research.directory);snprintf(out->reason,sizeof out->reason,"%s",s_hd_research.stop_reason);
 out->frame=s_frame_count;out->host_mono_ms=psx_host_mono_ms();out->start_frame=s_hd_research.start_frame;out->start_ms=s_hd_research.start_ms;out->bytes=s_hd_research.bytes_written;
 out->sources=s_hd_research.sources;out->records=s_hd_research.records;out->events=s_hd_research.events;out->files=s_hd_research.files;
 out->sampled_signatures=s_hd_research_sampler.count;out->sampler_burst=s_hd_research_sampler.burst;out->sampler_rate=s_hd_research_sampler.rate;
 out->sampler_evictions=s_hd_research_sampler.evictions;out->sampler_repeat_skips=s_hd_research_sampler.repeat_skips;
 out->sampler_rate_skips=s_hd_research_sampler.rate_skips;out->sampler_budget_skips=s_hd_research_sampler.budget_skips;
 out->sampler_record_cap_skips=s_hd_research_sampler.record_cap_skips;out->sampler_rows=s_hd_research_sampler.rows;
 out->event_reserved_files=hd_research_event_files_reserve();out->event_reserved_bytes=hd_research_event_bytes_reserve();
 out->limits.max_sources=s_hd_research.limits.max_sources;out->limits.max_records=s_hd_research.limits.max_records;out->limits.max_events=s_hd_research.limits.max_events;
 out->limits.max_frames=s_hd_research.limits.max_frames;out->limits.max_seconds=s_hd_research.limits.max_seconds;out->limits.max_bytes=s_hd_research.limits.max_bytes;
 out->limits.source_policy=s_hd_research_source_filter.source_policy;out->limits.source_key_count=s_hd_research_source_filter.source_key_count;
 memcpy(out->limits.source_keys,s_hd_research_source_filter.source_keys,sizeof out->limits.source_keys);
 out->source_filter_skips=s_hd_research_source_filter_skips;out->source_keys_fnv1a32=hdr_source_filter_hash(&s_hd_research_source_filter);return 1;
}
int gl_renderer_research_start(const char *path,const GlResearchLimits *limits,GlResearchState *out,char *error,int capacity){
 HdResearchLimits chosen;char metadata[768];
 if(!hd_research_ready()){hdrc_error(error,capacity,"OpenGL HD source tracker is not ready");return 0;}
 if(!limits){hdrc_error(error,capacity,"Capture limits required");return 0;}
 if(!hdr_source_filter_valid(limits)){hdrc_error(error,capacity,"Invalid exact source filter");return 0;}
 chosen.max_sources=limits->max_sources;chosen.max_records=limits->max_records;chosen.max_events=limits->max_events;chosen.max_frames=limits->max_frames;chosen.max_seconds=limits->max_seconds;chosen.max_bytes=limits->max_bytes;
 if(!hdrc_start(&s_hd_research,path,&chosen,s_frame_count,psx_host_mono_ms(),error,capacity))return 0;
 s_hd_research_source_filter=*limits;s_hd_research_source_filter_skips=0;
 qsort(s_hd_research_source_filter.source_keys,s_hd_research_source_filter.source_key_count,sizeof(GlResearchSourceKey),hdr_source_key_compare);
 memset(s_hd_research_seen,0,sizeof s_hd_research_seen);s_hd_research_seen_count=0;
 hdr_sample_start(&s_hd_research_sampler,chosen.max_records,chosen.max_events,chosen.max_seconds,s_hd_research.start_ms);
 snprintf(metadata,sizeof metadata,"{\"event\":\"capture_start\",\"contract\":\"%s\",\"frame\":%llu,\"host_mono_ms\":%llu,\"coverage\":\"sampled_activation_forward\",\"repeat_sample_frames\":60,\"cpu_vram\":\"mirror_may_be_stale_no_gpu_readback\",\"replay\":false,\"ram_writes\":false,\"source_filter\":{\"policy\":\"%s\",\"key_count\":%u,\"keys_fnv1a32\":%u,\"scope\":\"raw_source_archives_only\"}}",HD_RESEARCH_CONTRACT,(unsigned long long)s_frame_count,(unsigned long long)psx_host_mono_ms(),hdr_source_policy_name(limits->source_policy),limits->source_key_count,hdr_source_filter_hash(&s_hd_research_source_filter));
 if(!hdrc_json(&s_hd_research,metadata,s_frame_count,psx_host_mono_ms())){hdrc_error(error,capacity,"Capture metadata could not be committed within limits");return 0;}
 return gl_renderer_research_get(out);
}
void gl_renderer_research_stop(GlResearchState *out){hdrc_stop(&s_hd_research,"user_stop");gl_renderer_research_get(out);}
int gl_renderer_research_mark(const char *label,const uint8_t *ram,unsigned ram_size,GlResearchEvent *event,GlResearchState *out,char *error,int capacity){
 uint8_t *blob;uint64_t frame=s_frame_count,now=psx_host_mono_ms();unsigned index;char leaf[64],line[768];
 if(!event||!hd_research_ready()||!hdrc_tick(&s_hd_research,frame,now)){hdrc_error(error,capacity,"Research capture is not active and ready");return 0;}
 if(!hdr_label_valid(label)||!ram||ram_size!=HDR_RAM_BYTES){hdrc_error(error,capacity,"Mark requires a bounded label and full read-only RAM pointer");return 0;}
 if(s_hd_research.events>=s_hd_research.limits.max_events){hdrc_error(error,capacity,"Research event cap reached; other channels remain active");return 0;}
 index=s_hd_research.events+1;blob=(uint8_t*)malloc(HDR_EVENT_BYTES);if(!blob){hdrc_error(error,capacity,"Snapshot allocation failed");return 0;}
 if(!hdr_build_event(blob,HDR_EVENT_BYTES,ram,ram_size,s_vram,VRAM_W*VRAM_H,label,frame,now,s_gpu_dirty,s_up_nrects,s_pack_dirty.set,s_cpu_auth_dual,(unsigned)gr_backend(),index)){free(blob);hdrc_error(error,capacity,"Snapshot validation failed");return 0;}
 snprintf(leaf,sizeof leaf,"event-%04u.bin",index);
 if(!hdrc_blob(&s_hd_research,leaf,blob,HDR_EVENT_BYTES,frame,now)){free(blob);hdrc_error(error,capacity,s_hd_research.stop_reason);return 0;}
 free(blob);++s_hd_research.events;memset(event,0,sizeof(*event));strcpy(event->file,leaf);event->index=index;event->frame=frame;event->host_mono_ms=now;event->bytes=HDR_EVENT_BYTES;
 event->lives=ram[0x813C4];event->invincibility=ram[0x85718];event->ammo_upper=ram[0x84832]|((unsigned)ram[0x84833]<<8);event->ammo_lower=ram[0x84834]|((unsigned)ram[0x84835]<<8);
 /* The binary remains complete even if the independent JSON record cap was
  * reached. The command response carries the same exact event association. */
 snprintf(line,sizeof line,"{\"event\":\"mark\",\"label\":\"%s\",\"event_file\":\"%s\",\"event_index\":%u,\"frame\":%llu,\"host_mono_ms\":%llu,\"bytes\":%u,\"cpu_safe_point\":true,\"gpu_readback\":false,\"cpu_vram_may_be_stale\":true,\"gpu_dirty\":%u,\"pending_cpu_upload_rects\":%u,\"pack_dirty\":%u,\"cpu_authority_dual\":%u}",label,leaf,index,(unsigned long long)frame,(unsigned long long)now,HDR_EVENT_BYTES,s_gpu_dirty,s_up_nrects,s_pack_dirty.set,s_cpu_auth_dual);
 if(s_hd_research.records<s_hd_research.limits.max_records && hd_research_evidence_room(strlen(line)+1,0))hdrc_json(&s_hd_research,line,frame,now);
 gl_renderer_research_get(out);return 1;
}
static void hd_research_source(const HdTextureSourceMatch *m,const HdTextureDrawQuery *q,uint64_t frame,uint64_t now){
 unsigned i,nclut=q->depth==0?16u:q->depth==1?256u:0u;size_t count=(size_t)m->upload_width_words*m->upload_height,frag_count=0,fi,known=0;HdTextureUploadFragment frags[4096];
 uint8_t *words,*valid,clut[512];const uint16_t *original;char leaf[96],metadata[768];
 if(!m->upload_serial||!count||count>VRAM_W*VRAM_H||s_hd_research.sources>=s_hd_research.limits.max_sources)return;
 if(!hdr_source_filter_selected(&s_hd_research_source_filter,m->texture_hash,m->palette_hash)){++s_hd_research_source_filter_skips;return;}
 for(i=0;i<s_hd_research_seen_count;++i)if(s_hd_research_seen[i].texture==m->texture_hash&&s_hd_research_seen[i].palette==m->palette_hash)return;
 if(!hd_research_evidence_room(count*3+sizeof metadata+nclut*2,4))return;
 words=(uint8_t*)calloc(count,2);valid=(uint8_t*)calloc(count,1);if(!words||!valid){free(words);free(valid);return;}
 original=hd_source_upload_find(m);
 if(original){for(i=0;i<count;++i){words[i*2]=(uint8_t)original[i];words[i*2+1]=(uint8_t)(original[i]>>8);valid[i]=1;}known=count;}
 else if(hd_texture_pack_upload_fragments(s_hd_pack,m->upload_serial,frags,4096,&frag_count)==HD_TEXTURE_LOOKUP_FOUND && frag_count<=4096){
  for(fi=0;fi<frag_count;++fi){HdTextureUploadFragment *fr=&frags[fi];unsigned y,x;for(y=0;y<fr->height;++y)for(x=0;x<fr->width;++x){unsigned ux=fr->source_x+x,uy=fr->source_y+y;size_t d;uint16_t word;if(ux>=m->upload_width_words||uy>=m->upload_height)continue;d=(size_t)uy*m->upload_width_words+ux;word=s_vram[((fr->y+y)&511)*VRAM_W+((fr->x+x)&1023)];words[d*2]=(uint8_t)word;words[d*2+1]=(uint8_t)(word>>8);if(!valid[d]){valid[d]=1;++known;}}}
 }
 for(i=0;i<nclut;++i){uint16_t v=q->vram[((unsigned)q->clut_y&511)*VRAM_W+(((unsigned)q->clut_x+i)&1023)];clut[i*2]=(uint8_t)v;clut[i*2+1]=(uint8_t)(v>>8);}
 if(!hdrc_claim_source(&s_hd_research,frame,now)){free(words);free(valid);return;}
 snprintf(leaf,sizeof leaf,"%08X-%08X.words.bin",m->texture_hash,m->palette_hash);if(!hdrc_blob(&s_hd_research,leaf,words,count*2,frame,now))goto done;
 snprintf(leaf,sizeof leaf,"%08X-%08X.valid.bin",m->texture_hash,m->palette_hash);if(!hdrc_blob(&s_hd_research,leaf,valid,count,frame,now))goto done;
 snprintf(leaf,sizeof leaf,"%08X-%08X.clut.bin",m->texture_hash,m->palette_hash);if(!hdrc_blob(&s_hd_research,leaf,clut,nclut*2,frame,now))goto done;
 snprintf(metadata,sizeof metadata,"{\"key\":\"%08X-%08X\",\"frame\":%llu,\"host_mono_ms\":%llu,\"upload_serial\":%llu,\"width_words\":%u,\"height\":%u,\"depth\":%u,\"clut_xy\":[%u,%u],\"clut_words\":%u,\"known_words\":%llu,\"total_words\":%llu,\"raw_origin\":\"%s\",\"cpu_vram_may_be_stale\":true,\"gpu_dirty\":%u,\"pending_cpu_upload_rects\":%u,\"pack_dirty\":%u,\"cpu_authority_dual\":%u,\"words_fnv1a32\":%u,\"clut_fnv1a32\":%u}",m->texture_hash,m->palette_hash,(unsigned long long)frame,(unsigned long long)now,(unsigned long long)m->upload_serial,m->upload_width_words,m->upload_height,q->depth,q->clut_x,q->clut_y,nclut,(unsigned long long)known,(unsigned long long)count,original?"cached_original_cpu_upload":"surviving_cpu_vram_fragments",s_gpu_dirty,s_up_nrects,s_pack_dirty.set,s_cpu_auth_dual,hdr_fnv(words,count*2),hdr_fnv(clut,nclut*2));
 snprintf(leaf,sizeof leaf,"%08X-%08X.source.json",m->texture_hash,m->palette_hash);if(!hdrc_blob(&s_hd_research,leaf,metadata,strlen(metadata),frame,now))goto done;
 s_hd_research_seen[s_hd_research_seen_count].texture=m->texture_hash;s_hd_research_seen[s_hd_research_seen_count++].palette=m->palette_hash;
done:free(words);free(valid);
}
static void hd_research_on_draw(const HdTextureSourceMatch *m,const HdTextureDrawQuery *q,const HdTexturePixels *px,int semi,const int *xs,const int *ys){
 uint64_t frame=s_frame_count,now;HdResearchSampleKey key;HdResearchSampleEntry *sample;char line[1536],material_fields[384];const HdSkinConfig *material;
 if(!s_hd_research.active)return;now=psx_host_mono_ms();if(!hdrc_tick(&s_hd_research,frame,now))return;
 if(!px)hd_research_source(m,q,frame,now);
 if(s_hd_research.records>=s_hd_research.limits.max_records){++s_hd_research_sampler.record_cap_skips;return;}
 key.words[0]=m->texture_hash;key.words[1]=m->palette_hash;
 key.words[2]=((((unsigned)q->u_first+q->u_last)/2u)>>7)|(((((unsigned)q->v_first+q->v_last)/2u)>>7)<<1);
 key.words[3]=(unsigned)semi;key.words[4]=px!=NULL;key.words[5]=q->depth;
 key.words[6]=q->clut_x|((uint32_t)q->clut_y<<16);key.words[7]=(uint32_t)s_hd_live_generation;key.words[8]=(uint32_t)(s_hd_live_generation>>32);
 sample=hdr_sample_prepare(&s_hd_research_sampler,&key,frame,now);if(!sample)return;
 material=hd_skin_for_draw(m->texture_hash,m->palette_hash);
 snprintf(material_fields,sizeof material_fields,",\"material_generation\":%llu,\"material_channel\":\"%s\",\"material_profile\":\"%s\",\"material_strength\":%.4f,\"material_applied\":%s,\"material_diagnostic_scope\":%s,\"material_preserve_accents\":%s",(unsigned long long)s_hd_live_generation,material==&s_hd_skin?"player":material==&s_hd_skin_enemy?"enemy":"stock",material&&material->enabled&&material->profile?material->profile->id:"stock",material?(double)material->strength:0.0,px&&material&&material->enabled&&material->profile?"true":"false",material&&material->diagnostic_scope?"true":"false",material&&material->preserve_accents?"true":"false");
 snprintf(line,sizeof line,"{\"event\":\"%s\",\"key\":\"%08X-%08X\",\"frame\":%llu,\"host_mono_ms\":%llu,\"upload_serial\":%llu,\"native_words\":[%u,%u],\"source_kind\":\"%s\",\"depth\":%u,\"semi\":%d,\"page_xy\":[%u,%u],\"source_word_xy\":[%u,%u],\"clut_xy\":[%u,%u],\"uv_bounds\":[%u,%u,%u,%u],\"xy\":[[%d,%d],[%d,%d],[%d,%d]],\"replacement_size\":[%u,%u],\"gpu_dirty\":%u,\"pending_cpu_upload_rects\":%u,\"pack_dirty\":%u,\"cpu_authority_dual\":%u,\"cpu_vram_may_be_stale\":true,\"not_visibility_proof\":true%s}",px?"replacement_gl_draw_submitted":"source_draw_query_matched",m->texture_hash,m->palette_hash,(unsigned long long)frame,(unsigned long long)now,(unsigned long long)m->upload_serial,m->upload_width_words,m->upload_height,m->exact_region?"exact_region":m->upload_serial?"upload":"native_page",q->depth,semi,q->page_x,q->page_y,m->source_word_x,m->source_y,q->clut_x,q->clut_y,q->u_first,q->v_first,q->u_last,q->v_last,xs[0],ys[0],xs[1],ys[1],xs[2],ys[2],px?px->width:0,px?px->height:0,s_gpu_dirty,s_up_nrects,s_pack_dirty.set,s_cpu_auth_dual,material_fields);
 if(!hd_research_evidence_room(strlen(line)+1,0)){++s_hd_research_sampler.budget_skips;return;}
 if(hdrc_json(&s_hd_research,line,frame,now))hdr_sample_commit(&s_hd_research_sampler,sample,frame);
}
#endif
