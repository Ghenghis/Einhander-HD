#include <windows.h>
#include "sdk-minecraft-reference/remix_c.h"
#include <cstdio>
int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);remixapi_Interface api={};HMODULE dll=nullptr;
 auto rc=remixapi_lib_loadRemixDllAndInitialize(L"C:\\Program Files\\NVIDIA Corporation\\RTX Remix\\deps\\remix_runtime\\runtime\\.trex\\d3d9.dll",&api,&dll);
 std::printf("{\"version\":[%u,%u,%u],\"rc\":%d,\"interface_bytes\":%llu,\"startup\":%s,\"submit\":%s,\"interop_info\":%s,\"memory_texture\":%s,\"gpu_started\":false}\n",REMIXAPI_VERSION_MAJOR,REMIXAPI_VERSION_MINOR,REMIXAPI_VERSION_PATCH,int(rc),(unsigned long long)sizeof(api),api.Startup?"true":"false",api.Submit?"true":"false",api.dxvk_GetInteropInfo?"true":"false",api.CreateTextureFromMemory?"true":"false");if(dll)FreeLibrary(dll);return int(rc);}
