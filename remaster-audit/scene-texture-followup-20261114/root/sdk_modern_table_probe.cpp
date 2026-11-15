#include <windows.h>
#include "sdk-release-header/remix_c.h"
#include <cstdio>
int main() {
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
  SetDllDirectoryW(L"C:\\github\\Einhander\\remaster-audit\\runtime-review\\gpu-texture-remix-20261114\\sdk-v016-release\\win64");
  remixapi_Interface api{};HMODULE dll=nullptr;
  const auto rc=remixapi_lib_loadRemixDllAndInitialize(L"C:\\github\\Einhander\\remaster-audit\\runtime-review\\gpu-texture-remix-20261114\\sdk-v016-release\\win64\\d3d9.dll",&api,&dll);
  std::printf("{\"version\":[%u,%u,%u],\"rc\":%d,\"interface_bytes\":%zu,\"startup\":%s,\"submit\":%s,\"interop_info\":%s,\"memory_texture\":%s,\"startup_called\":false,\"submit_called\":false,\"game_loaded\":false}\n",REMIXAPI_VERSION_MAJOR,REMIXAPI_VERSION_MINOR,REMIXAPI_VERSION_PATCH,int(rc),sizeof(api),api.Startup?"true":"false",api.Submit?"true":"false",api.dxvk_GetInteropInfo?"true":"false",api.CreateTextureFromMemory?"true":"false");
  std::fflush(stdout);if(dll)FreeLibrary(dll);return int(rc);
}
