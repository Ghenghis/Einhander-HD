// Exercise the actual runtime and GL backend in a hidden window. Retain the
// runtime's exported host symbols, but replace only its application entry point.
#define main einhander_unused_runtime_main
#include "../windows-x64/psxrecomp/runtime/src/main.cpp"
#undef main

extern "C" uint16_t* gpu_get_vram_ptr(void);
extern "C" int gl_renderer_vram_diff(uint32_t*, int[4], int[8][2], uint16_t[8][2]);
extern "C" uint32_t gpu_get_opcode_count(uint8_t);

static int qa_failures = 0;
static int qa_checks = 0;

static void qa_upload(int x, int y, int width, int height,
                      const std::vector<uint16_t>& pixels) {
    gpu_write_gp0(0xA0000000);
    gpu_write_gp0((uint32_t)y << 16 | (uint32_t)x);
    gpu_write_gp0((uint32_t)height << 16 | (uint32_t)width);
    for (size_t i = 0; i < pixels.size(); i += 2)
        gpu_write_gp0(pixels[i] | (i + 1 < pixels.size() ? (uint32_t)pixels[i + 1] << 16 : 0));
}

static void qa_check(const char* name, int x, int y, int width, int height,
                     const std::vector<uint16_t>& expected) {
    std::vector<uint16_t> actual((size_t)width * height);
    int read = gl_renderer_fbo_peek(x, y, width, height, actual.data());
    size_t mismatches = 0;
    for (size_t i = 0; i < actual.size(); ++i)
        if (actual[i] != expected[i]) ++mismatches;
    ++qa_checks;
    if (!read || mismatches) ++qa_failures;
    std::printf("CHECK %s read=%d mismatches=%zu/%zu", name, read, mismatches, actual.size());
    for (size_t i = 0, n = 0; i < actual.size() && n < 4; ++i) {
        if (actual[i] != expected[i]) {
            std::printf(" [%zu:%04x!=%04x]", i, actual[i], expected[i]);
            ++n;
        }
    }
    std::printf("\n");
}

static void qa_sprite(int x, int y, int width, int height) {
    gpu_write_gp0(0x65000000); // Raw 15-bit textured rectangle; page set by E1.
    gpu_write_gp0((uint32_t)y << 16 | (uint32_t)x);
    gpu_write_gp0(0);
    gpu_write_gp0((uint32_t)height << 16 | (uint32_t)width);
}

