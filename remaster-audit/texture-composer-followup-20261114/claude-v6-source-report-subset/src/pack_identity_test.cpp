/* pack_identity_test.cpp - host test of the PRIVATE v6 pack copy (make_pack_patch.py) through its PUBLIC API
 * (claude-einhander). Real PNGs in a temporary pack directory, the real decode worker thread, real leases.
 *   pack_identity_test MODE PACK_DIR EXPECTED_TSV
 *   MODE on : caller sets PSXRECOMP_HD_DECODE_IDENTITY=1  -> identity == expected HDCM-X4 (computed independently by the
 *             offline tool over the same stb decode), guards, lease lifetime across eviction, re-decode
 *   MODE off: env unset / not "1" -> every identity UNAVAILABLE, pixels unchanged
 * EXPECTED_TSV lines: KEY X4HEX CUT WIDTH HEIGHT. Test-harness output only. */
#include "hd_texture_pack.h"
#include "hd_texture_identity.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

static int g_fail = 0, g_checks = 0;
#define CHECK(c) do { ++g_checks; if (!(c)) { std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); ++g_fail; } } while (0)

struct Exp { uint32_t th, ph; uint64_t x4; int cut; uint32_t w, h; };

static int wait_ready(HdTexturePack* p, uint32_t th, uint32_t ph) {
    for (int i = 0; i < 6000; i++) {                       /* bounded: 60 s */
        const int r = hd_texture_pack_request_decode(p, th, ph);
        if (r == HD_TEXTURE_LOOKUP_FOUND) return 1;
        if (r == HD_TEXTURE_LOOKUP_ERROR) return 0;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    return 0;
}

int main(int argc, char** argv) {
    if (argc < 4) return 2;
    const bool on = std::strcmp(argv[1], "on") == 0;
    const char* env = std::getenv("PSXRECOMP_HD_DECODE_IDENTITY");
    if (on != (env && std::strcmp(env, "1") == 0)) return 3;        /* the caller set the environment wrong */
    std::vector<Exp> exp;
    std::ifstream in(argv[3]);
    std::string line;
    while (std::getline(in, line)) {
        std::istringstream s(line);
        std::string key, x4;
        Exp e{};
        if (!(s >> key >> x4 >> e.cut >> e.w >> e.h) || key.size() != 17) continue;
        e.th = (uint32_t)std::strtoul(key.substr(0, 8).c_str(), nullptr, 16);
        e.ph = (uint32_t)std::strtoul(key.substr(9, 8).c_str(), nullptr, 16);
        e.x4 = std::strtoull(x4.c_str(), nullptr, 16);
        exp.push_back(e);
    }
    CHECK(exp.size() >= 2);
    char err[256] = {0};
    HdTexturePack* pack = nullptr;
    CHECK(hd_texture_pack_create(argv[2], &pack, err, sizeof err) == 1 && pack);
    if (!pack) { std::printf("checks %d failures %d\n", g_checks, g_fail + 1); return 1; }
    hd_texture_pack_set_decode_budget(pack, (size_t)1 << 30);
    HdTexturePixels keep{};
    for (size_t i = 0; i < exp.size(); i++) {
        const Exp& e = exp[i];
        CHECK(wait_ready(pack, e.th, e.ph));
        HdTexturePixels px{};
        CHECK(hd_texture_pack_acquire_decoded(pack, e.th, e.ph, &px) == HD_TEXTURE_LOOKUP_FOUND);
        CHECK(px.rgba && px.width == e.w && px.height == e.h && px.stride == e.w * 4 && px.lease);
        uint64_t x4 = 0;
        int cut = -1;
        const int rc = hd_texture_pixels_identity(&px, &x4, &cut);
        if (on) {
            CHECK(rc == HD_TEXTURE_IDENTITY_OK && x4 == e.x4 && cut == e.cut);
            std::printf("IDENTITY %08X-%08X %016llx cut %d %ux%u\n", e.th, e.ph, (unsigned long long)x4, cut, px.width, px.height);
            HdTexturePixels q = px; q.width ^= 1u;                 /* guards: the caller's view must match the image */
            CHECK(hd_texture_pixels_identity(&q, &x4, &cut) == HD_TEXTURE_IDENTITY_MISMATCH);
            q = px; q.height += 1u;
            CHECK(hd_texture_pixels_identity(&q, &x4, &cut) == HD_TEXTURE_IDENTITY_MISMATCH);
            q = px; q.stride += 4u;
            CHECK(hd_texture_pixels_identity(&q, &x4, &cut) == HD_TEXTURE_IDENTITY_MISMATCH);
            q = px; q.rgba += 4;
            CHECK(hd_texture_pixels_identity(&q, &x4, &cut) == HD_TEXTURE_IDENTITY_MISMATCH);
            q = px; q.lease = nullptr;
            CHECK(hd_texture_pixels_identity(&q, &x4, &cut) == HD_TEXTURE_IDENTITY_NO_LEASE);
            CHECK(hd_texture_pixels_identity(nullptr, &x4, &cut) == HD_TEXTURE_IDENTITY_NO_LEASE);
            uint64_t only = 0;                                      /* null outputs are allowed */
            CHECK(hd_texture_pixels_identity(&px, &only, nullptr) == HD_TEXTURE_IDENTITY_OK && only == e.x4);
        } else {
            CHECK(rc == HD_TEXTURE_IDENTITY_UNAVAILABLE && x4 == 0 && cut == -1);
        }
        if (i == 0) keep = px;
        else hd_texture_pixels_release(&px);
    }
    if (on) {
        /* lifetime: evict every Ready image while a lease is held; the leased image and its identity stay valid */
        const Exp& e0 = exp[0];
        std::vector<uint8_t> copy(keep.rgba, keep.rgba + (size_t)keep.stride * keep.height);
        hd_texture_pack_set_decode_budget(pack, 0);
        uint64_t x4 = 0;
        int cut = -1;
        CHECK(hd_texture_pixels_identity(&keep, &x4, &cut) == HD_TEXTURE_IDENTITY_OK && x4 == e0.x4 && cut == e0.cut);
        CHECK(std::memcmp(copy.data(), keep.rgba, copy.size()) == 0);
        CHECK(hd_texture_pack_request_decode(pack, e0.th, e0.ph) == HD_TEXTURE_LOOKUP_ERROR);   /* budget 0 */
        hd_texture_pack_set_decode_budget(pack, (size_t)1 << 30);
        CHECK(wait_ready(pack, e0.th, e0.ph));                      /* re-decode: a NEW image object */
        HdTexturePixels again{};
        CHECK(hd_texture_pack_acquire_decoded(pack, e0.th, e0.ph, &again) == HD_TEXTURE_LOOKUP_FOUND);
        CHECK(again.rgba != keep.rgba);                             /* both alive: a different allocation */
        CHECK(hd_texture_pixels_identity(&again, &x4, &cut) == HD_TEXTURE_IDENTITY_OK && x4 == e0.x4 && cut == e0.cut);
        CHECK(std::memcmp(copy.data(), again.rgba, copy.size()) == 0);
        HdTexturePixels cross = again; cross.rgba = keep.rgba;      /* a lease with another image's pixels */
        CHECK(hd_texture_pixels_identity(&cross, &x4, &cut) == HD_TEXTURE_IDENTITY_MISMATCH);
        hd_texture_pixels_release(&again);
        CHECK(again.lease == nullptr && hd_texture_pixels_identity(&again, &x4, &cut) == HD_TEXTURE_IDENTITY_NO_LEASE);
    }
    hd_texture_pixels_release(&keep);
    hd_texture_pack_destroy(pack);
    std::printf("checks %d failures %d\n", g_checks, g_fail);
    return g_fail ? 1 : 0;
}
