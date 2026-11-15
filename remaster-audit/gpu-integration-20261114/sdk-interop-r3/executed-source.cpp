#include <windows.h>
#include <GL/gl.h>
#include "../project-completion-20261114/remix-sdk-reference/remix_c.h"
#include <cstdio>
#include <cstring>
#include <vector>
#include <thread>
#include <atomic>

// Private backend qualification, deliberately no game hooks or guest data.
using SemaphoreFn = void(APIENTRY*)(unsigned long long);
using DrawVkFn = void(APIENTRY*)(unsigned long long,GLuint,GLfloat,GLfloat,GLfloat,GLfloat,GLfloat,GLfloat,GLfloat,GLfloat,GLfloat);
static bool check(const char* name, remixapi_ErrorCode code) {
  std::printf("{\"call\":\"%s\",\"result\":%d,\"tick_ms\":%llu}\n", name, (int)code,(unsigned long long)GetTickCount64()); std::fflush(stdout);
  return code==REMIXAPI_ERROR_CODE_SUCCESS;
}
static LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l) {return DefWindowProcW(h,m,w,l);}
int main(int argc,char**argv) {
  if(argc!=2) return 2;
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
  SetPriorityClass(GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS);
  const wchar_t* dir=L"C:\\Program Files\\NVIDIA Corporation\\RTX Remix\\deps\\remix_runtime\\runtime\\.trex";
  SetDllDirectoryW(dir);
  WNDCLASSW wc={}; wc.style=CS_OWNDC;wc.lpfnWndProc=proc;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"EinhanderPrivateRemixQualification";
  if(!RegisterClassW(&wc))return 3;
  RECT rect={0,0,640,360};AdjustWindowRect(&rect,WS_OVERLAPPEDWINDOW,FALSE);
  HWND hwnd=CreateWindowW(wc.lpszClassName,L"Einhander private Remix SDK probe",WS_OVERLAPPEDWINDOW,40,40,rect.right-rect.left,rect.bottom-rect.top,nullptr,nullptr,wc.hInstance,nullptr);
  if(!hwnd)return 4;
  HDC dc=GetDC(hwnd);PIXELFORMATDESCRIPTOR pf={};pf.nSize=sizeof(pf);pf.nVersion=1;pf.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;pf.iPixelType=PFD_TYPE_RGBA;pf.cColorBits=32;
  int fmt=ChoosePixelFormat(dc,&pf);if(!fmt||!SetPixelFormat(dc,fmt,&pf))return 5;
  HGLRC gl=wglCreateContext(dc);if(!gl||!wglMakeCurrent(dc,gl))return 6;
  const char* renderer=(const char*)glGetString(GL_RENDERER);
  std::printf("{\"gl_renderer\":\"%s\",\"gl_version\":\"%s\"}\n",renderer,(const char*)glGetString(GL_VERSION));std::fflush(stdout);
  if(!renderer||!strstr(renderer,"3090 Ti"))return 7;
  auto draw=(DrawVkFn)wglGetProcAddress("glDrawVkImageNV");
  auto wait=(SemaphoreFn)wglGetProcAddress("glWaitVkSemaphoreNV");
  auto signal=(SemaphoreFn)wglGetProcAddress("glSignalVkSemaphoreNV");
  if(!draw||!wait||!signal)return 8;
  // Read back an owned offscreen framebuffer: a hidden HWND is subject to pixel ownership clipping.
  auto genfb=(void(APIENTRY*)(GLsizei,GLuint*))wglGetProcAddress("glGenFramebuffers");
  auto bindfb=(void(APIENTRY*)(GLenum,GLuint))wglGetProcAddress("glBindFramebuffer");
  auto attach=(void(APIENTRY*)(GLenum,GLenum,GLenum,GLuint,GLint))wglGetProcAddress("glFramebufferTexture2D");
  auto statusfb=(GLenum(APIENTRY*)(GLenum))wglGetProcAddress("glCheckFramebufferStatus");
  auto deletefb=(void(APIENTRY*)(GLsizei,const GLuint*))wglGetProcAddress("glDeleteFramebuffers");
  if(!genfb||!bindfb||!attach||!statusfb||!deletefb)return 20;
  GLuint fb=0,color=0;glGenTextures(1,&color);glBindTexture(GL_TEXTURE_2D,color);glTexImage2D(GL_TEXTURE_2D,0,0x8058,640,360,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
  genfb(1,&fb);bindfb(0x8D40,fb);attach(0x8D40,0x8CE0,GL_TEXTURE_2D,color,0);if(statusfb(0x8D40)!=0x8CD5)return 21;glDrawBuffer(0x8CE0);glReadBuffer(0x8CE0);
  remixapi_Interface api={};HMODULE dll=nullptr;
  if(!check("InitializeLibrary",remixapi_lib_loadRemixDllAndInitialize(L"C:\\Program Files\\NVIDIA Corporation\\RTX Remix\\deps\\remix_runtime\\runtime\\.trex\\d3d9.dll",&api,&dll)))return 9;
  if(!api.Startup||!api.Shutdown||!api.Present||!api.CreateMaterial||!api.CreateMesh||!api.SetupCamera||!api.DrawInstance||!api.dxvk_GetExternalSwapchain)return 10;
  remixapi_StartupInfo startup={};startup.sType=REMIXAPI_STRUCT_TYPE_STARTUP_INFO;startup.hwnd=hwnd;startup.forceNoVkSwapchain=TRUE;startup.combineGuiInFinalColor=TRUE;
  if(!check("Startup",api.Startup(&startup)))return 11;
  int rc=0;
  remixapi_MaterialInfoOpaqueEXT opaque={};opaque.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO_OPAQUE_EXT;opaque.albedoConstant={0.05f,0.7f,0.15f};opaque.opacityConstant=1;opaque.roughnessConstant=.35f;
  remixapi_MaterialInfo material={};material.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO;material.pNext=&opaque;material.hash=0xE1A00001;material.emissiveIntensity=1;material.emissiveColorConstant={.05f,.7f,.15f};
  remixapi_MaterialHandle mh=nullptr;remixapi_MeshHandle mesh=nullptr;remixapi_LightHandle light=nullptr;
  if(!check("CreateMaterial",api.CreateMaterial(&material,&mh)))rc=12;
  remixapi_HardcodedVertex v[3]={};
  const float positions[3][3]={{-3,-2,8},{0,2,8},{3,-2,8}};
  for(int i=0;i<3;++i){std::memcpy(v[i].position,positions[i],sizeof(positions[i]));v[i].normal[2]=-1;v[i].color=0xFFFFFFFF;}
  remixapi_MeshInfoSurfaceTriangles surface={};surface.vertices_values=v;surface.vertices_count=3;surface.material=mh;
  remixapi_MeshInfo mi={};mi.sType=REMIXAPI_STRUCT_TYPE_MESH_INFO;mi.hash=0xE1A00002;mi.surfaces_values=&surface;mi.surfaces_count=1;
  if(!rc&&!check("CreateMesh",api.CreateMesh(&mi,&mesh)))rc=13;
  remixapi_LightInfoSphereEXT sphere={};sphere.sType=REMIXAPI_STRUCT_TYPE_LIGHT_INFO_SPHERE_EXT;sphere.position={0,0,3};sphere.radius=.2f;
  remixapi_LightInfo li={};li.sType=REMIXAPI_STRUCT_TYPE_LIGHT_INFO;li.pNext=&sphere;li.hash=0xE1A00003;li.radiance={100,100,100};
  if(!rc&&!check("CreateLight",api.CreateLight(&li,&light)))rc=14;
  glViewport(0,0,640,360);glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);
  for(int frame=0;!rc&&frame<24;++frame){
    MSG msg;while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessageW(&msg);}
    remixapi_CameraInfoParameterizedEXT cp={};cp.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO_PARAMETERIZED_EXT;cp.forward={0,0,1};cp.up={0,1,0};cp.right={1,0,0};cp.fovYInDegrees=60;cp.aspect=640.f/360;cp.nearPlane=.1f;cp.farPlane=100;
    remixapi_CameraInfo ci={};ci.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO;ci.pNext=&cp;
    remixapi_InstanceInfo inst={};inst.sType=REMIXAPI_STRUCT_TYPE_INSTANCE_INFO;inst.mesh=mesh;inst.doubleSided=TRUE;inst.transform={{{1,0,0,0},{0,1,0,0},{0,0,1,0}}};
    if(!check("SetupCamera",api.SetupCamera(&ci))||!check("DrawInstance",api.DrawInstance(&inst))||!check("DrawLightInstance",api.DrawLightInstance(light))||!check("Present",api.Present(nullptr))){rc=15;break;}
    uint64_t image=0,done=0,resume=0;
    if(!check("GetExternalSwapchain",api.dxvk_GetExternalSwapchain(&image,&done,&resume))||!image||!done||!resume){rc=16;break;}
    wait(done);draw(image,0,0,0,640,360,0,0,1,1,0);
    if(frame==23){
      std::vector<unsigned char> pixels(640*360*3);glPixelStorei(GL_PACK_ALIGNMENT,1);glReadPixels(0,0,640,360,GL_RGB,GL_UNSIGNED_BYTE,pixels.data());
      FILE*f=std::fopen(argv[1],"wb");if(!f){rc=17;}else{std::fprintf(f,"P6\n640 360\n255\n");for(int y=359;y>=0;--y)std::fwrite(pixels.data()+y*640*3,1,640*3,f);std::fclose(f);}
    }
    signal(resume);glFlush();GLenum error=glGetError();if(error){std::printf("{\"gl_error\":%u}\n",error);rc=18;}
    std::printf("{\"completed_frame\":%d}\n",frame);std::fflush(stdout);Sleep(67);
  }
  glFinish();
  if(mesh)check("DestroyMesh",api.DestroyMesh(mesh));if(light)check("DestroyLight",api.DestroyLight(light));if(mh)check("DestroyMaterial",api.DestroyMaterial(mh));
  // D3D9 teardown may synchronously message the HWND owner. Keep that owner pumping.
  std::atomic<bool> stopped{false};remixapi_ErrorCode shutdownCode=REMIXAPI_ERROR_CODE_GENERAL_FAILURE;
  std::thread shutdown([&]{shutdownCode=api.Shutdown();stopped.store(true);});
  while(!stopped.load()){MSG msg;while(PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)){TranslateMessage(&msg);DispatchMessageW(&msg);}Sleep(1);}
  shutdown.join();if(!check("Shutdown",shutdownCode))rc=19;
  bindfb(0x8D40,0);deletefb(1,&fb);glDeleteTextures(1,&color);
  FreeLibrary(dll);wglMakeCurrent(nullptr,nullptr);wglDeleteContext(gl);ReleaseDC(hwnd,dc);DestroyWindow(hwnd);UnregisterClassW(wc.lpszClassName,wc.hInstance);
  std::printf("{\"exit\":%d,\"gameplay\":false}\n",rc);return rc;
}
