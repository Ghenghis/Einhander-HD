/* Focused tests for the HD texture-pack source-match and surviving-upload-
 * fragment APIs plus the async decode cache. Standalone — no test framework:
 * compile with hd_texture_pack.cpp and run; non-zero exit = failures. */
#include "hd_texture_pack.h"

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <chrono>
#include <filesystem>
#include <thread>
#include <vector>

#include "../src/png_write.h"

#define STB_IMAGE_IMPLEMENTATION
#include "../third_party/stb_image.h"

namespace fs = std::filesystem;

static int s_failures = 0;
static int s_checks = 0;
#define CHECK(cond, msg) do { \
    ++s_checks; \
    if (!(cond)) { std::printf("FAIL line %d: %s\n", __LINE__, msg); ++s_failures; } \
} while (0)

static constexpr int kVramW = 1024;
static constexpr int kVramH = 512;
static uint16_t s_vram[kVramW * kVramH];

/* Copy row-major logical upload words into the fake VRAM mirror (no wrap). */
static void vram_write_upload(int x, int y, int w, int h, const uint16_t* words) {
    for (int r = 0; r < h; ++r)
        for (int c = 0; c < w; ++c)
            s_vram[(y + r) * kVramW + (x + c)] = words[r * w + c];
}

static HdTextureDrawQuery make_query(int page_x, int page_y, int depth,
                                   int u0, int u1, int v0, int v1) {
    HdTextureDrawQuery q{};
    q.page_x = (uint16_t)page_x;
    q.page_y = (uint16_t)page_y;
    q.depth = (uint8_t)depth;
    q.u_first = (uint8_t)u0;
    q.u_last = (uint8_t)u1;
    q.v_first = (uint8_t)v0;
    q.v_last = (uint8_t)v1;
    q.vram = s_vram;
    q.vram_word_count = (size_t)kVramW * kVramH;
    return q;
}

