// Native-presentation control based on pinned NVIDIA remixapi_example_c.c.
// No OpenGL/context, custom material, particle system or game data.
#include <windows.h>
#include "../project-completion-20261114/remix-sdk-reference/remix_c.h"
#include <cstdio>
#include <thread>
#include <atomic>
static bool call(const char*n,remixapi_ErrorCode c){std::printf("{\"call\":\"%s\",\"result\":%d,\"tick_ms\":%llu}\n",n,int(c),(unsigned long long)GetTickCount64());std::fflush(stdout);return c==REMIXAPI_ERROR_CODE_SUCCESS;}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l){return DefWindowProcW(h,m,w,l);}
static void pump(){MSG m;while(PeekMessageW(&m,nullptr,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);}}
int main(int,char**){
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);SetPriorityClass(GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS);
 WNDCLASSW wc={};wc.hInstance=GetModuleHandleW(nullptr);wc.lpfnWndProc=proc;wc.lpszClassName=L"EinhanderRemixNativeControl";RegisterClassW(&wc);
 RECT rect={0,0,640,360};AdjustWindowRect(&rect,WS_OVERLAPPEDWINDOW,FALSE);
 HWND hwnd=CreateWindowW(wc.lpszClassName,L"Einhander private Remix native control",WS_OVERLAPPEDWINDOW,40,40,rect.right-rect.left,rect.bottom-rect.top,nullptr,nullptr,wc.hInstance,nullptr);
 if(!hwnd)return 1;
 remixapi_Interface api={};HMODULE dll=nullptr;
 if(!call("InitializeLibrary",remixapi_lib_loadRemixDllAndInitialize(L"C:\\Program Files\\NVIDIA Corporation\\RTX Remix\\deps\\remix_runtime\\runtime\\.trex\\d3d9.dll",&api,&dll)))return 2;
 remixapi_StartupInfo startup={};startup.sType=REMIXAPI_STRUCT_TYPE_STARTUP_INFO;startup.hwnd=hwnd;startup.forceNoVkSwapchain=FALSE;startup.combineGuiInFinalColor=TRUE;
 if(!call("Startup",api.Startup(&startup)))return 3;
 ShowWindow(hwnd,SW_SHOWNOACTIVATE);UpdateWindow(hwnd);
 remixapi_HardcodedVertex verts[]={{{5,-5,10},{0,0,-1},{0,0},0xFFFFFFFF},{{0,5,10},{0,0,-1},{0,0},0xFFFFFFFF},{{-5,-5,10},{0,0,-1},{0,0},0xFFFFFFFF}};
 remixapi_MeshInfoSurfaceTriangles surface={};surface.vertices_values=verts;surface.vertices_count=3;
 remixapi_MeshInfo mi={};mi.sType=REMIXAPI_STRUCT_TYPE_MESH_INFO;mi.hash=1;mi.surfaces_values=&surface;mi.surfaces_count=1;remixapi_MeshHandle mesh=nullptr;
 if(!call("CreateMesh",api.CreateMesh(&mi,&mesh)))return 4;
 remixapi_LightInfoSphereEXT sphere={};sphere.sType=REMIXAPI_STRUCT_TYPE_LIGHT_INFO_SPHERE_EXT;sphere.position={0,-1,0};sphere.radius=.1f;
 remixapi_LightInfo li={};li.sType=REMIXAPI_STRUCT_TYPE_LIGHT_INFO;li.pNext=&sphere;li.hash=3;li.radiance={100,200,100};remixapi_LightHandle light=nullptr;
 if(!call("CreateLight",api.CreateLight(&li,&light)))return 5;
 for(int frame=0;frame<120;++frame){pump();
  remixapi_CameraInfoParameterizedEXT cp={};cp.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO_PARAMETERIZED_EXT;cp.forward={0,0,1};cp.up={0,1,0};cp.right={1,0,0};cp.fovYInDegrees=70;cp.aspect=640.f/360;cp.nearPlane=.1f;cp.farPlane=1000;
  remixapi_CameraInfo ci={};ci.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO;ci.pNext=&cp;
  remixapi_InstanceInfo inst={};inst.sType=REMIXAPI_STRUCT_TYPE_INSTANCE_INFO;inst.mesh=mesh;inst.doubleSided=TRUE;inst.transform={{{1,0,0,0},{0,1,0,0},{0,0,1,5}}};
  if(!call("SetupCamera",api.SetupCamera(&ci))||!call("DrawInstance",api.DrawInstance(&inst))||!call("DrawLightInstance",api.DrawLightInstance(light))||!call("Present",api.Present(nullptr)))return 6;
  std::printf("{\"completed_frame\":%d}\n",frame);std::fflush(stdout);Sleep(100);
 }
 std::puts("{\"inspection_window_seconds\":10}");std::fflush(stdout);for(int i=0;i<100;++i){pump();Sleep(100);}
 call("DestroyMesh",api.DestroyMesh(mesh));call("DestroyLight",api.DestroyLight(light));
 std::atomic<bool>done{false};remixapi_ErrorCode stopped=REMIXAPI_ERROR_CODE_GENERAL_FAILURE;
 std::thread shutdown([&]{stopped=api.Shutdown();done=true;});while(!done){pump();Sleep(1);}shutdown.join();bool ok=call("Shutdown",stopped);
 FreeLibrary(dll);DestroyWindow(hwnd);UnregisterClassW(wc.lpszClassName,wc.hInstance);return ok?0:7;
}
