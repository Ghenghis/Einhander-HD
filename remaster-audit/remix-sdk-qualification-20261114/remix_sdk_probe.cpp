// Private ABI qualification only. Never starts a renderer or presents a frame.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define REMIX_WINAPI_NO_LIBRARY_LOADER
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <cstddef>
#include "remix-sdk-reference/remix_c.h"

static_assert(sizeof(void*) == 8, "Remix ray tracing ABI requires x64");
static_assert(offsetof(remixapi_Interface, Shutdown) == 0, "Unexpected ABI prefix");
static_assert(sizeof(remixapi_HardcodedVertex) == 64, "Unexpected mesh vertex ABI");

int main(int argc, char** argv) {
    SetPriorityClass(GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS);
    const bool initialize = argc == 2 && std::strcmp(argv[1], "--initialize") == 0;
    if (argc > 1 && !initialize) return 2;
    std::printf("{\"header_version\":[%d,%d,%d],\"interface_bytes\":%zu,\"vertex_bytes\":%zu,\"startup_bytes\":%zu,\"startup_offset\":%zu,\"gpu_startup_called\":false,\"initialize_requested\":%s",
        REMIXAPI_VERSION_MAJOR, REMIXAPI_VERSION_MINOR, REMIXAPI_VERSION_PATCH,
        sizeof(remixapi_Interface), sizeof(remixapi_HardcodedVertex), sizeof(remixapi_StartupInfo),
        offsetof(remixapi_Interface, Startup), initialize ? "true" : "false");
    if (!initialize) { std::puts("}"); return 0; }
    // Explicit vendor installation. No current-directory/PATH shim search or game injection.
    const wchar_t* path = L"C:\\Program Files\\NVIDIA Corporation\\RTX Remix\\deps\\remix_runtime\\runtime\\.trex\\d3d9.dll";
    HMODULE module = LoadLibraryExW(path, nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!module) { std::printf(",\"load_error\":%lu}\n", GetLastError()); return 3; }
    auto initialize_library = reinterpret_cast<PFN_remixapi_InitializeLibrary>(
        GetProcAddress(module, "remixapi_InitializeLibrary"));
    if (!initialize_library) {
        std::printf(",\"symbol_error\":%lu}\n", GetLastError()); FreeLibrary(module); return 4;
    }
    remixapi_InitializeLibraryInfo info{};
    info.sType = REMIXAPI_STRUCT_TYPE_INITIALIZE_LIBRARY_INFO;
    info.version = REMIXAPI_VERSION_MAKE(REMIXAPI_VERSION_MAJOR, REMIXAPI_VERSION_MINOR, REMIXAPI_VERSION_PATCH);
    remixapi_Interface api{}; // Older compatible runtimes can leave later fields null.
    const auto result = initialize_library(&info, &api);
    const bool required = result == REMIXAPI_ERROR_CODE_SUCCESS && api.Startup && api.Shutdown &&
        api.Present && api.SetupCamera && api.CreateMesh && api.DestroyMesh && api.DrawInstance &&
        api.CreateMaterial && api.DestroyMaterial && api.CreateLight && api.DrawLightInstance;
    std::printf(",\"initialize_result\":%d,\"required_scene_api_present\":%s,\"external_swapchain_api_present\":%s,\"rendered_gameplay\":false}\n",
        static_cast<int>(result), required ? "true" : "false", api.dxvk_GetExternalSwapchain ? "true" : "false");
    FreeLibrary(module);
    return required ? 0 : 5;
}