int main() {
    std::memset(s_vram, 0, sizeof s_vram);

    /* ---- pack root: Hashes.ini + exactly one *-texture-replacements dir -- */
    fs::path root = fs::temp_directory_path() /
        ("hd_pack_test_" + std::to_string((unsigned long long)
            std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::path repl = root / "unit-texture-replacements";
    fs::create_directories(repl);
    {
        FILE* ini = fopen((root / "Hashes.ini").string().c_str(), "wb");
        fputs("# test\n", ini);
        fclose(ini);
    }

    /* ---- tracked upload: 64x64 words at (100,50) ------------------------ */
    std::vector<uint16_t> words(64 * 64);
    for (size_t i = 0; i < words.size(); ++i)
        words[i] = (uint16_t)(0x8000 | (i & 0x7FFF));
    const uint32_t expect_hash =
        hd_texture_crc32_words_le(words.data(), words.size());
    CHECK(expect_hash != 0, "crc32 of upload words");

    /* replacement PNG for the decode-path test, named <th>-<ph>.png */
    {
        std::vector<uint8_t> rgb(64 * 64 * 3);
        for (int y = 0; y < 64; ++y)
            for (int x = 0; x < 64; ++x) {
                rgb[(y * 64 + x) * 3 + 0] = (uint8_t)(x * 4);
                rgb[(y * 64 + x) * 3 + 1] = (uint8_t)(y * 4);
                rgb[(y * 64 + x) * 3 + 2] = 0x55;
            }
        char name[64];
        std::snprintf(name, sizeof name, "%08X-%08X.png", expect_hash, 0u);
        FILE* f = fopen((repl / name).string().c_str(), "wb");
        CHECK(f != nullptr, "open replacement png for write");
        CHECK(png_write_rgb(f, rgb.data(), 64, 64) == 1, "png_write_rgb");
        fclose(f);
    }

    HdTexturePack* pack = nullptr;
    char err[256] = {0};
    CHECK(hd_texture_pack_create(root.string().c_str(), &pack, err, sizeof err)
              == 1 && pack,
          "hd_texture_pack_create");
    if (!pack) { std::printf("create error: %s\n", err); return 1; }

    HdTexturePackInfo info{};
    hd_texture_pack_get_info(pack, &info);
    CHECK(info.replacement_file_count == 1, "replacement_file_count == 1");

    HdTexturePackEntry ent{};
    CHECK(hd_texture_pack_lookup(pack, expect_hash, 0, &ent)
              == HD_TEXTURE_LOOKUP_FOUND && ent.replacement_path != nullptr,
          "lookup finds replacement entry");

    uint32_t tracked_hash = 0;
    CHECK(hd_texture_pack_track_upload(pack, 100, 50, 64, 64,
                                       words.data(), words.size(),
                                       &tracked_hash) == 1,
          "track_upload");
    CHECK(tracked_hash == expect_hash,
          "track_upload hash == crc32_words_le");
    vram_write_upload(100, 50, 64, 64, words.data());

    /* ---- match_source: whole-upload query ------------------------------ */
    HdTextureSourceMatch m{};
    HdTextureDrawQuery q = make_query(100, 50, 2, 0, 63, 0, 63);
    CHECK(hd_texture_pack_match_source(pack, &q, &m)
              == HD_TEXTURE_LOOKUP_FOUND,
          "match_source FOUND on covering upload");
    CHECK(m.upload_serial != 0, "match serial non-zero");
    CHECK(m.texture_hash == expect_hash && m.palette_hash == 0,
          "match texture/palette hashes");
    CHECK(m.upload_width_words == 64 && m.upload_height == 64,
          "match upload dims");
    CHECK(m.source_word_x == 0 && m.source_y == 0,
          "match source offset at upload origin");
    const uint64_t upload_serial = m.upload_serial;

    /* ---- fragments: one contiguous rect before invalidation ------------ */
    HdTextureUploadFragment fr[8];
    size_t nfr = 0;
    CHECK(hd_texture_pack_upload_fragments(pack, upload_serial,
                                           fr, 8, &nfr)
              == HD_TEXTURE_LOOKUP_FOUND && nfr == 1,
          "upload_fragments single rect");
    CHECK(fr[0].x == 100 && fr[0].y == 50 &&
          fr[0].width == 64 && fr[0].height == 64 &&
          fr[0].source_x == 0 && fr[0].source_y == 0,
          "fragment 0 coords/source");
    CHECK(hd_texture_pack_upload_fragments(pack, 0xDEADBEEFull,
                                           fr, 8, &nfr)
              == HD_TEXTURE_LOOKUP_NONE,
          "upload_fragments bad serial -> NONE");
    CHECK(hd_texture_pack_upload_fragments(pack, upload_serial,
                                           nullptr, 0, &nfr)
              == HD_TEXTURE_LOOKUP_FOUND && nfr == 1,
          "fragments count-only call");

    /* ---- invalidate a vertical strip -> two fragments ------------------ */
    hd_texture_pack_invalidate(pack, 120, 50, 8, 64);
    CHECK(hd_texture_pack_upload_fragments(pack, upload_serial,
                                           fr, 8, &nfr)
              == HD_TEXTURE_LOOKUP_FOUND && nfr == 2,
          "invalidate splits into two fragments");
    if (nfr == 2) {
        /* Order is unspecified; identify by source_x. */
        const HdTextureUploadFragment* a = fr[0].source_x == 0 ? &fr[0] : &fr[1];
        const HdTextureUploadFragment* b = a == &fr[0] ? &fr[1] : &fr[0];
        CHECK(a->x == 100 && a->width == 20 && a->source_x == 0,
              "left fragment {x=100,w=20,sx=0}");
        CHECK(b->x == 128 && b->width == 36 && b->source_x == 28,
              "right fragment {x=128,w=36,sx=28}");
    }

    /* match_source after split: inside one fragment -> FOUND; spanning the
     * hole -> NONE. */
    q = make_query(100, 50, 2, 0, 19, 0, 63);
    std::memset(&m, 0, sizeof m);
    CHECK(hd_texture_pack_match_source(pack, &q, &m)
              == HD_TEXTURE_LOOKUP_FOUND && m.source_word_x == 0,
          "match inside left fragment");
    q = make_query(100, 50, 2, 28, 63, 0, 63);
    CHECK(hd_texture_pack_match_source(pack, &q, &m)
              == HD_TEXTURE_LOOKUP_FOUND && m.source_word_x == 28,
          "match inside right fragment keeps source offset");
    q = make_query(100, 50, 2, 0, 63, 0, 63);
    CHECK(hd_texture_pack_match_source(pack, &q, &m)
              == HD_TEXTURE_LOOKUP_NONE,
          "match spanning invalidated strip -> NONE");

    /* ---- tracking state save/load roundtrip ---------------------------- */
    uint8_t* state = nullptr;
    size_t state_size = 0;
    CHECK(hd_texture_pack_tracking_state_save(pack, &state, &state_size) == 1 &&
          state && state_size > 0,
          "tracking_state_save");
    CHECK(hd_texture_pack_tracking_state_check(state, state_size) == 1,
          "tracking_state_check");
    {
        HdTexturePack* pack2 = nullptr;
        CHECK(hd_texture_pack_create(root.string().c_str(), &pack2,
                                     err, sizeof err) == 1 && pack2,
              "second pack create");
        CHECK(hd_texture_pack_tracking_state_load(pack2, state, state_size)
                  == 1,
              "tracking_state_load");
        HdTextureSourceMatch m2{};
        q = make_query(100, 50, 2, 0, 19, 0, 63);
        CHECK(hd_texture_pack_match_source(pack2, &q, &m2)
                  == HD_TEXTURE_LOOKUP_FOUND &&
              m2.upload_serial == upload_serial &&
              m2.texture_hash == expect_hash,
              "restored residency still matches");
        size_t n2 = 0;
        CHECK(hd_texture_pack_upload_fragments(pack2, m2.upload_serial,
                                               nullptr, 0, &n2)
                  == HD_TEXTURE_LOOKUP_FOUND && n2 == 2,
              "restored fragments survive");
        hd_texture_pack_destroy(pack2);
    }
    free(state);

    /* ---- async decode cache -------------------------------------------- */
    hd_texture_pack_set_decode_budget(pack, 64u * 1024u * 1024u);
    const int req = hd_texture_pack_request_decode(pack, expect_hash, 0);
    CHECK(req == HD_TEXTURE_LOOKUP_FOUND ||
          req == HD_TEXTURE_LOOKUP_NONE /* queued */,
          "request_decode accepted");
    HdTexturePixels px{};
    int got = HD_TEXTURE_LOOKUP_NONE;
    for (int i = 0; i < 200 && got != HD_TEXTURE_LOOKUP_FOUND; ++i) {
        got = hd_texture_pack_acquire_decoded(pack, expect_hash, 0, &px);
        if (got != HD_TEXTURE_LOOKUP_FOUND)
            std::this_thread::sleep_for(std::chrono::milliseconds(25));
    }
    CHECK(got == HD_TEXTURE_LOOKUP_FOUND, "acquire_decoded within 5s");
    if (got == HD_TEXTURE_LOOKUP_FOUND) {
        CHECK(px.width == 64 && px.height == 64 && px.rgba != nullptr,
              "decoded dims/pixels");
        if (px.rgba) {
            const uint8_t* row0 = px.rgba;
            CHECK(row0[0] == 0 && row0[1] == 0 && row0[2] == 0x55 &&
                  row0[3] == 255,
                  "decoded pixel (0,0)");
            const uint8_t* row63 = px.rgba + (size_t)63 * px.stride + 63 * 4;
            CHECK(row63[0] == 252 && row63[1] == 252 && row63[2] == 0x55 &&
                  row63[3] == 255,
                  "decoded pixel (63,63)");
        }
        hd_texture_pixels_release(&px);
    }
    CHECK(hd_texture_pack_request_decode(pack, 0xF00DF00D, 0)
              == HD_TEXTURE_LOOKUP_ERROR,
          "request_decode absent key -> ERROR");

    hd_texture_pack_destroy(pack);

    /* ---- entry ambiguity: 1-0.png vs 00000001-0.png ---------------------- */
    {
        fs::path repl2 = root / "amb-texture-replacements";
        fs::create_directories(repl2);
        for (const char* n : {"1-0.png", "00000001-0.png"}) {
            FILE* f = fopen((repl2 / n).string().c_str(), "wb");
            uint8_t rgb[3] = {1, 2, 3};
            png_write_rgb(f, rgb, 1, 1);
            fclose(f);
        }
        /* Point the pack at the replacement dir itself; ambiguous aliases must
         * not resolve to a single entry. */
        HdTexturePack* pack3 = nullptr;
        CHECK(hd_texture_pack_create(repl2.string().c_str(), &pack3,
                                     err, sizeof err) == 1 && pack3,
              "ambiguous pack create");
        if (pack3) {
            CHECK(hd_texture_pack_lookup(pack3, 1, 0, &ent)
                      == HD_TEXTURE_LOOKUP_AMBIGUOUS,
                  "numeric alias ambiguity -> AMBIGUOUS");
            hd_texture_pack_destroy(pack3);
        }
    }

    fs::remove_all(root);
    std::printf("hd_texture_pack_test: %d checks, %d failures\n",
                s_checks, s_failures);
    return s_failures ? 1 : 0;
}