int main() {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) return 2;
    SDL_Window* window = SDL_CreateWindow("VRAM coherence regression",
        SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, 320, 240,
        SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (!window) return 3;
    gr_set_backend(GR_BACKEND_OPENGL);
    gpu_init();
    gr_set_scale(4);
    gpu_hd_texture_config(0, nullptr, nullptr);
    gl_renderer_set_cpu_auth_dual(0); // Environment selects the isolated A/B.
    if (!gl_renderer_init_context(window)) return 4;
    std::printf("MODE native_cpu_authority=%d\n", gl_renderer_cpu_auth_dual());
    gpu_write_gp0(0xE3000000);
    gpu_write_gp0(0xE407FFFF);
    gpu_write_gp0(0xE5000000);
    gpu_write_gp0(0xE6000000);

    std::vector<uint16_t> palette(256);
    for (size_t i = 0; i < palette.size(); ++i)
        palette[i] = (uint16_t)(i * 113 + 1);
    qa_upload(0, 480, 256, 1, palette);
    qa_check("palette-upload-preserves-all-bits", 0, 480, 256, 1, palette);

    std::vector<uint16_t> red(16 * 16, 0x001f), green(16 * 16, 0x03e0);
    qa_upload(768, 256, 16, 16, red);
    gpu_write_gp0(0xE100011c); // x=768, y=256, 15-bit texture.
    qa_sprite(20, 20, 16, 16);
    qa_upload(768, 256, 16, 16, green);
    qa_sprite(50, 20, 16, 16);
    qa_check("queued-draw-before-texture-update", 20, 20, 16, 16, red);
    qa_check("draw-after-texture-update", 50, 20, 16, 16, green);

    std::vector<uint16_t> patterned(32 * 8);
    for (size_t i = 0; i < patterned.size(); ++i)
        patterned[i] = (uint16_t)(0x8000 | (i * 73 & 0x7fff));
    qa_upload(800, 300, 32, 8, patterned);
    gpu_write_gp0(0x80000000);
    gpu_write_gp0(300u << 16 | 800u);
    gpu_write_gp0(320u << 16 | 848u);
    gpu_write_gp0(8u << 16 | 32u);
    qa_check("copy-preserves-index-and-mask-bits", 848, 320, 32, 8, patterned);
    qa_check("copy-leaves-source-intact", 800, 300, 32, 8, patterned);
    std::vector<uint16_t> guard_palette(16, 0x7fff);
    qa_upload(128, 492, 16, 1, guard_palette);
    uint32_t fills = gpu_get_opcode_count(0x02);
    // Captured failure shape: an early terminator-like colour is followed by
    // a negative vertex, black colour 0x02000000, negative vertex, terminator.
    // Losing the polyline state turns that black colour into a wrapping fill.
    const uint32_t first_segment[] = {0x5a000000, 0xffd2ffe0, 0x55555555,
        0xffd2ffe0, 0x02000000, 0xffdaffe6, 0x55555555};
    for (uint32_t word : first_segment) gpu_write_gp0(word);
    ++qa_checks;
    uint32_t unexpected_fills = gpu_get_opcode_count(0x02) - fills;
    if (unexpected_fills) ++qa_failures;
    std::printf("CHECK first-two-polyline-vertices-consumed unexpected_fills=%u\n", unexpected_fills);
    qa_check("polyline-preserves-palette", 128, 492, 16, 1, guard_palette);
    qa_upload(128, 492, 16, 1, guard_palette);
    fills = gpu_get_opcode_count(0x02);
    const uint32_t vertex_pattern[] = {0x5a000000, 0xffd2ffe0, 0x00101010,
        0xffd2ffe0, 0x00000000, 0x55555555, 0x02000000, 0xffdaffe6, 0x55555555};
    for (uint32_t word : vertex_pattern) gpu_write_gp0(word);
    ++qa_checks;
    unexpected_fills = gpu_get_opcode_count(0x02) - fills;
    if (unexpected_fills) ++qa_failures;
    std::printf("CHECK shaded-terminator-only-at-color-position unexpected_fills=%u\n", unexpected_fills);
    qa_check("vertex-pattern-preserves-palette", 128, 492, 16, 1, guard_palette);
    fills = gpu_get_opcode_count(0x02);
    const uint32_t mono_first_vertex[] = {0x48000000, 0x55555555,
        0x02000000, 0x55555555, 0x01000140};
    for (uint32_t word : mono_first_vertex) gpu_write_gp0(word);
    ++qa_checks;
    unexpected_fills = gpu_get_opcode_count(0x02) - fills;
    if (unexpected_fills) ++qa_failures;
    std::printf("CHECK mono-first-two-vertices-consumed unexpected_fills=%u\n", unexpected_fills);
    if (gl_renderer_cpu_auth_dual()) {
        // Deliberately separate the native authority from the cosmetic FBO.
        // A peek must report the GPU, then restore the native sampling mirror.
        uint16_t* native = gpu_get_vram_ptr();
        for (int y = 0; y < 16; ++y)
            for (int x = 0; x < 16; ++x)
                native[(256 + y) * 1024 + 768 + x] = 0x001f;
        qa_check("diagnostic-reads-gpu-not-native-mirror", 768, 256, 16, 16, green);
        qa_sprite(90, 20, 16, 16);
        qa_check("diagnostic-preserves-native-texture-source", 90, 20, 16, 16, red);
        uint32_t count = 0;
        int bbox[4], samples[8][2];
        uint16_t colors[8][2];
        int read = gl_renderer_vram_diff(&count, bbox, samples, colors);
        ++qa_checks;
        if (!read || count != 256) ++qa_failures;
        std::printf("CHECK diagnostic-diff-reads-gpu read=%d mismatches=%u expected=256\n", read, count);
        qa_sprite(120, 20, 16, 16);
        qa_check("diff-preserves-native-texture-source", 120, 20, 16, 16, red);
    }
    std::printf("RESULT checks=%d failures=%d\n", qa_checks, qa_failures);
    std::fflush(stdout);
    return qa_failures ? 1 : 0;
}
