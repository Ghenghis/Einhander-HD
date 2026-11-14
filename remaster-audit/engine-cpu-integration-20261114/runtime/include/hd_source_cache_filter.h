#ifndef EIN_HD_SOURCE_CACHE_FILTER_H
#define EIN_HD_SOURCE_CACHE_FILTER_H
#include <stdint.h>
#include <string.h>

/* Optional authoring-only raw-upload CRC shortlist. An empty setting preserves
 * the existing bounded LRU. Invalid settings admit nothing, never all uploads. */
#define HD_SOURCE_CACHE_FILTER_MAX 32
typedef struct {
    unsigned count;
    int valid, filtered;
    uint32_t hashes[HD_SOURCE_CACHE_FILTER_MAX];
} HdSourceCacheFilter;

static int hd_source_cache_filter_parse(const char *text,HdSourceCacheFilter *out) {
    HdSourceCacheFilter next;memset(&next,0,sizeof next);next.valid=1;
    if(!text || !*text){*out=next;return 1;}
    next.filtered=1;
    for(;;){
        uint32_t hash=0;
        if(next.count==HD_SOURCE_CACHE_FILTER_MAX)goto invalid;
        for(unsigned i=0;i<8;++i){
            unsigned char c=(unsigned char)*text;
            unsigned value;
            if(c>='0' && c<='9')value=c-'0';
            else if(c>='a' && c<='f')value=c-'a'+10;
            else if(c>='A' && c<='F')value=c-'A'+10;
            else goto invalid;
            hash=(hash<<4)|value;++text;
        }
        next.hashes[next.count++]=hash;
        if(!*text){*out=next;return 1;}
        if(*text++!=',' || !*text)goto invalid;
    }
invalid:
    memset(out,0,sizeof *out);out->filtered=1;return 0;
}
static int hd_source_cache_filter_match(const HdSourceCacheFilter *filter,uint32_t hash) {
    if(!filter->valid)return 0;
    if(!filter->filtered)return 1;
    for(unsigned i=0;i<filter->count;++i)if(filter->hashes[i]==hash)return 1;
    return 0;
}
#endif
