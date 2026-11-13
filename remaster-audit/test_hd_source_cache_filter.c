#include <stdio.h>
#include "hd_source_cache_filter.h"
static unsigned checks,failures;
#define CHECK(label,expr) do{++checks;if(!(expr)){++failures;printf("FAIL %s\n",label);}}while(0)
int main(void){
    HdSourceCacheFilter f;
    CHECK("absent preserves unfiltered cache",hd_source_cache_filter_parse(NULL,&f)&&hd_source_cache_filter_match(&f,1));
    CHECK("empty preserves unfiltered cache",hd_source_cache_filter_parse("",&f)&&hd_source_cache_filter_match(&f,0));
    CHECK("exact two-key shortlist",hd_source_cache_filter_parse("DB715733,b24c6da2",&f)&&f.count==2&&hd_source_cache_filter_match(&f,0xDB715733)&&hd_source_cache_filter_match(&f,0xB24C6DA2)&&!hd_source_cache_filter_match(&f,0xDB715732));
    const char *bad[]={"1234567","123456789","0x12345678","DB715733,",",DB715733","DB715733,,B24C6DA2","DB71573Z"," DB715733","DB715733 B24C6DA2"};
    for(unsigned i=0;i<sizeof bad/sizeof bad[0];++i)CHECK("malformed fails closed",!hd_source_cache_filter_parse(bad[i],&f)&&!hd_source_cache_filter_match(&f,0xDB715733));
    char many[33*9+1];unsigned offset=0;
    for(unsigned i=0;i<32;++i)offset+=(unsigned)sprintf(many+offset,"%s%08X",i?",":"",i);
    CHECK("32 bounded keys admitted",hd_source_cache_filter_parse(many,&f)&&f.count==32&&hd_source_cache_filter_match(&f,31));
    sprintf(many+offset,",00000020");
    CHECK("33 keys rejected atomically",!hd_source_cache_filter_parse(many,&f)&&!f.count&&!hd_source_cache_filter_match(&f,31));
    printf("RESULT checks=%u failures=%u\n",checks,failures);return failures?1:0;
}
