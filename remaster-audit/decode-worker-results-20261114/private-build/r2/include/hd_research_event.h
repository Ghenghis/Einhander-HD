#ifndef PSXRECOMP_HD_RESEARCH_EVENT_H
#define PSXRECOMP_HD_RESEARCH_EVENT_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define HD_RESEARCH_CONTRACT "ein-research-v1"
#define HDR_EVENT_HEADER 160u
#define HDR_RAM_BYTES 2097152u
#define HDR_VRAM_BYTES 1048576u
#define HDR_EVENT_BYTES (HDR_EVENT_HEADER+HDR_RAM_BYTES+HDR_VRAM_BYTES)
static void hdr_le32(uint8_t *p,uint32_t n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);p[2]=(uint8_t)(n>>16);p[3]=(uint8_t)(n>>24);}
static void hdr_le64(uint8_t *p,uint64_t n){hdr_le32(p,(uint32_t)n);hdr_le32(p+4,(uint32_t)(n>>32));}
static uint32_t hdr_fnv(const uint8_t *p,size_t n){uint32_t h=2166136261u;size_t i;for(i=0;i<n;++i)h=(h^p[i])*16777619u;return h;}
static int hdr_label_valid(const char *s){size_t n=0;if(!s)return 0;while(*s){unsigned char c=(unsigned char)*s++;if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'||c=='-')||++n>63)return 0;}return n>0;}
/* Exact on-disk format: fixed header, full RAM, then LE CPU-mirror VRAM.
 * Copying is synchronous at the owning thread's command safe point. It is
 * atomic CPU-state evidence, never a claim of GPU/framebuffer coherence. */
static int hdr_build_event(uint8_t *out,size_t capacity,const uint8_t *ram,size_t ram_bytes,
 const uint16_t *vram,size_t vram_words,const char *label,uint64_t frame,uint64_t ms,
 unsigned gpu_dirty,unsigned pending,unsigned pack_dirty,unsigned dual,unsigned renderer,unsigned index){
 size_t i,n;if(!out||capacity<HDR_EVENT_BYTES||!ram||ram_bytes!=HDR_RAM_BYTES||!vram||vram_words!=HDR_VRAM_BYTES/2||!hdr_label_valid(label))return 0;
 n=strlen(label);memset(out,0,HDR_EVENT_HEADER);memcpy(out,"EINRC01",7);
 hdr_le32(out+8,1);hdr_le32(out+12,HDR_EVENT_HEADER);hdr_le64(out+16,frame);hdr_le64(out+24,ms);
 hdr_le32(out+32,HDR_EVENT_HEADER);hdr_le32(out+36,HDR_RAM_BYTES);hdr_le32(out+40,HDR_EVENT_HEADER+HDR_RAM_BYTES);hdr_le32(out+44,HDR_VRAM_BYTES);
 hdr_le32(out+48,gpu_dirty);hdr_le32(out+52,pending);hdr_le32(out+56,pack_dirty);hdr_le32(out+60,dual);hdr_le32(out+64,renderer);
 hdr_le32(out+76,index);hdr_le32(out+80,(uint32_t)n);hdr_le32(out+84,1);memcpy(out+96,label,n);
 memcpy(out+HDR_EVENT_HEADER,ram,HDR_RAM_BYTES);
 for(i=0;i<HDR_VRAM_BYTES/2;++i){out[HDR_EVENT_HEADER+HDR_RAM_BYTES+i*2]=(uint8_t)vram[i];out[HDR_EVENT_HEADER+HDR_RAM_BYTES+i*2+1]=(uint8_t)(vram[i]>>8);}
 hdr_le32(out+68,hdr_fnv(out+HDR_EVENT_HEADER,HDR_RAM_BYTES));hdr_le32(out+72,hdr_fnv(out+HDR_EVENT_HEADER+HDR_RAM_BYTES,HDR_VRAM_BYTES));return 1;
}
#endif
