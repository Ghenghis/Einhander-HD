/* Exact bounded source filtering. No Bloom filter, key truncation or file IO. */
#ifndef PSXRECOMP_HD_RESEARCH_FILTER_H
#define PSXRECOMP_HD_RESEARCH_FILTER_H
#include "gpu_gl_renderer.h"
#include <stdlib.h>
#include <stdio.h>
static int hdr_source_key_compare(const void *a,const void *b){
 const GlResearchSourceKey *x=(const GlResearchSourceKey*)a,*y=(const GlResearchSourceKey*)b;
 if(x->texture!=y->texture)return x->texture<y->texture?-1:1;
 return x->palette==y->palette?0:(x->palette<y->palette?-1:1);
}
static int hdr_source_filter_valid(const GlResearchLimits *limits){
 unsigned i,j;if(!limits||limits->source_policy>GL_RESEARCH_SOURCE_EXCLUDE||limits->source_key_count>GL_RESEARCH_SOURCE_KEYS_MAX)return 0;
 if((limits->source_policy==GL_RESEARCH_SOURCE_ALL)!=(limits->source_key_count==0))return 0;
 for(i=0;i<limits->source_key_count;++i)for(j=0;j<i;++j)if(!hdr_source_key_compare(&limits->source_keys[i],&limits->source_keys[j]))return 0;
 return 1;
}
static uint32_t hdr_source_filter_hash(const GlResearchLimits *limits){
 uint32_t value=2166136261u;unsigned i,j;char key[19];
 for(i=0;i<limits->source_key_count;++i){snprintf(key,sizeof key,"%08X-%08X\n",limits->source_keys[i].texture,limits->source_keys[i].palette);for(j=0;j<18;++j)value=(value^(unsigned char)key[j])*16777619u;}
 return value;
}
static int hdr_source_filter_selected(const GlResearchLimits *limits,uint32_t texture,uint32_t palette){
 GlResearchSourceKey key;int found;
 if(limits->source_policy==GL_RESEARCH_SOURCE_ALL)return 1;
 key.texture=texture;key.palette=palette;
 found=bsearch(&key,limits->source_keys,limits->source_key_count,sizeof key,hdr_source_key_compare)!=NULL;
 return limits->source_policy==GL_RESEARCH_SOURCE_INCLUDE?found:!found;
}
static const char *hdr_source_policy_name(unsigned policy){return policy==GL_RESEARCH_SOURCE_INCLUDE?"include":policy==GL_RESEARCH_SOURCE_EXCLUDE?"exclude":"all";}
#endif
