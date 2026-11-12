/* Bounded native texture-page identity cache. Renderer-thread only.
 * Requires hd_texture_crc32_words_le from hd_texture_pack.h. */
#ifndef PSXRECOMP_HD_NATIVE_PAGE_H
#define PSXRECOMP_HD_NATIVE_PAGE_H
#include <stdint.h>
#include <string.h>
typedef struct {
    uint64_t generation[32];
    uint16_t cpu_dirty_rows[512]; /* exact rows, 64-word column tiles */
    struct { uint64_t generation[4]; uint32_t hash; int valid, width_words; } page[3][32];
} HdNativePageCache;

/* Keep framebuffer/render-to-texture and texture-window queries native. A
 * physical right-edge page may admit only the part before VRAM wraps, provided
 * the complete primitive UV interval remains inside that part. Ordinary full
 * pages retain their existing wrapping-UV behavior and identity. */
static int hd_page_admission_width(int x,int depth,int u_first,int u_last,int texture_windowed) {
    int nominal,physical,ppw;
    if(x<320 || x>=1024 || (x&63) || depth<0 || depth>2 || texture_windowed ||
       u_first<0 || u_first>255 || u_last<0 || u_last>255)return 0;
    nominal=64<<depth;physical=1024-x;
    if(nominal<=physical)return nominal;
    ppw=4>>depth;
    if(u_first>u_last || u_last/ppw>=physical)return 0;
    return physical;
}

static uint32_t hd_page_tiles(int x, int y, int w, int h) {
    uint32_t bits = 0;
    if (w <= 0 || h <= 0) return 0;
    if (w > 1024) w = 1024;
    if (h > 512) h = 512;
    /* Walk tile-boundary segments, including native VRAM wrap. */
    for (int ry = 0; ry < h;) {
        int py = (y + ry) & 511;
        for (int rx = 0; rx < w;) {
            int px = (x + rx) & 1023;
            bits |= UINT32_C(1) << ((py / 256) * 16 + px / 64);
            rx += 64 - (px & 63);
        }
        ry += 256 - (py & 255);
    }
    return bits;
}

static void hd_page_mark_gpu_dirty(HdNativePageCache *cache,int x,int y,int w,int h) {
    const uint32_t bits=hd_page_tiles(x,0,w,1);
    if(h>512)h=512;
    for(int row=0;row<h;++row)cache->cpu_dirty_rows[(y+row)&511]|=(uint16_t)bits;
}

static int hd_page_needs_cpu(const HdNativePageCache *cache,int x,int y,int w,int h) {
    const uint16_t columns=(uint16_t)hd_page_tiles(x,0,w,1);
    if(h>512)h=512;
    for(int row=0;row<h;++row)
        if(cache->cpu_dirty_rows[(y+row)&511]&columns)return 1;
    return 0;
}

static void hd_page_changed(HdNativePageCache *cache, int x, int y, int w, int h,
                            int gpu_write) {
    uint32_t bits = hd_page_tiles(x,y,w,h);
    for (int i = 0; i < 32; ++i)
        if (bits & (UINT32_C(1) << i)) ++cache->generation[i];
    if (gpu_write) hd_page_mark_gpu_dirty(cache,x,y,w,h);
}

static uint32_t hd_page_hash_width(HdNativePageCache *cache, const uint16_t *vram,
                             int x, int y, int depth,int width) {
    if(depth<0 || depth>2 || width<64 || width>256 || (width&63))return 0;
    const int columns = width/64;
    const int first = ((y & 511) / 256) * 16 + ((x & 1023) / 64);
    int hit = cache->page[depth][first].valid && cache->page[depth][first].width_words==width;
    for (int i = 0; i < columns; ++i) {
        const int tile = (first & 16) | ((first + i) & 15);
        if (cache->page[depth][first].generation[i] != cache->generation[tile]) hit = 0;
    }
    if (!hit) {
        uint16_t words[256 * 256];
        for (int row = 0; row < 256; ++row)
            for (int col = 0; col < width; ++col)
                words[row * width + col] = vram[((y+row)&511)*1024+((x+col)&1023)];
        cache->page[depth][first].hash = hd_texture_crc32_words_le(words,(size_t)width*256);
        for (int i = 0; i < columns; ++i) {
            const int tile = (first & 16) | ((first + i) & 15);
            cache->page[depth][first].generation[i] = cache->generation[tile];
        }
        cache->page[depth][first].valid = 1;
        cache->page[depth][first].width_words = width;
    }
    return cache->page[depth][first].hash;
}

static uint32_t hd_page_hash(HdNativePageCache *cache, const uint16_t *vram,
                             int x, int y, int depth) {
    return hd_page_hash_width(cache,vram,x,y,depth,64<<depth);
}
#endif
