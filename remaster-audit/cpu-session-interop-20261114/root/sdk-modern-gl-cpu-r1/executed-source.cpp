// Private API0.16.1 interop qualification. Not a game backend or an installed release.
// Official release header documents Submit -> external-memory/timeline GL -> Present.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <GL/gl.h>
#include "sdk-release-header/remix_c.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <thread>
#include <vector>

static_assert(REMIXAPI_VERSION_MINOR==16 && REMIXAPI_VERSION_PATCH==1,"Pinned API required");
static_assert(sizeof(remixapi_Interface)==288,"Unexpected SDK ABI");
namespace {
constexpr int W=320,H=180,FRAMES=32;
constexpr GLenum FBO=0x8d40,COLOR=0x8ce0,COMPLETE=0x8cd5;
constexpr GLenum HANDLE_WIN32=0x9587,TYPE_NV=0x95b3,TIMELINE_NV=0x95b5,VALUE_NV=0x9595,GENERAL=0x958d;
constexpr GLenum RGBA8=0x8058,SRGBA8=0x8c43,RGBA16F=0x881a,RGBA32F=0x8814;
using U64=unsigned long long;
using Gen=void(APIENTRY*)(GLsizei,GLuint*);
using Del=void(APIENTRY*)(GLsizei,const GLuint*);
struct Gl {
  Gen createMemory,createSemaphore,genFramebuffer;
  Del deleteMemory,deleteSemaphore,deleteFramebuffer;
  void(APIENTRY*importMemory)(GLuint,U64,GLenum,void*);
  void(APIENTRY*importSemaphore)(GLuint,GLenum,void*);
  void(APIENTRY*memoryParam)(GLuint,GLenum,const GLint*);
  void(APIENTRY*semaphoreType)(GLuint,GLenum,const GLint*);
  void(APIENTRY*semaphoreValue)(GLuint,GLenum,const U64*);
  void(APIENTRY*wait)(GLuint,GLuint,const GLuint*,GLuint,const GLuint*,const GLenum*);
  void(APIENTRY*signal)(GLuint,GLuint,const GLuint*,GLuint,const GLuint*,const GLenum*);
  void(APIENTRY*textureStorage)(GLenum,GLsizei,GLenum,GLsizei,GLsizei,GLuint,U64);
  void(APIENTRY*bindFramebuffer)(GLenum,GLuint);
  void(APIENTRY*attach)(GLenum,GLenum,GLenum,GLuint,GLint);
  GLenum(APIENTRY*framebufferStatus)(GLenum);
};
template<class T> bool load(T&dst,const char*name){
  auto p=wglGetProcAddress(name);auto v=reinterpret_cast<intptr_t>(p);
  if(!p||v==1||v==2||v==3||v==-1){std::printf("{\"missing_gl\":\"%s\"}\n",name);return false;}
  dst=reinterpret_cast<T>(p);return true;
}
bool init(Gl&g){
#define FN(field,name) if(!load(g.field,name))return false
  FN(createMemory,"glCreateMemoryObjectsEXT");FN(deleteMemory,"glDeleteMemoryObjectsEXT");
  FN(importMemory,"glImportMemoryWin32HandleEXT");FN(memoryParam,"glMemoryObjectParameterivEXT");
  FN(createSemaphore,"glCreateSemaphoresNV");FN(deleteSemaphore,"glDeleteSemaphoresEXT");
  FN(importSemaphore,"glImportSemaphoreWin32HandleEXT");FN(semaphoreType,"glSemaphoreParameterivNV");
  FN(semaphoreValue,"glSemaphoreParameterui64vEXT");FN(wait,"glWaitSemaphoreEXT");FN(signal,"glSignalSemaphoreEXT");
  FN(textureStorage,"glTexStorageMem2DEXT");FN(genFramebuffer,"glGenFramebuffers");
  FN(deleteFramebuffer,"glDeleteFramebuffers");FN(bindFramebuffer,"glBindFramebuffer");
  FN(attach,"glFramebufferTexture2D");FN(framebufferStatus,"glCheckFramebufferStatus");
#undef FN
  return true;
}
bool glOk(const char*where){GLenum e=glGetError();if(e)std::printf("{\"gl_error\":%u,\"where\":\"%s\"}\n",e,where);return !e;}
bool call(const char*where,remixapi_ErrorCode rc){std::printf("{\"call\":\"%s\",\"rc\":%d}\n",where,int(rc));std::fflush(stdout);return rc==REMIXAPI_ERROR_CODE_SUCCESS;}
HANDLE duplicate(uint64_t original){HANDLE h=nullptr;if(!original||!DuplicateHandle(GetCurrentProcess(),reinterpret_cast<HANDLE>(uintptr_t(original)),GetCurrentProcess(),&h,0,FALSE,DUPLICATE_SAME_ACCESS))return nullptr;return h;}
bool importSem(Gl&g,uint64_t original,GLuint&out){
  HANDLE h=duplicate(original);if(!h)return false;g.createSemaphore(1,&out);
  const GLint type=TIMELINE_NV;g.semaphoreType(out,TYPE_NV,&type);g.importSemaphore(out,HANDLE_WIN32,h);
  CloseHandle(h);return out&&glOk("import-timeline");
}
GLenum format(remixapi_TextureFormat f){switch(f){case REMIXAPI_TEXTURE_FORMAT_RGBA8_UNORM:case REMIXAPI_TEXTURE_FORMAT_BGRA8_UNORM:return RGBA8;case REMIXAPI_TEXTURE_FORMAT_RGBA8_SRGB:case REMIXAPI_TEXTURE_FORMAT_BGRA8_SRGB:return SRGBA8;case REMIXAPI_TEXTURE_FORMAT_RGBA16_SFLOAT:return RGBA16F;case REMIXAPI_TEXTURE_FORMAT_RGBA32_SFLOAT:return RGBA32F;default:return 0;}}
uint32_t pixelBytes(remixapi_TextureFormat f){switch(f){case REMIXAPI_TEXTURE_FORMAT_RGBA8_UNORM:case REMIXAPI_TEXTURE_FORMAT_BGRA8_UNORM:case REMIXAPI_TEXTURE_FORMAT_RGBA8_SRGB:case REMIXAPI_TEXTURE_FORMAT_BGRA8_SRGB:return 4;case REMIXAPI_TEXTURE_FORMAT_RGBA16_SFLOAT:return 8;case REMIXAPI_TEXTURE_FORMAT_RGBA32_SFLOAT:return 16;default:return 0;}}
bool metadata(const remixapi_dxvk_InteropInfo&i){return i.imageMemory_Handle&&i.allocationSize>=uint64_t(W)*H*pixelBytes(i.interopImageFormat)&&i.allocationSize<=256ull*1024*1024&&i.width==W&&i.height==H&&format(i.interopImageFormat)&&i.dxvkDoneSemaphore_Handle&&i.clientDoneSemaphore_Handle&&i.dxvkDoneSemaphore_ValueToWait;}
void pump(){MSG m;while(PeekMessageW(&m,nullptr,0,0,PM_REMOVE)){TranslateMessage(&m);DispatchMessageW(&m);}}
LRESULT CALLBACK windowProc(HWND w,UINT m,WPARAM p,LPARAM l){return DefWindowProcW(w,m,p,l);}
bool capture(GLuint tex,GLuint fb,Gl&g,const char*prefix,int frame,int&green){
  g.bindFramebuffer(FBO,fb);g.attach(FBO,COLOR,GL_TEXTURE_2D,tex,0);
  if(g.framebufferStatus(FBO)!=COMPLETE||!glOk("external-fbo"))return false;
  glReadBuffer(COLOR);std::vector<float> px(size_t(W)*H*4);glReadPixels(0,0,W,H,GL_RGBA,GL_FLOAT,px.data());
  if(!glOk("readback"))return false;
  int finite=0,magenta=0;green=0;std::vector<unsigned char> rgb(size_t(W)*H*3);
  for(int j=0;j<W*H;++j){float a=px[j*4],b=px[j*4+1],c=px[j*4+2];if(std::isfinite(a)&&std::isfinite(b)&&std::isfinite(c))finite++;
    if(b>.15f&&b>1.3f*a&&b>1.3f*c)green++;if(a>.8f&&c>.8f&&b<.05f)magenta++;
    for(int k=0;k<3;++k){float v=px[j*4+k];rgb[size_t(j)*3+k]=std::isfinite(v)?static_cast<unsigned char>(std::clamp(v,0.f,1.f)*255.f):0;}}
  char name[2048];std::snprintf(name,sizeof name,"%s.%d.ppm",prefix,frame);FILE*f=std::fopen(name,"wb");if(!f)return false;
  std::fprintf(f,"P6\n%d %d\n255\n",W,H);for(int y=H-1;y>=0;--y)std::fwrite(rgb.data()+size_t(y)*W*3,1,size_t(W)*3,f);std::fclose(f);
  std::printf("{\"frame\":%d,\"finite_pixels\":%d,\"green_pixels\":%d,\"fallback_magenta_pixels\":%d}\n",frame,finite,green,magenta);std::fflush(stdout);
  g.attach(FBO,COLOR,GL_TEXTURE_2D,0,0);g.bindFramebuffer(FBO,0);
  return finite==W*H&&green>500&&magenta<W*H/10;
}
}
int main(int argc,char**argv){
  if(argc==2&&!std::strcmp(argv[1],"--guard-contract")){
    const bool reserved=GetFileAttributesW(L"C:\\github\\Einhander\\remaster-audit\\comfy-authoring\\GPU-RESERVED")!=INVALID_FILE_ATTRIBUTES;
    std::printf("{\"reservation_exists\":%s,\"gpu_started\":false,\"dll_loaded\":false}\n",reserved?"true":"false");return reserved?77:0;
  }
  // This CPU mode does not create a window, load a DLL or call any graphics API.
  if(argc==2&&!std::strcmp(argv[1],"--cpu-contract")){
    remixapi_dxvk_InteropInfo i={};int checks=0;auto test=[&](bool b){++checks;return b;};bool ok=test(!metadata(i));
    i.imageMemory_Handle=1;i.allocationSize=uint64_t(W)*H*8;i.width=W;i.height=H;i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_RGBA16_SFLOAT;i.dxvkDoneSemaphore_Handle=2;i.clientDoneSemaphore_Handle=3;i.dxvkDoneSemaphore_ValueToWait=1;
    ok&=test(metadata(i));i.width=W+1;ok&=test(!metadata(i));i.width=W;i.allocationSize=256ull*1024*1024+1;ok&=test(!metadata(i));i.allocationSize=1;ok&=test(!metadata(i));i.allocationSize=W*H*8;i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_R32_SFLOAT;ok&=test(!metadata(i));i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_BGRA8_UNORM;ok&=test(metadata(i));i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_RGBA8_SRGB;ok&=test(metadata(i));i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_RGBA8_UNORM;ok&=test(metadata(i));i.dxvkDoneSemaphore_ValueToWait=0;ok&=test(!metadata(i));
    std::printf("{\"cpu_contract_checks\":%d,\"passed\":%s,\"dll_loaded\":false,\"gl_context\":false}\n",checks,ok?"true":"false");return ok?0:1;
  }
  if(argc!=3||std::strcmp(argv[1],"--run-after-explicit-user-release")){std::puts("Private GPU probe is not enabled. CPU-only: --cpu-contract");return 2;}
  if(GetFileAttributesW(L"C:\\github\\Einhander\\remaster-audit\\comfy-authoring\\GPU-RESERVED")!=INVALID_FILE_ATTRIBUTES){std::puts("{\"blocked\":\"user GPU reservation exists\",\"gpu_started\":false}");return 77;}
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);SetPriorityClass(GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS);
  WNDCLASSW wc={};wc.style=CS_OWNDC;wc.lpfnWndProc=windowProc;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"EinhanderModernPrivateProbe";
  if(!RegisterClassW(&wc))return 3;RECT r={0,0,W,H};AdjustWindowRect(&r,WS_OVERLAPPEDWINDOW,FALSE);
  HWND win=CreateWindowW(wc.lpszClassName,L"Einhander private modern SDK qualification",WS_OVERLAPPEDWINDOW,40,40,r.right-r.left,r.bottom-r.top,nullptr,nullptr,wc.hInstance,nullptr);if(!win)return 4;
  HDC dc=GetDC(win);PIXELFORMATDESCRIPTOR pf={};pf.nSize=sizeof pf;pf.nVersion=1;pf.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;pf.iPixelType=PFD_TYPE_RGBA;pf.cColorBits=32;
  int pix=ChoosePixelFormat(dc,&pf);if(!pix||!SetPixelFormat(dc,pix,&pf))return 5;HGLRC ctx=wglCreateContext(dc);if(!ctx||!wglMakeCurrent(dc,ctx))return 6;
  const char*renderer=reinterpret_cast<const char*>(glGetString(GL_RENDERER));std::printf("{\"gl_renderer\":\"%s\"}\n",renderer?renderer:"");if(!renderer||!std::strstr(renderer,"3090 Ti"))return 7;
  Gl gl={};if(!init(gl))return 8;
  // Owned offscreen baseline: first prove GL readback independently of SDK output.
  GLuint fb=0,baseline=0;gl.genFramebuffer(1,&fb);gl.bindFramebuffer(FBO,fb);glGenTextures(1,&baseline);glBindTexture(GL_TEXTURE_2D,baseline);glTexImage2D(GL_TEXTURE_2D,0,RGBA8,W,H,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);gl.attach(FBO,COLOR,GL_TEXTURE_2D,baseline,0);if(gl.framebufferStatus(FBO)!=COMPLETE)return 9;
  glDrawBuffer(COLOR);glReadBuffer(COLOR);glClearColor(1,0,1,1);glClear(GL_COLOR_BUFFER_BIT);std::vector<unsigned char> base(size_t(W)*H*4);glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,base.data());int magenta=0;for(int j=0;j<W*H;++j)if(base[j*4]==255&&base[j*4+1]==0&&base[j*4+2]==255)magenta++;if(!glOk("baseline")||magenta!=W*H)return 10;
  std::printf("{\"owned_readback_magenta_pixels\":%d}\n",magenta);gl.bindFramebuffer(FBO,0);ShowWindow(win,SW_SHOWNOACTIVATE);
  const wchar_t*dir=L"C:\\github\\Einhander\\remaster-audit\\runtime-review\\gpu-texture-remix-20261114\\sdk-v016-release\\win64";SetDllDirectoryW(dir);
  remixapi_Interface api={};HMODULE dll=nullptr;if(!call("InitializeLibrary",remixapi_lib_loadRemixDllAndInitialize(L"C:\\github\\Einhander\\remaster-audit\\runtime-review\\gpu-texture-remix-20261114\\sdk-v016-release\\win64\\d3d9.dll",&api,&dll)))return 11;
  if(!api.Startup||!api.Submit||!api.Present||!api.dxvk_GetInteropInfo||!api.Shutdown)return 12;
  remixapi_StartupInfo si={};si.sType=REMIXAPI_STRUCT_TYPE_STARTUP_INFO;si.hwnd=win;si.interopImage=1;si.useRemixOwnedChildWindow=1;si.combineGuiInFinalColor=1;
  if(!call("Startup",api.Startup(&si)))return 13;
  int rc=0;remixapi_dxvk_InteropInfo initial={};GLuint done=0,client=0;
  if(!call("InteropInfo-initial",api.dxvk_GetInteropInfo(&initial))||!importSem(gl,initial.dxvkDoneSemaphore_Handle,done)||!importSem(gl,initial.clientDoneSemaphore_Handle,client))rc=14;
  remixapi_MaterialInfoOpaqueEXT op={};op.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO_OPAQUE_EXT;op.albedoConstant={.02f,.8f,.02f};op.opacityConstant=1;op.roughnessConstant=.4f;op.alphaTestType=7;
  remixapi_MaterialInfo mi={};mi.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO;mi.pNext=&op;mi.hash=0xe1a01601;mi.emissiveIntensity=2;mi.emissiveColorConstant={.02f,.8f,.02f};remixapi_MaterialHandle material=nullptr;
  if(!rc&&!call("CreateMaterial",api.CreateMaterial(&mi,&material)))rc=15;
  remixapi_HardcodedVertex vertices[3]={};const float positions[3][3]={{-3,-2,8},{0,2,8},{3,-2,8}};for(int j=0;j<3;++j){std::memcpy(vertices[j].position,positions[j],sizeof positions[j]);vertices[j].normal[2]=-1;vertices[j].color=0xffffffff;}
  remixapi_MeshInfoSurfaceTriangles surface={};surface.vertices_values=vertices;surface.vertices_count=3;surface.material=material;remixapi_MeshInfo meshinfo={};meshinfo.sType=REMIXAPI_STRUCT_TYPE_MESH_INFO;meshinfo.hash=0xe1a01602;meshinfo.surfaces_values=&surface;meshinfo.surfaces_count=1;remixapi_MeshHandle mesh=nullptr;
  if(!rc&&!call("CreateMesh",api.CreateMesh(&meshinfo,&mesh)))rc=16;
  U64 clientValue=0,lastDone=0;int acceptedImages=0;
  for(int frame=0;!rc&&frame<FRAMES;++frame){pump();remixapi_CameraInfoParameterizedEXT cp={};cp.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO_PARAMETERIZED_EXT;cp.forward={0,0,1};cp.up={0,1,0};cp.right={1,0,0};cp.fovYInDegrees=60;cp.aspect=float(W)/H;cp.nearPlane=.1f;cp.farPlane=100;
    remixapi_CameraInfo camera={};camera.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO;camera.pNext=&cp;remixapi_InstanceInfo instance={};instance.sType=REMIXAPI_STRUCT_TYPE_INSTANCE_INFO;instance.mesh=mesh;instance.doubleSided=1;instance.transform={{{1,0,0,0},{0,1,0,0},{0,0,1,0}}};auto submit=remixapi_SubmitInfo_init();
    if(!call("SetupCamera",api.SetupCamera(&camera))||!call("DrawInstance",api.DrawInstance(&instance))||!call("Submit",api.Submit(&submit))){rc=17;break;}
    remixapi_dxvk_InteropInfo info={};if(!call("InteropInfo",api.dxvk_GetInteropInfo(&info))||!metadata(info)||info.dxvkDoneSemaphore_Handle!=initial.dxvkDoneSemaphore_Handle||info.clientDoneSemaphore_Handle!=initial.clientDoneSemaphore_Handle||info.dxvkDoneSemaphore_ValueToWait<=lastDone){rc=18;break;}lastDone=info.dxvkDoneSemaphore_ValueToWait;
    // Re-import each qualification frame: no unsupported image-generation/handle ABA cache assumption.
    GLuint memory=0,tex=0;HANDLE handle=duplicate(info.imageMemory_Handle);if(!handle){rc=19;break;}gl.createMemory(1,&memory);gl.importMemory(memory,info.allocationSize,HANDLE_WIN32,handle);CloseHandle(handle);glGenTextures(1,&tex);glBindTexture(GL_TEXTURE_2D,tex);gl.textureStorage(GL_TEXTURE_2D,1,format(info.interopImageFormat),W,H,memory,0);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    const GLenum layout=GENERAL;U64 waitValue=info.dxvkDoneSemaphore_ValueToWait;gl.semaphoreValue(done,VALUE_NV,&waitValue);gl.wait(done,0,nullptr,1,&tex,&layout);
    if(!glOk("import-wait"))rc=20;
    if(!rc&&(frame==7||frame==23||frame==31)){int green=0;if(capture(tex,fb,gl,argv[2],frame,green))acceptedImages++;}
    ++clientValue;gl.semaphoreValue(client,VALUE_NV,&clientValue);gl.signal(client,0,nullptr,1,&tex,&layout);glFlush();
    auto present=remixapi_PresentInfo_init();present.interopFlipY=1;present.clientDoneSemaphore_ValueToWait=clientValue;
    if(!call("Present",api.Present(&present)))rc=21;glFinish();gl.bindFramebuffer(FBO,0);glDeleteTextures(1,&tex);gl.deleteMemory(1,&memory);Sleep(100);
  }
  if(!rc&&acceptedImages!=3)rc=22;
  if(mesh)call("DestroyMesh",api.DestroyMesh(mesh));if(material)call("DestroyMaterial",api.DestroyMaterial(material));glFinish();
  if(done)gl.deleteSemaphore(1,&done);if(client)gl.deleteSemaphore(1,&client);
  std::atomic<bool> stopped{false};remixapi_ErrorCode shutdownRc=REMIXAPI_ERROR_CODE_GENERAL_FAILURE;std::thread shutdown([&]{shutdownRc=api.Shutdown();stopped.store(true);});while(!stopped.load()){pump();Sleep(1);}shutdown.join();if(!call("Shutdown",shutdownRc))rc=23;
  gl.deleteFramebuffer(1,&fb);glDeleteTextures(1,&baseline);FreeLibrary(dll);wglMakeCurrent(nullptr,nullptr);wglDeleteContext(ctx);ReleaseDC(win,dc);DestroyWindow(win);UnregisterClassW(wc.lpszClassName,wc.hInstance);
  std::printf("{\"exit\":%d,\"accepted_images\":%d,\"gameplay\":false}\n",rc,acceptedImages);return rc;
}
