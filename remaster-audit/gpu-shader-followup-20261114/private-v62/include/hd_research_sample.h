#ifndef PSXRECOMP_HD_RESEARCH_SAMPLE_H
#define PSXRECOMP_HD_RESEARCH_SAMPLE_H
#include <stdint.h>
#include <string.h>
#define HDR_SAMPLE_SLOTS 512u
#define HDR_SAMPLE_KEY_WORDS 9u
typedef struct {uint32_t words[HDR_SAMPLE_KEY_WORDS];} HdResearchSampleKey;
typedef struct {HdResearchSampleKey key;uint64_t seen,frame;int emitted;} HdResearchSampleEntry;
typedef struct {
 HdResearchSampleEntry entries[HDR_SAMPLE_SLOTS];unsigned count,burst;
 uint64_t stamp,token_ms,evictions,repeat_skips,rate_skips,budget_skips,record_cap_skips,rows;
 double tokens,rate;
} HdResearchSampler;
static void hdr_sample_start(HdResearchSampler *s,unsigned records,unsigned events,unsigned seconds,uint64_t now){
 unsigned quota=records>events+1?records-events-1:0;
 memset(s,0,sizeof(*s));s->rate=seconds?(double)quota/seconds:0;
 if(s->rate>128.0)s->rate=128.0;
 s->burst=quota<32?quota:32;s->tokens=s->burst;s->token_ms=now;
}
/* Exact bounded identity comparison, not a hash: collisions cannot hide a
 * different source/material phase. LRU replacement never freezes discovery
 * when the512 slots fill. Repeat suppression is per coarse UV quadrant. */
static HdResearchSampleEntry *hdr_sample_prepare(HdResearchSampler *s,const HdResearchSampleKey *key,uint64_t frame,uint64_t now){
 unsigned i,slot=0;HdResearchSampleEntry *e;
 if(now>s->token_ms){s->tokens+=(double)(now-s->token_ms)*s->rate/1000.0;if(s->tokens>s->burst)s->tokens=s->burst;s->token_ms=now;}
 for(i=0;i<s->count;++i)if(!memcmp(&s->entries[i].key,key,sizeof(*key)))break;
 if(i==s->count){
  if(s->count<HDR_SAMPLE_SLOTS)i=s->count++;
  else{for(unsigned j=1;j<HDR_SAMPLE_SLOTS;++j)if(s->entries[j].seen<s->entries[slot].seen)slot=j;i=slot;++s->evictions;}
  memset(&s->entries[i],0,sizeof s->entries[i]);s->entries[i].key=*key;
 }
 e=&s->entries[i];e->seen=++s->stamp;
 if(e->emitted && frame>=e->frame && frame-e->frame<60){++s->repeat_skips;return NULL;}
 if(s->tokens<1.0){++s->rate_skips;return NULL;}
 return e;
}
/* A row consumes quota only after the evidence sink commits it. Failed or
 * budget-blocked writes do not suppress a later actual GL submission. */
static void hdr_sample_commit(HdResearchSampler *s,HdResearchSampleEntry *e,uint64_t frame){
 e->frame=frame;e->emitted=1;s->tokens-=1.0;++s->rows;
}
#endif
