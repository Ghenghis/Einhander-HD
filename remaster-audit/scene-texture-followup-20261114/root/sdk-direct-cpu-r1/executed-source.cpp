// Private diagnostic: public low-level Remix device registration, owned readback.
// Built on CPU during the user's GPU reservation. Do not launch before release.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d9.h>
#include "../project-completion-20261114/remix-sdk-reference/remix_c.h"
#include <cstdio>
#include <cstring>
#include <vector>
static bool api_call(const char *name,remixapi_ErrorCode rc) {
  std::printf("{\"call\":\"%s\",\"code\":%d,\"tick_ms\":%llu}\n",name,int(rc),(unsigned long long)GetTickCount64());std::fflush(stdout);return rc==REMIXAPI_ERROR_CODE_SUCCESS;
}
static bool hr_call(const char *name,HRESULT hr) {
  std::printf("{\"d3d_call\":\"%s\",\"hr\":%ld,\"tick_ms\":%llu}\n",name,long(hr),(unsigned long long)GetTickCount64());std::fflush(stdout);return SUCCEEDED(hr);
}
static LRESULT CALLBACK window_proc(HWND h,UINT m,WPARAM w,LPARAM l){return DefWindowProcW(h,m,w,l);}
static void pump(){MSG m;while(PeekMessageW(&m,nullptr,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);}}
static bool readback(IDirect3DDevice9Ex *dev,IDirect3DSurface9 *target,IDirect3DSurface9 *system,const char *prefix,int frame) {
  if(!hr_call("GetRenderTargetData",dev->GetRenderTargetData(target,system)))return false;
  D3DLOCKED_RECT rect{};if(!hr_call("LockRect",system->LockRect(&rect,nullptr,D3DLOCK_READONLY)))return false;
  D3DSURFACE_DESC desc{};system->GetDesc(&desc);
  std::vector<unsigned char> bytes(size_t(desc.Width)*desc.Height*3);
  unsigned green=0,magenta=0;
  for(UINT y=0;y<desc.Height;++y)for(UINT x=0;x<desc.Width;++x){
    const auto *p=static_cast<const unsigned char*>(rect.pBits)+size_t(y)*rect.Pitch+x*4;
    size_t i=(size_t(y)*desc.Width+x)*3;bytes[i]=p[2];bytes[i+1]=p[1];bytes[i+2]=p[0];
    if(p[1]>50&&p[1]>p[0]*1.4&&p[1]>p[2]*1.4)++green;
    if(p[2]>180&&p[0]>180&&p[1]<50)++magenta;
  }
  system->UnlockRect();char path[1024];std::snprintf(path,sizeof path,"%s.%d.ppm",prefix,frame);
  FILE *f=std::fopen(path,"wb");if(!f)return false;std::fprintf(f,"P6\n%u %u\n255\n",desc.Width,desc.Height);std::fwrite(bytes.data(),1,bytes.size(),f);std::fclose(f);
  std::printf("{\"readback_frame\":%d,\"width\":%u,\"height\":%u,\"green_pixels\":%u,\"magenta_pixels\":%u}\n",frame,desc.Width,desc.Height,green,magenta);std::fflush(stdout);return true;
}
int main(int argc,char **argv) {
  if(argc==2&&std::strcmp(argv[1],"--cpu-schema")==0) {
    std::printf("{\"cpu_only\":true,\"startup_bytes\":%zu,\"interface_bytes\":%zu,\"vertex_bytes\":%zu,\"sdk_version\":\"%d.%d.%d\"}\n",sizeof(remixapi_StartupInfo),sizeof(remixapi_Interface),sizeof(remixapi_HardcodedVertex),REMIXAPI_VERSION_MAJOR,REMIXAPI_VERSION_MINOR,REMIXAPI_VERSION_PATCH);return 0;
  }
  if(argc!=2)return 2;
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);SetPriorityClass(GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS);
  WNDCLASSW wc{};wc.hInstance=GetModuleHandleW(nullptr);wc.lpfnWndProc=window_proc;wc.lpszClassName=L"EinhanderRemixDirectControl";
  if(!RegisterClassW(&wc))return 3;
  RECT bounds{0,0,320,180};AdjustWindowRect(&bounds,WS_OVERLAPPEDWINDOW,FALSE);
  HWND window=CreateWindowW(wc.lpszClassName,L"Einhander private Remix device control",WS_OVERLAPPEDWINDOW,40,40,bounds.right-bounds.left,bounds.bottom-bounds.top,nullptr,nullptr,wc.hInstance,nullptr);
  if(!window)return 4;
  remixapi_Interface api{};HMODULE dll=nullptr;
  if(!api_call("InitializeLibrary",remixapi_lib_loadRemixDllAndInitialize(L"C:\\Program Files\\NVIDIA Corporation\\RTX Remix\\deps\\remix_runtime\\runtime\\.trex\\d3d9.dll",&api,&dll)))return 5;
  if(!api.dxvk_CreateD3D9||!api.dxvk_RegisterD3D9Device||!api.dxvk_CopyRenderingOutput||!api.dxvk_SetDefaultOutput)return 6;
  IDirect3D9Ex *d3d=nullptr;IDirect3DDevice9Ex *dev=nullptr;
  if(!api_call("CreateD3D9",api.dxvk_CreateD3D9(FALSE,&d3d))||!d3d)return 7;
  D3DPRESENT_PARAMETERS pp{};pp.BackBufferWidth=320;pp.BackBufferHeight=180;pp.BackBufferFormat=D3DFMT_A8R8G8B8;pp.BackBufferCount=1;
  pp.SwapEffect=D3DSWAPEFFECT_DISCARD;pp.hDeviceWindow=window;pp.Windowed=TRUE;pp.PresentationInterval=D3DPRESENT_INTERVAL_IMMEDIATE;
  if(!hr_call("CreateDeviceEx",d3d->CreateDeviceEx(D3DADAPTER_DEFAULT,D3DDEVTYPE_HAL,window,D3DCREATE_HARDWARE_VERTEXPROCESSING,&pp,nullptr,&dev)))return 8;
  if(!api_call("RegisterD3D9Device",api.dxvk_RegisterD3D9Device(dev)))return 9;
  ShowWindow(window,SW_SHOWNOACTIVATE);UpdateWindow(window);
  IDirect3DSurface9 *back=nullptr,*target=nullptr,*system=nullptr;
  if(!hr_call("GetBackBuffer",dev->GetBackBuffer(0,0,D3DBACKBUFFER_TYPE_MONO,&back)))return 10;
  if(!hr_call("CreateSystemSurface",dev->CreateOffscreenPlainSurface(320,180,D3DFMT_A8R8G8B8,D3DPOOL_SYSTEMMEM,&system,nullptr)))return 11;
  if(!hr_call("CreateReadbackTarget",dev->CreateRenderTarget(320,180,D3DFMT_A8R8G8B8,D3DMULTISAMPLE_NONE,0,FALSE,&target,nullptr)))return 12;
  if(!hr_call("ClearControl",dev->Clear(0,nullptr,D3DCLEAR_TARGET,D3DCOLOR_XRGB(255,0,255),1,0)))return 13;
  if(!readback(dev,back,system,argv[1],-1))return 14;
  back->Release();back=nullptr;
  // SetDefaultOutput supplies the documented CopyRenderingOutput fallback.
  // Magenta thus distinguishes an absent final-color image from an unreadable image.
  remixapi_Float4D fallback{1,0,1,1};if(!api_call("SetDefaultOutput",api.dxvk_SetDefaultOutput(REMIXAPI_DXVK_COPY_RENDERING_OUTPUT_TYPE_FINAL_COLOR,&fallback)))return 15;
  remixapi_MaterialInfoOpaqueEXT opaque{};opaque.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO_OPAQUE_EXT;opaque.albedoConstant={.05f,.7f,.15f};opaque.opacityConstant=1;opaque.roughnessConstant=.35f;opaque.alphaTestType=7;
  remixapi_MaterialInfo mat{};mat.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO;mat.pNext=&opaque;mat.hash=0xe1a00001;mat.emissiveIntensity=1;mat.emissiveColorConstant={.05f,.7f,.15f};
  remixapi_MaterialHandle mh=nullptr;if(!api_call("CreateMaterial",api.CreateMaterial(&mat,&mh)))return 16;
  remixapi_HardcodedVertex v[3]{};const float positions[3][3]={{-3,-2,8},{0,2,8},{3,-2,8}};
  for(int i=0;i<3;++i){std::memcpy(v[i].position,positions[i],sizeof positions[i]);v[i].normal[2]=-1;v[i].color=0xffffffff;}
  remixapi_MeshInfoSurfaceTriangles surface{};surface.vertices_values=v;surface.vertices_count=3;surface.material=mh;
  remixapi_MeshInfo mi{};mi.sType=REMIXAPI_STRUCT_TYPE_MESH_INFO;mi.hash=0xe1a00002;mi.surfaces_values=&surface;mi.surfaces_count=1;
  remixapi_MeshHandle mesh=nullptr;if(!api_call("CreateMesh",api.CreateMesh(&mi,&mesh)))return 17;
  remixapi_LightInfoSphereEXT sphere{};sphere.sType=REMIXAPI_STRUCT_TYPE_LIGHT_INFO_SPHERE_EXT;sphere.position={0,0,3};sphere.radius=.2f;
  remixapi_LightInfo li{};li.sType=REMIXAPI_STRUCT_TYPE_LIGHT_INFO;li.pNext=&sphere;li.hash=0xe1a00003;li.radiance={100,100,100};
  remixapi_LightHandle light=nullptr;if(!api_call("CreateLight",api.CreateLight(&li,&light)))return 18;
  int rc=0;
  for(int frame=0;frame<120&&!rc;++frame) {
    pump();remixapi_CameraInfoParameterizedEXT cp{};cp.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO_PARAMETERIZED_EXT;cp.forward={0,0,1};cp.up={0,1,0};cp.right={1,0,0};cp.fovYInDegrees=70;cp.aspect=320.f/180;cp.nearPlane=.1f;cp.farPlane=1000;
    remixapi_CameraInfo ci{};ci.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO;ci.pNext=&cp;
    remixapi_InstanceInfo inst{};inst.sType=REMIXAPI_STRUCT_TYPE_INSTANCE_INFO;inst.mesh=mesh;inst.doubleSided=TRUE;inst.transform={{{1,0,0,0},{0,1,0,0},{0,0,1,0}}};
    if(!api_call("SetupCamera",api.SetupCamera(&ci))||!api_call("DrawInstance",api.DrawInstance(&inst))||!api_call("DrawLightInstance",api.DrawLightInstance(light))){rc=19;break;}
    // Bypass ONLY the API Present helper. The same registered renderer device
    // executes its normal native presentation path, with no API swapchain query.
    if(!hr_call("DevicePresent",dev->Present(nullptr,nullptr,nullptr,nullptr))){rc=20;break;}
    if(frame==7||frame==31||frame==119) {
      if(!api_call("CopyFinalColor",api.dxvk_CopyRenderingOutput(target,REMIXAPI_DXVK_COPY_RENDERING_OUTPUT_TYPE_FINAL_COLOR))||!readback(dev,target,system,argv[1],frame)){rc=21;break;}
    }
    std::printf("{\"completed_frame\":%d}\n",frame);std::fflush(stdout);Sleep(100);
  }
  target->Release();system->Release();
  api_call("DestroyMesh",api.DestroyMesh(mesh));api_call("DestroyLight",api.DestroyLight(light));api_call("DestroyMaterial",api.DestroyMaterial(mh));
  // Registration gives the API its renderer device; Shutdown owns its teardown.
  // No resource references held by this probe remain. Do not Release dangling
  // d3d/dev pointers after Shutdown's device/global reference cleanup.
  if(!api_call("Shutdown",api.Shutdown()))rc=22;dev=nullptr;d3d=nullptr;
  FreeLibrary(dll);DestroyWindow(window);UnregisterClassW(wc.lpszClassName,wc.hInstance);
  std::printf("{\"exit\":%d,\"gameplay\":false}\n",rc);return rc;
}
