// Read-only asset probe using the project's actual HD loader and a hidden GL context.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <GL/gl.h>
#include <chrono>
#include <cstdio>
#include <thread>
#include "hd_texture_pack.h"
#define STB_IMAGE_IMPLEMENTATION
#include "C:/github/Einhander/windows-x64/psxrecomp/runtime/third_party/stb_image.h"

int main(int argc, char** argv) {
    if (argc != 5) return 2;
    WNDCLASSA cls{};
    cls.style = CS_OWNDC;
    cls.lpfnWndProc = DefWindowProcA;
    cls.hInstance = GetModuleHandleA(nullptr);
    cls.lpszClassName = "EinhanderTextureCapabilityProbe";
    if (!RegisterClassA(&cls)) return 3;
    HWND window = CreateWindowA(cls.lpszClassName, "Texture capability probe", WS_POPUP,
                                0, 0, 1, 1, nullptr, nullptr, cls.hInstance, nullptr);
    HDC dc = GetDC(window);
    PIXELFORMATDESCRIPTOR pfd{};
    pfd.nSize = sizeof(pfd);
    pfd.nVersion = 1;
    pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL;
    pfd.iPixelType = PFD_TYPE_RGBA;
    pfd.cColorBits = 32;
    const int format = ChoosePixelFormat(dc, &pfd);
    if (!format || !SetPixelFormat(dc, format, &pfd)) return 4;
    HGLRC context = wglCreateContext(dc);
    if (!context || !wglMakeCurrent(dc, context)) return 5;
    GLint limit = 0;
    glGetIntegerv(GL_MAX_TEXTURE_SIZE, &limit);
    std::printf("GPU: %s\nOpenGL: %s\nGL_MAX_TEXTURE_SIZE: %d\n",
                glGetString(GL_RENDERER), glGetString(GL_VERSION), limit);
    int failures = 0;
    for (int i = 1; i < argc; ++i) {
        HdTexturePack* pack = nullptr;
        char error[256]{};
        if (!hd_texture_pack_create(argv[i], &pack, error, sizeof(error))) {
            std::printf("FAIL pack %s: %s\n", argv[i], error);
            ++failures;
            continue;
        }
        // Same 256-MiB budget as gpu_gl_renderer.c's live HD path.
        hd_texture_pack_set_decode_budget(pack, size_t{256} * 1024 * 1024);
        HdTexturePixels pixels{};
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
        while (std::chrono::steady_clock::now() < deadline) {
            const int state = hd_texture_pack_request_decode(pack, 0x5CC44E5F, 0x053D9A00);
            if (state < 0) break;
            if (hd_texture_pack_acquire_decoded(pack, 0x5CC44E5F, 0x053D9A00, &pixels) == HD_TEXTURE_LOOKUP_FOUND) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        if (!pixels.rgba) {
            std::printf("FAIL decode %s\n", argv[i]);
            ++failures;
            hd_texture_pack_destroy(pack);
            continue;
        }
        GLuint texture = 0;
        glGenTextures(1, &texture);
        glBindTexture(GL_TEXTURE_2D, texture);
        while (glGetError() != GL_NO_ERROR) {}
        glTexImage2D(GL_TEXTURE_2D, 0, 0x8058 /* GL_RGBA8 */, pixels.width,
                     pixels.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels.rgba);
        glFinish();
        const GLenum gl_error = glGetError();
        std::printf("%s loader+GL upload: %ux%u, %llu bytes RGBA8, GL error %u, %s\n",
                    gl_error == GL_NO_ERROR ? "PASS" : "FAIL", pixels.width, pixels.height,
                    static_cast<unsigned long long>(pixels.width) * pixels.height * 4,
                    gl_error, argv[i]);
        if (gl_error != GL_NO_ERROR) ++failures;
        glDeleteTextures(1, &texture);
        hd_texture_pixels_release(&pixels);
        hd_texture_pack_destroy(pack);
    }
    wglMakeCurrent(nullptr, nullptr);
    wglDeleteContext(context);
    ReleaseDC(window, dc);
    DestroyWindow(window);
    UnregisterClassA(cls.lpszClassName, cls.hInstance);
    std::printf("Scope: loader and actual GPU texture allocation/upload only; not gameplay, UV matching, or frame-time QA.\n");
    return failures ? 1 : 0;
}
