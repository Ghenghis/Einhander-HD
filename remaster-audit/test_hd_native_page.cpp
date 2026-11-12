#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <vector>
static unsigned hash_calls;
static uint32_t hd_texture_crc32_words_le(const uint16_t *words,size_t n) {
    ++hash_calls;
    uint32_t crc=~0u;
    for(size_t i=0;i<n;++i) for(int b=0;b<2;++b) {
        crc^=(words[i]>>(b*8))&255;
        for(int bit=0;bit<8;++bit) crc=(crc>>1)^((crc&1)?0xEDB88320u:0);
    }
    return ~crc;
}
#include "hd_native_page.h"
int main() {
    HdNativePageCache cache={};
    std::vector<uint16_t> vram(1024*512);
    for(size_t i=0;i<vram.size();++i)vram[i]=(uint16_t)(i*71+i/1024);
    unsigned checks=0;
    for(int depth=0;depth<3;++depth)for(int y:{0,256})for(int x:{320,768,960}) {
        uint32_t a=hd_page_hash(&cache,vram.data(),x,y,depth);
        unsigned before=hash_calls;
        assert(hd_page_hash(&cache,vram.data(),x,y,depth)==a && hash_calls==before); ++checks;
        const int w=64<<depth;
        const int mx=(x+w-1)&1023, my=y+127;
        vram[my*1024+mx]^=0x9241;
        hd_page_changed(&cache,mx,my,1,1,0);
        uint32_t b=hd_page_hash(&cache,vram.data(),x,y,depth);
        assert(b!=a && hash_calls==before+1); ++checks;
        before=hash_calls;
        hd_page_changed(&cache,640,256-y,64,8,0);
        assert(hd_page_hash(&cache,vram.data(),x,y,depth)==b && hash_calls==before); ++checks;
    }
    assert(hd_page_tiles(1023,511,2,2)==0x80018001u); ++checks;
    hd_page_changed(&cache,1008,7,256,1,1);
    assert(hd_page_needs_cpu(&cache,0,7,256,1)); ++checks;
    assert(!hd_page_needs_cpu(&cache,0,8,256,1)); ++checks;
    hd_page_changed(&cache,0,256,320,216,1);
    assert(!hd_page_needs_cpu(&cache,0,480,256,1)); ++checks;
    assert(hd_page_needs_cpu(&cache,0,471,256,1)); ++checks;
    assert(!hd_page_needs_cpu(&cache,320,256,64,256)); ++checks;
    hd_page_changed(&cache,0,0,1024,512,1);
    for(int row=0;row<512;++row)assert(cache.cpu_dirty_rows[row]==0xffffu);
    ++checks;
    for(int width:{64,128,192}){
        const int x=1024-width;
        assert(hd_page_admission_width(x,2,0,width-1,0)==width);++checks;
        assert(hd_page_admission_width(x,2,0,width,0)==0);++checks;
        assert(hd_page_admission_width(x,2,250,2,0)==0);++checks;
        assert(hd_page_admission_width(x,2,0,width-1,1)==0);++checks;
        std::vector<uint16_t> cropped(width*256);
        for(int row=0;row<256;++row)for(int col=0;col<width;++col)cropped[row*width+col]=vram[(256+row)*1024+x+col];
        uint32_t expected=hd_texture_crc32_words_le(cropped.data(),cropped.size());
        uint32_t actual=hd_page_hash_width(&cache,vram.data(),x,256,2,width);
        assert(actual==expected);++checks;
        unsigned before=hash_calls;
        assert(hd_page_hash_width(&cache,vram.data(),x,256,2,width)==actual && hash_calls==before);++checks;
        // The wrapped framebuffer is not part of this clipped identity.
        vram[300*1024]^=0x6318;hd_page_changed(&cache,0,300,1,1,0);
        assert(hd_page_hash_width(&cache,vram.data(),x,256,2,width)==actual && hash_calls==before);++checks;
        vram[300*1024+x]^=0x4210;hd_page_changed(&cache,x,300,1,1,0);
        uint32_t changed=hd_page_hash_width(&cache,vram.data(),x,256,2,width);
        assert(changed!=actual && hash_calls==before+1);++checks;
        uint32_t full=hd_page_hash(&cache,vram.data(),x,256,2);
        assert(full!=changed);++checks;
        before=hash_calls;
        assert(hd_page_hash_width(&cache,vram.data(),x,256,2,width)==changed && hash_calls==before+1);++checks;
    }
    assert(hd_page_admission_width(704,2,0,255,0)==256);++checks;
    assert(hd_page_admission_width(704,2,250,2,0)==256);++checks;
    assert(hd_page_admission_width(0,2,0,63,0)==0);++checks;
    assert(hd_page_admission_width(256,2,0,63,0)==0);++checks;
    assert(hd_page_admission_width(960,1,0,127,0)==64);++checks;
    assert(hd_page_admission_width(960,1,0,128,0)==0);++checks;
    assert(hd_page_admission_width(960,0,0,255,0)==64);++checks;
    assert(hd_page_admission_width(959,2,0,63,0)==0);++checks;
    assert(hd_page_admission_width(1024,2,0,63,0)==0);++checks;
    std::printf("{\"checks\":%u,\"failures\":0,\"crc_recomputations\":%u}\n",checks,hash_calls);
}
