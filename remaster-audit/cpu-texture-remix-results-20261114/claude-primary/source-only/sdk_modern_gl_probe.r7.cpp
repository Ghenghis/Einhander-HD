// Private API0.16.1 interop qualification, r7 PROPOSAL (claude-einhander; root reviews and applies canonical).
// r7 (root msg_eee3aa32): legal 'not ready' frames. Per the official client (GlInterop.java:41/98/280), interop image
//  handle 0 or -1 means 'no image yet' and the client's last waited value starts at -1, so a dxvkDone value of 0 is legal.
//  Such frames are NOT READY: no import, no wait, no readback, never counted or accepted; Submit is still paired with
//  Present (clientDone signalled without an image barrier). They stay bounded by the ready/capture deadlines; all-not-ready
//  until the ready limit FAILs as no_interop_image_within_ready_window. Still fatal (rc 18): zero or changed semaphore
//  handles (explicit prerequisite; the client requires them nonzero), a present image with the wrong size/format, a
//  value that decreases, and value 0 after a positive wait on the same imported image. Deadlines are now checked before
//  any frame is counted. r6 af7eb6e43e9d1bdf4e60952f42d870b3079f43b138a81f68f2fbb7b10b617a6e is preserved unchanged.
// r6 (root review of r5 c2a6e7ee, msg_c0ba2d55): deadline BEFORE success. The ready window is the half-open interval
//  [0, readyLimit) seconds from the first frame loop start: a frame observed at t >= readyLimit never counts, even if it
//  passes the oracle (e.g. after a long blocking Submit or readback). The capture window is likewise half-open:
//  [firstValidSeconds, firstValidSeconds + 20 s). r6 still rejected timeline value 0; r7 above replaces that.
//  r5 c2a6e7eebfa241bb38a6ca2787d1fa1b9658e9a6d8a0f7b40c73c4266f6005d0 is preserved unchanged.
// Not a game backend or an installed release. Official release header documents Submit -> external-memory/timeline GL -> Present.
// Base: r4 sdk_modern_gl_probe.cpp 3f77474fea5208bafae6a7cd82132f0188584a030112c7db68915e04f382a2dc.
// r5 changes, each matched to the official 0.16.1 client (NVIDIAGameWorks/rtx-remix-minecraft 7d2ba9f):
//  D1 camera: right = forward x up (RemixRenderer.updateCamera), explicit WORLD type and position.
//  D2 interop image imported once and re-imported only when handle/size/width/height/format change
//     (GlInterop.recreateImagesIf; header remix_c.h step 3). A re-import resets the last waited value (as the client does).
//  D3 dxvkDone value: greater -> wait; equal -> skip the wait, no new Remix output this frame; smaller -> contract error
//     (GlInterop.waitForVk).
//  Bounded readiness: Submit/Present keep running every frame for at most --ready-seconds (default 30, 5..120). The first
//  frame that passes the UNCHANGED r4 green oracle ends readiness; then offsets -2/0/+2 are each settled for SETTLE fresh
//  frames and captured once with the same oracle. Black is never accepted. Capture files keep the r4 slot names
//  <prefix>.7/.23/.31.ppm (offsets -2/0/+2) so the runner's image audit is unchanged; actual frame numbers are printed.
//  Records first_nonblack/first_valid frame+seconds, imports, skipped-equal frames, shutdown_seconds and the cache/config
//  environment it runs under. The probe never creates, moves or clears any cache (policy is the parent runner's).
// The cold-compile/async-gating explanation (review b51b60a4, addendum 00b22020) is a HYPOTHESIS this probe can test,
// not an established cause.
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
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

static_assert(REMIXAPI_VERSION_MINOR==16 && REMIXAPI_VERSION_PATCH==1,"Pinned API required");
static_assert(sizeof(remixapi_Interface)==288,"Unexpected SDK ABI");
namespace {
constexpr int W=320,H=180,SETTLE=6,FRAME_SLEEP_MS=100,FRAME_CAP=4000,READY_DEFAULT=30,READY_MIN=5,READY_MAX=120;
constexpr double CAPTURE_WINDOW_SECONDS=20.0;
constexpr float OFFSETS[3]={-2.f,0.f,2.f};
constexpr int SLOT_NAME[3]={7,23,31};   // r4 file names, kept for the runner's unchanged image audit
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
bool glOk(const char*where){bool ok=true;for(int n=0;n<32;++n){GLenum e=glGetError();if(!e)return ok;ok=false;std::printf("{\"gl_error\":%u,\"where\":\"%s\"}\n",e,where);}std::fflush(stdout);return false;}
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
bool ownedLease(const std::string&bytes,const std::string&nonce){
  if(nonce.size()!=32||nonce.find_first_not_of("0123456789abcdef")!=std::string::npos||bytes.size()>4096)return false;
  const std::string prefix="{\"owner\":\"codex-einhander\",\"purpose\":\"private-modern-sdk-gl-probe\",\"lease_nonce\":\""+nonce+"\",";
  return bytes.rfind(prefix,0)==0&&bytes.size()>prefix.size()+2&&bytes.substr(bytes.size()-2)=="}\n";
}
bool executionLease(){
  const char*nonce=std::getenv("EINHANDER_PRIVATE_GPU_NONCE");if(!nonce)return false;
  std::ifstream file("C:/github/Einhander/remaster-audit/comfy-authoring/GPU-RESERVED",std::ios::binary|std::ios::ate);
  if(!file)return false;const auto size=file.tellg();if(size<0||size>4096)return false;
  std::string bytes(static_cast<size_t>(size),'\0');file.seekg(0);if(!file.read(bytes.data(),size))return false;
  return ownedLease(bytes,nonce);
}
double seconds(){static LARGE_INTEGER f={},t0={};LARGE_INTEGER c;if(!f.QuadPart){QueryPerformanceFrequency(&f);QueryPerformanceCounter(&t0);}QueryPerformanceCounter(&c);return double(c.QuadPart-t0.QuadPart)/double(f.QuadPart);}
std::string jsonText(const char*s){std::string o;for(const char*p=s?s:"";*p;++p){unsigned char c=static_cast<unsigned char>(*p);if(c=='"'||c=='\\'){o+='\\';o+=char(c);}else if(c<0x20){char b[8];std::snprintf(b,sizeof b,"\\u%04x",c);o+=b;}else o+=char(c);}return o;}

// ---- D1: official camera basis (RemixRenderer.updateCamera: up = right x forward, i.e. right = forward x up)
struct V3{float x,y,z;};
V3 cross(V3 a,V3 b){return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
float dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
struct Basis{V3 forward,up,right;};
Basis officialBasis(){const V3 f{0,0,1},u{0,1,0};return {f,u,cross(f,u)};}

// ---- D3: dxvkDone timeline handling (GlInterop.waitForVk)
enum class WaitAction{Wait,SkipEqual,ErrorDecrease};
WaitAction waitAction(bool haveLast,U64 last,U64 next){if(!haveLast||next>last)return WaitAction::Wait;if(next==last)return WaitAction::SkipEqual;return WaitAction::ErrorDecrease;}

// ---- D2: persistent interop import (GlInterop.recreateImagesIf; header step 3)
struct ImportKey{uint64_t handle,size;int w,h;GLenum fmt;};
bool importNeeded(bool imported,const ImportKey&have,const ImportKey&want){return !imported||have.handle!=want.handle||have.size!=want.size||have.w!=want.w||have.h!=want.h||have.fmt!=want.fmt;}

// ---- r7: interop frame classification (official GlInterop: handle 0/-1 = no image yet; last waited = -1 accepts 0)
bool semaphoresMatch(const remixapi_dxvk_InteropInfo&i,const remixapi_dxvk_InteropInfo&initial){return i.dxvkDoneSemaphore_Handle&&i.clientDoneSemaphore_Handle&&i.dxvkDoneSemaphore_Handle==initial.dxvkDoneSemaphore_Handle&&i.clientDoneSemaphore_Handle==initial.clientDoneSemaphore_Handle;}
bool imagePresent(const remixapi_dxvk_InteropInfo&i){return i.imageMemory_Handle!=0&&i.imageMemory_Handle!=~uint64_t(0);}
bool imageMetaValid(const remixapi_dxvk_InteropInfo&i){return i.allocationSize>=uint64_t(W)*H*pixelBytes(i.interopImageFormat)&&i.allocationSize<=256ull*1024*1024&&i.width==W&&i.height==H&&format(i.interopImageFormat);}
ImportKey keyOf(const remixapi_dxvk_InteropInfo&i){return {i.imageMemory_Handle,i.allocationSize,i.width,i.height,format(i.interopImageFormat)};}
enum class Interop{Fatal,NoImage,ZeroValue,Image};
// haveLastOnSameImage: a value was already waited on THIS imported image (the client resets its last value on re-import).
Interop classifyInterop(const remixapi_dxvk_InteropInfo&i,const remixapi_dxvk_InteropInfo&initial,bool haveLastOnSameImage,U64 last){
  if(!semaphoresMatch(i,initial))return Interop::Fatal;      // explicit prerequisite: nonzero, stable semaphores
  if(!imagePresent(i))return Interop::NoImage;                // legal: no image yet
  if(!imageMetaValid(i))return Interop::Fatal;                // a present image of the wrong size/format violates the contract
  if(i.dxvkDoneSemaphore_ValueToWait==0)return haveLastOnSameImage&&last>0?Interop::Fatal:Interop::ZeroValue;  // 0 after progress = decrease
  return Interop::Image;
}
struct FramePlan{bool wait,read,signalImage;};
FramePlan planFor(Interop k,WaitAction a){if(k!=Interop::Image)return {false,false,false};return {a==WaitAction::Wait,a==WaitAction::Wait,true};}

// ---- Image classification; the oracle is r4's capture() acceptance, unchanged
struct Image{int finite=0,green=0,magenta=0,nonblack=0;};
Image classify(const std::vector<float>&px){Image r;for(int j=0;j<W*H;++j){float a=px[size_t(j)*4],b=px[size_t(j)*4+1],c=px[size_t(j)*4+2];
  if(std::isfinite(a)&&std::isfinite(b)&&std::isfinite(c)){r.finite++;if(a>1.f/255||b>1.f/255||c>1.f/255)r.nonblack++;}
  if(b>.15f&&b>1.3f*a&&b>1.3f*c)r.green++;if(a>.8f&&c>.8f&&b<.05f)r.magenta++;}return r;}
bool oracle(const Image&i){return i.finite==W*H&&i.green>500&&i.magenta<W*H/10;}

// ---- Bounded readiness/capture state machine (pure; covered by --cpu-contract)
enum class Phase{Ready,Settle,Done,Fail};
enum class Obs{Fresh,SkipEqual,NotReady};
struct Machine{
  Phase phase=Phase::Ready;double readyLimit=READY_DEFAULT;int slot=0,settled=0,accepted=0,fresh=0,skipped=0,notReady=0;
  int firstNonblackFrame=-1,firstValidFrame=-1;double firstNonblackSeconds=-1,firstValidSeconds=-1;const char*failure="";
  bool active()const{return phase==Phase::Ready||phase==Phase::Settle;}
  float offset()const{return phase==Phase::Ready?0.f:OFFSETS[std::min(slot,2)];}
  // Fresh: a new dxvkDone value was waited and read. SkipEqual: same value as the last wait (no new output).
  // NotReady (r7): no interop image yet or value 0; never read, counted or accepted.
  // Deadlines come first (half-open windows): nothing observed at or after a deadline is counted or recorded.
  // Returns the capture slot (0..2) this frame's image must be written to, or -1.
  int stepKind(int frame,double t,Obs kind,const Image&img){
    if(!active())return -1;
    if(phase==Phase::Ready&&t>=readyLimit){phase=Phase::Fail;failure=fresh==0?"no_interop_image_within_ready_window":firstNonblackFrame<0?"no_rt_output_within_ready_window":"no_valid_green_within_ready_window";return -1;}
    if(phase==Phase::Settle&&t-firstValidSeconds>=CAPTURE_WINDOW_SECONDS){phase=Phase::Fail;failure="capture_window_exceeded";return -1;}
    if(kind==Obs::NotReady){++notReady;return -1;}
    if(kind==Obs::SkipEqual){++skipped;return -1;}
    ++fresh;
    if(phase==Phase::Ready){
      if(img.nonblack>0&&firstNonblackFrame<0){firstNonblackFrame=frame;firstNonblackSeconds=t;}
      if(oracle(img)){firstValidFrame=frame;firstValidSeconds=t;phase=Phase::Settle;slot=0;settled=0;}
      return -1;
    }
    if(settled<SETTLE){++settled;return -1;}
    const int s=slot;if(oracle(img))++accepted;++slot;settled=0;if(slot==3)phase=Phase::Done;return s;
  }
  int step(int frame,double t,bool isFresh,const Image&img){return stepKind(frame,t,isFresh?Obs::Fresh:Obs::SkipEqual,img);}
};

bool readback(GLuint tex,GLuint fb,Gl&g,std::vector<float>&px,Image&img){
  g.bindFramebuffer(FBO,fb);g.attach(FBO,COLOR,GL_TEXTURE_2D,tex,0);
  auto detach=[&]{g.attach(FBO,COLOR,GL_TEXTURE_2D,0,0);g.bindFramebuffer(FBO,0);};
  if(g.framebufferStatus(FBO)!=COMPLETE||!glOk("external-fbo")){detach();return false;}
  glReadBuffer(COLOR);px.assign(size_t(W)*H*4,0.f);glReadPixels(0,0,W,H,GL_RGBA,GL_FLOAT,px.data());
  const bool ok=glOk("readback");detach();if(ok)img=classify(px);return ok;
}
bool writePpm(const char*prefix,int slotName,const std::vector<float>&px){
  std::vector<unsigned char> rgb(size_t(W)*H*3);for(size_t j=0;j<size_t(W)*H;++j)for(size_t k=0;k<3;++k){float v=px[j*4+k];rgb[j*3+k]=std::isfinite(v)?static_cast<unsigned char>(std::clamp(v,0.f,1.f)*255.f):0;}
  char name[2048];std::snprintf(name,sizeof name,"%s.%d.ppm",prefix,slotName);FILE*f=std::fopen(name,"wb");if(!f)return false;
  std::fprintf(f,"P6\n%d %d\n255\n",W,H);for(int y=H-1;y>=0;--y)std::fwrite(rgb.data()+size_t(y)*W*3,1,size_t(W)*3,f);return std::fclose(f)==0;
}

int cpuContract(){
  int checks=0;auto test=[&](bool b){++checks;return b;};
  // r4 metadata and lease checks (14), unchanged
  remixapi_dxvk_InteropInfo i={};bool ok=test(!metadata(i));
  i.imageMemory_Handle=1;i.allocationSize=uint64_t(W)*H*8;i.width=W;i.height=H;i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_RGBA16_SFLOAT;i.dxvkDoneSemaphore_Handle=2;i.clientDoneSemaphore_Handle=3;i.dxvkDoneSemaphore_ValueToWait=1;
  ok&=test(metadata(i));i.width=W+1;ok&=test(!metadata(i));i.width=W;i.allocationSize=256ull*1024*1024+1;ok&=test(!metadata(i));i.allocationSize=1;ok&=test(!metadata(i));i.allocationSize=W*H*8;i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_R32_SFLOAT;ok&=test(!metadata(i));i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_BGRA8_UNORM;ok&=test(metadata(i));i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_RGBA8_SRGB;ok&=test(metadata(i));i.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_RGBA8_UNORM;ok&=test(metadata(i));i.dxvkDoneSemaphore_ValueToWait=0;ok&=test(!metadata(i));
  const std::string nonce(32,'a');const std::string lease="{\"owner\":\"codex-einhander\",\"purpose\":\"private-modern-sdk-gl-probe\",\"lease_nonce\":\""+nonce+"\",\"parent_pid\":123}\n";
  ok&=test(ownedLease(lease,nonce));ok&=test(!ownedLease(lease,std::string(32,'b')));ok&=test(!ownedLease("{\"owner\":\"user-external-project\"}\n",nonce));ok&=test(!ownedLease(lease,""));
  // D1 basis: right = forward x up = (-1,0,0); orthonormal; official handedness det[right,up,forward] = -1
  const Basis b=officialBasis();
  ok&=test(b.right.x==-1.f&&b.right.y==0.f&&b.right.z==0.f);
  ok&=test(dot(b.right,b.up)==0.f&&dot(b.right,b.forward)==0.f&&dot(b.up,b.forward)==0.f);
  ok&=test(dot(cross(b.right,b.up),b.forward)==-1.f);
  ok&=test(cross(b.right,b.forward).x==b.up.x&&cross(b.right,b.forward).y==b.up.y&&cross(b.right,b.forward).z==b.up.z);
  // D3 timeline decisions
  ok&=test(waitAction(false,0,5)==WaitAction::Wait);ok&=test(waitAction(true,5,6)==WaitAction::Wait);
  ok&=test(waitAction(true,6,6)==WaitAction::SkipEqual);ok&=test(waitAction(true,6,5)==WaitAction::ErrorDecrease);
  ok&=test(waitAction(false,9,3)==WaitAction::Wait);   // after a (re)import the client waits on any value
  // D2 persistent import
  const ImportKey k{10,uint64_t(W)*H*8,W,H,RGBA16F};
  ok&=test(importNeeded(false,k,k));ok&=test(!importNeeded(true,k,k));
  {ImportKey x=k;x.handle=11;ok&=test(importNeeded(true,k,x));}{ImportKey x=k;x.size+=4096;ok&=test(importNeeded(true,k,x));}
  {ImportKey x=k;x.w=W+2;ok&=test(importNeeded(true,k,x));}{ImportKey x=k;x.h=H+2;ok&=test(importNeeded(true,k,x));}
  {ImportKey x=k;x.fmt=RGBA8;ok&=test(importNeeded(true,k,x));}
  // Oracle unchanged: black, green, magenta, non-finite
  std::vector<float> px(size_t(W)*H*4,0.f);Image black=classify(px);ok&=test(!oracle(black)&&black.nonblack==0&&black.finite==W*H);
  for(int j=0;j<501;++j){px[size_t(j)*4+1]=.8f;px[size_t(j)*4]=.02f;px[size_t(j)*4+2]=.02f;}Image green=classify(px);ok&=test(oracle(green)&&green.green==501);
  for(int j=0;j<500;++j){px[size_t(j)*4+1]=0.f;}Image g500=classify(px);ok&=test(!oracle(g500)&&g500.green==1);
  {std::vector<float> m(size_t(W)*H*4,0.f);for(int j=0;j<W*H;++j){m[size_t(j)*4+1]=.8f;}for(int j=0;j<W*H/10;++j){m[size_t(j)*4]=.9f;m[size_t(j)*4+1]=0.f;m[size_t(j)*4+2]=.9f;}ok&=test(!oracle(classify(m)));}
  {std::vector<float> n(size_t(W)*H*4,0.f);for(int j=0;j<W*H;++j)n[size_t(j)*4+1]=.8f;n[0]=NAN;ok&=test(!oracle(classify(n)));}
  // Readiness/capture state machine scenarios
  const Image valid=green,dark=black;Image grey=black;grey.nonblack=100;
  {Machine m;m.readyLimit=10;int f=0;double t=0;for(;f<20;++f,t+=.2)m.step(f,t,true,dark);  // 4 s of black: still waiting
   ok&=test(m.phase==Phase::Ready&&m.firstNonblackFrame<0);
   m.step(f,t,true,valid);ok&=test(m.phase==Phase::Settle&&m.firstValidFrame==20);
   int caps=0,lastSlot=-1;float offs[3]={0,0,0};for(++f,t+=.2;m.active()&&f<200;++f,t+=.2){const float o=m.offset();const int s=m.step(f,t,true,valid);if(s>=0){offs[s]=o;lastSlot=s;++caps;}}
   ok&=test(m.phase==Phase::Done&&caps==3&&lastSlot==2&&m.accepted==3);
   ok&=test(offs[0]==-2.f&&offs[1]==0.f&&offs[2]==2.f);}
  {Machine m;m.readyLimit=5;int f=0;double t=0;for(;m.active()&&f<100;++f,t+=.2)m.step(f,t,true,dark);
   ok&=test(m.phase==Phase::Fail&&std::strcmp(m.failure,"no_rt_output_within_ready_window")==0);}
  {Machine m;m.readyLimit=5;int f=0;double t=0;for(;m.active()&&f<100;++f,t+=.2)m.step(f,t,true,grey);
   ok&=test(m.phase==Phase::Fail&&std::strcmp(m.failure,"no_valid_green_within_ready_window")==0&&m.firstNonblackFrame==0);}
  {Machine m;m.readyLimit=10;m.step(0,0,true,valid);int f=1;double t=.2;for(int n=0;n<50;++n,++f,t+=.2)m.step(f,t,false,valid);  // skipped-equal frames
   ok&=test(m.phase==Phase::Settle&&m.settled==0&&m.skipped==50);}
  {Machine m;m.readyLimit=10;m.step(0,0,true,valid);int f=1,caps=0;double t=.2;for(;m.active()&&f<200;++f,t+=.2){if(m.step(f,t,true,f%2?valid:dark)>=0)++caps;}
   ok&=test(m.phase==Phase::Done&&caps==3&&m.accepted<3);}  // a failing capture is recorded, never accepted
  {Machine m;m.readyLimit=10;m.step(0,0,true,valid);int f=1;double t=.2;for(;m.active()&&f<400;++f,t+=.2)m.step(f,t,false,valid);
   ok&=test(m.phase==Phase::Fail&&std::strcmp(m.failure,"capture_window_exceeded")==0);}
  // r6 deadline-before-success controls: exact boundary, just inside, late valid after a long blocking frame, capture window
  {Machine m;m.readyLimit=10;m.step(0,9.999,true,valid);ok&=test(m.phase==Phase::Settle&&m.firstValidFrame==0);}
  {Machine m;m.readyLimit=10;m.step(0,10.0,true,valid);ok&=test(m.phase==Phase::Fail&&std::strcmp(m.failure,"no_interop_image_within_ready_window")==0&&m.firstValidFrame<0&&m.firstNonblackFrame<0);}
  {Machine m;m.readyLimit=10;m.step(0,1,true,grey);m.step(1,20,true,valid);ok&=test(m.phase==Phase::Fail&&std::strcmp(m.failure,"no_valid_green_within_ready_window")==0&&m.firstValidFrame<0&&m.firstNonblackFrame==0);}
  {Machine m;m.readyLimit=10;m.step(0,0,true,valid);int f=1;for(;f<=SETTLE;++f)m.step(f,.1*f,true,valid);const int s=m.step(f,20.0,true,valid);
   ok&=test(s==-1&&m.phase==Phase::Fail&&std::strcmp(m.failure,"capture_window_exceeded")==0&&m.accepted==0);}
  {Machine m;m.readyLimit=10;m.step(0,0,true,valid);int f=1;for(;f<=SETTLE;++f)m.step(f,.1*f,true,valid);const int s=m.step(f,19.999,true,valid);
   ok&=test(s==0&&m.phase==Phase::Settle&&m.accepted==1);}
  // r7 interop classification (official: handle 0/-1 = no image yet; last waited = -1 accepts value 0)
  {remixapi_dxvk_InteropInfo init={};init.dxvkDoneSemaphore_Handle=2;init.clientDoneSemaphore_Handle=3;
   remixapi_dxvk_InteropInfo v=init;v.imageMemory_Handle=10;v.allocationSize=uint64_t(W)*H*8;v.width=W;v.height=H;v.interopImageFormat=REMIXAPI_TEXTURE_FORMAT_RGBA16_SFLOAT;v.dxvkDoneSemaphore_ValueToWait=7;
   ok&=test(classifyInterop(v,init,false,0)==Interop::Image);
   {remixapi_dxvk_InteropInfo x=v;x.dxvkDoneSemaphore_Handle=0;ok&=test(classifyInterop(x,init,false,0)==Interop::Fatal);}
   {remixapi_dxvk_InteropInfo x=v;x.clientDoneSemaphore_Handle=4;ok&=test(classifyInterop(x,init,false,0)==Interop::Fatal);}
   {remixapi_dxvk_InteropInfo x=v;x.imageMemory_Handle=0;ok&=test(classifyInterop(x,init,true,5)==Interop::NoImage);}
   {remixapi_dxvk_InteropInfo x=v;x.imageMemory_Handle=~uint64_t(0);ok&=test(classifyInterop(x,init,false,0)==Interop::NoImage);}
   {remixapi_dxvk_InteropInfo x=v;x.width=W+1;ok&=test(classifyInterop(x,init,false,0)==Interop::Fatal);}
   {remixapi_dxvk_InteropInfo x=v;x.dxvkDoneSemaphore_ValueToWait=0;ok&=test(classifyInterop(x,init,false,0)==Interop::ZeroValue);
    ok&=test(classifyInterop(x,init,true,5)==Interop::Fatal);}}
  {const FramePlan a=planFor(Interop::NoImage,WaitAction::Wait),b=planFor(Interop::ZeroValue,WaitAction::Wait),c=planFor(Interop::Image,WaitAction::Wait),d=planFor(Interop::Image,WaitAction::SkipEqual);
   ok&=test(!a.wait&&!a.read&&!a.signalImage);ok&=test(!b.wait&&!b.read&&!b.signalImage);
   ok&=test(c.wait&&c.read&&c.signalImage);ok&=test(!d.wait&&!d.read&&d.signalImage);}
  // r7 not-ready frames: never counted (even with a 'valid' image), bounded by the deadlines
  {Machine m;m.readyLimit=10;int f=0;double t=0;for(;f<20;++f,t+=.2)m.stepKind(f,t,Obs::NotReady,valid);m.stepKind(f,t,Obs::Fresh,valid);
   ok&=test(m.phase==Phase::Settle&&m.notReady==20&&m.fresh==1&&m.firstValidFrame==20);}
  {Machine m;m.readyLimit=5;int f=0;double t=0;for(;m.active()&&f<100;++f,t+=.2)m.stepKind(f,t,Obs::NotReady,valid);
   ok&=test(m.phase==Phase::Fail&&std::strcmp(m.failure,"no_interop_image_within_ready_window")==0&&m.fresh==0&&m.firstValidFrame<0);}
  {Machine m;m.readyLimit=10;m.step(0,0,true,valid);int f=1;double t=.1;for(int n=0;n<50;++n,++f,t+=.1)m.stepKind(f,t,Obs::NotReady,valid);
   ok&=test(m.phase==Phase::Settle&&m.settled==0&&m.notReady==50&&m.skipped==0);}
  {Machine m;m.readyLimit=10;m.step(0,0,true,valid);int f=1;for(;f<=SETTLE;++f)m.step(f,.1*f,true,valid);
   const int nr=m.stepKind(f,.1*f,Obs::NotReady,valid);const int s=m.stepKind(f+1,.1*(f+1),Obs::Fresh,valid);
   ok&=test(nr==-1&&s==0&&m.accepted==1);}
  std::printf("{\"cpu_contract_checks\":%d,\"passed\":%s,\"revision\":\"r7\",\"dll_loaded\":false,\"gl_context\":false}\n",checks,ok?"true":"false");
  return ok?0:1;
}
}
int main(int argc,char**argv){
  if(argc==2&&!std::strcmp(argv[1],"--guard-contract")){
    const bool reserved=GetFileAttributesW(L"C:\\github\\Einhander\\remaster-audit\\comfy-authoring\\GPU-RESERVED")!=INVALID_FILE_ATTRIBUTES;
    const bool allowed=executionLease();std::printf("{\"reservation_exists\":%s,\"owned_execution_lease\":%s,\"gpu_started\":false,\"dll_loaded\":false}\n",reserved?"true":"false",allowed?"true":"false");return allowed?0:77;
  }
  // This CPU mode does not create a window, load a DLL or call any graphics API.
  if(argc==2&&!std::strcmp(argv[1],"--cpu-contract"))return cpuContract();
  int readyLimit=READY_DEFAULT;
  const bool shapeOk=(argc==3||(argc==5&&!std::strcmp(argv[3],"--ready-seconds")))&&!std::strcmp(argv[1],"--run-after-explicit-user-release");
  if(shapeOk&&argc==5){char*end=nullptr;const long v=std::strtol(argv[4],&end,10);if(!end||*end||v<READY_MIN||v>READY_MAX){std::puts("--ready-seconds must be an integer in 5..120");return 2;}readyLimit=int(v);}
  if(!shapeOk){std::puts("Private GPU probe is not enabled. CPU-only: --cpu-contract");return 2;}
  // Only the parent runner can provide a matching fresh owned reservation. A user marker, missing
  // marker, read failure or stale/foreign nonce refuses execution before creating any graphics state.
  if(!executionLease()){std::puts("{\"blocked\":\"no matching owned execution lease or user GPU reservation exists\",\"gpu_started\":false}");return 77;}
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);SetPriorityClass(GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS);
  SetProcessDPIAware(); // Local process only: fixed320x180 physical client size for the image oracle.
  WNDCLASSW wc={};wc.style=CS_OWNDC;wc.lpfnWndProc=windowProc;wc.hInstance=GetModuleHandleW(nullptr);wc.lpszClassName=L"EinhanderModernPrivateProbe";
  if(!RegisterClassW(&wc))return 3;RECT r={0,0,W,H};AdjustWindowRect(&r,WS_OVERLAPPEDWINDOW,FALSE);
  HWND win=CreateWindowW(wc.lpszClassName,L"Einhander private modern SDK qualification",WS_OVERLAPPEDWINDOW,40,40,r.right-r.left,r.bottom-r.top,nullptr,nullptr,wc.hInstance,nullptr);if(!win)return 4;
  HDC dc=GetDC(win);PIXELFORMATDESCRIPTOR pf={};pf.nSize=sizeof pf;pf.nVersion=1;pf.dwFlags=PFD_DRAW_TO_WINDOW|PFD_SUPPORT_OPENGL|PFD_DOUBLEBUFFER;pf.iPixelType=PFD_TYPE_RGBA;pf.cColorBits=32;
  int pix=ChoosePixelFormat(dc,&pf);if(!pix||!SetPixelFormat(dc,pix,&pf))return 5;HGLRC ctx=wglCreateContext(dc);if(!ctx||!wglMakeCurrent(dc,ctx))return 6;
  const char*renderer=reinterpret_cast<const char*>(glGetString(GL_RENDERER));std::printf("{\"gl_renderer\":\"%s\"}\n",renderer?renderer:"");std::fflush(stdout);if(!renderer||!std::strstr(renderer,"3090 Ti"))return 7;
  Gl gl={};if(!init(gl))return 8;
  // Owned offscreen baseline: first prove GL readback independently of SDK output.
  GLuint fb=0,baseline=0;gl.genFramebuffer(1,&fb);gl.bindFramebuffer(FBO,fb);glGenTextures(1,&baseline);glBindTexture(GL_TEXTURE_2D,baseline);glTexImage2D(GL_TEXTURE_2D,0,RGBA8,W,H,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);gl.attach(FBO,COLOR,GL_TEXTURE_2D,baseline,0);if(gl.framebufferStatus(FBO)!=COMPLETE)return 9;
  glDrawBuffer(COLOR);glReadBuffer(COLOR);glClearColor(1,0,1,1);glClear(GL_COLOR_BUFFER_BIT);std::vector<unsigned char> base(size_t(W)*H*4);glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,base.data());int magenta=0;for(int j=0;j<W*H;++j)if(base[size_t(j)*4]==255&&base[size_t(j)*4+1]==0&&base[size_t(j)*4+2]==255)magenta++;if(!glOk("baseline")||magenta!=W*H)return 10;
  std::printf("{\"owned_readback_magenta_pixels\":%d}\n",magenta);std::fflush(stdout);gl.bindFramebuffer(FBO,0);ShowWindow(win,SW_SHOWNOACTIVATE);
  // Record (never modify) the cache/config policy the parent runner chose.
  std::printf("{\"cache_policy\":{\"DXVK_STATE_CACHE_PATH\":\"%s\",\"DXVK_CONFIG_FILE\":\"%s\",\"DXVK_LOG_PATH\":\"%s\",\"RTX_ENABLE_ASYNC_COMPILATION\":\"%s\",\"probe_modifies_caches\":false},\"ready_limit_seconds\":%d}\n",
    jsonText(std::getenv("DXVK_STATE_CACHE_PATH")).c_str(),jsonText(std::getenv("DXVK_CONFIG_FILE")).c_str(),jsonText(std::getenv("DXVK_LOG_PATH")).c_str(),jsonText(std::getenv("RTX_ENABLE_ASYNC_COMPILATION")).c_str(),readyLimit);std::fflush(stdout);
  const wchar_t*dir=L"C:\\github\\Einhander\\remaster-audit\\runtime-review\\gpu-texture-remix-20261114\\sdk-v016-release\\win64";SetDllDirectoryW(dir);
  remixapi_Interface api={};HMODULE dll=nullptr;if(!call("InitializeLibrary",remixapi_lib_loadRemixDllAndInitialize(L"C:\\github\\Einhander\\remaster-audit\\runtime-review\\gpu-texture-remix-20261114\\sdk-v016-release\\win64\\d3d9.dll",&api,&dll)))return 11;
  if(!api.Startup||!api.Submit||!api.Present||!api.dxvk_GetInteropInfo||!api.Shutdown)return 12;
  remixapi_StartupInfo si={};si.sType=REMIXAPI_STRUCT_TYPE_STARTUP_INFO;si.hwnd=win;si.interopImage=1;si.useRemixOwnedChildWindow=1;si.combineGuiInFinalColor=0;
  const double startupBegin=seconds();
  if(!call("Startup",api.Startup(&si)))return 13;
  std::printf("{\"startup_seconds\":%.3f}\n",seconds()-startupBegin);std::fflush(stdout);
  int rc=0;remixapi_dxvk_InteropInfo initial={};GLuint done=0,client=0;
  if(!call("InteropInfo-initial",api.dxvk_GetInteropInfo(&initial))||!importSem(gl,initial.dxvkDoneSemaphore_Handle,done)||!importSem(gl,initial.clientDoneSemaphore_Handle,client))rc=14;
  remixapi_MaterialInfoOpaqueEXT op={};op.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO_OPAQUE_EXT;op.albedoConstant={.02f,.8f,.02f};op.opacityConstant=1;op.roughnessConstant=.4f;op.alphaTestType=7;
  remixapi_MaterialInfo mi={};mi.sType=REMIXAPI_STRUCT_TYPE_MATERIAL_INFO;mi.pNext=&op;mi.hash=0xe1a01601;mi.emissiveIntensity=2;mi.emissiveColorConstant={.02f,.8f,.02f};remixapi_MaterialHandle material=nullptr;
  if(!rc&&!call("CreateMaterial",api.CreateMaterial(&mi,&material)))rc=15;
  remixapi_HardcodedVertex vertices[3]={};const float positions[3][3]={{-3,-2,8},{0,2,8},{3,-2,8}};for(int j=0;j<3;++j){std::memcpy(vertices[j].position,positions[j],sizeof positions[j]);vertices[j].normal[2]=-1;vertices[j].color=0xffffffff;}
  remixapi_MeshInfoSurfaceTriangles surface={};surface.vertices_values=vertices;surface.vertices_count=3;surface.material=material;remixapi_MeshInfo meshinfo={};meshinfo.sType=REMIXAPI_STRUCT_TYPE_MESH_INFO;meshinfo.hash=0xe1a01602;meshinfo.surfaces_values=&surface;meshinfo.surfaces_count=1;remixapi_MeshHandle mesh=nullptr;
  if(!rc&&!call("CreateMesh",api.CreateMesh(&meshinfo,&mesh)))rc=16;
  U64 clientValue=0,lastDone=0;bool haveLast=false,imported=false;ImportKey have{0,0,0,0,0};GLuint memory=0,tex=0;int imports=0,noImageFrames=0,zeroValueFrames=0;
  auto dropImport=[&]{if(tex)glDeleteTextures(1,&tex);if(memory)gl.deleteMemory(1,&memory);tex=0;memory=0;imported=false;};
  auto finishSubmitted=[&](GLuint image,bool waitOnClient=true){
    const GLenum layout=GENERAL;++clientValue;gl.semaphoreValue(client,VALUE_NV,&clientValue);
    gl.signal(client,0,nullptr,image?1:0,image?&image:nullptr,image?&layout:nullptr);
    const bool signalled=glOk("client-signal");glFlush();
    auto present=remixapi_PresentInfo_init();present.interopFlipY=1;
    // An error path still pairs a successful Submit with Present. A failed signal must
    // never request a wait for an unsignalled value; the frame cannot qualify either way.
    present.clientDoneSemaphore_ValueToWait=signalled&&waitOnClient?clientValue:0;
    return call("Present",api.Present(&present))&&signalled;
  };
  const Basis basis=officialBasis();Machine sm;sm.readyLimit=readyLimit;const double loopBegin=seconds();int frame=0;std::vector<float> px;
  for(;!rc&&sm.active()&&frame<FRAME_CAP;++frame){pump();remixapi_CameraInfoParameterizedEXT cp={};cp.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO_PARAMETERIZED_EXT;cp.position={0,0,0};cp.forward={basis.forward.x,basis.forward.y,basis.forward.z};cp.up={basis.up.x,basis.up.y,basis.up.z};cp.right={basis.right.x,basis.right.y,basis.right.z};cp.fovYInDegrees=60;cp.aspect=float(W)/H;cp.nearPlane=.1f;cp.farPlane=100;
    const float offset=sm.offset();
    remixapi_CameraInfo camera={};camera.sType=REMIXAPI_STRUCT_TYPE_CAMERA_INFO;camera.pNext=&cp;camera.type=REMIXAPI_CAMERA_TYPE_WORLD;remixapi_InstanceInfo instance={};instance.sType=REMIXAPI_STRUCT_TYPE_INSTANCE_INFO;instance.mesh=mesh;instance.doubleSided=1;instance.transform={{{1,0,0,offset},{0,1,0,0},{0,0,1,0}}};auto submit=remixapi_SubmitInfo_init();
    if(!call("SetupCamera",api.SetupCamera(&camera))||!call("DrawInstance",api.DrawInstance(&instance))||!call("Submit",api.Submit(&submit))){rc=17;break;}
    remixapi_dxvk_InteropInfo info={};if(!call("InteropInfo",api.dxvk_GetInteropInfo(&info))){rc=18;finishSubmitted(0,false);break;}
    const bool sameImage=imported&&imagePresent(info)&&imageMetaValid(info)&&!importNeeded(imported,have,keyOf(info));
    const Interop kind=classifyInterop(info,initial,haveLast&&sameImage,lastDone);
    if(kind==Interop::Fatal){std::printf("{\"interop_contract_violation\":{\"frame\":%d,\"image\":%llu,\"value\":%llu,\"width\":%d,\"height\":%d,\"format\":%d}}\n",frame,U64(info.imageMemory_Handle),U64(info.dxvkDoneSemaphore_ValueToWait),int(info.width),int(info.height),int(info.interopImageFormat));std::fflush(stdout);rc=18;finishSubmitted(0,false);break;}
    WaitAction act=WaitAction::Wait;
    if(kind==Interop::Image){
    const ImportKey want=keyOf(info);
    if(importNeeded(imported,have,want)){
      dropImport();HANDLE handle=duplicate(info.imageMemory_Handle);if(!handle){rc=19;finishSubmitted(0);break;}
      gl.createMemory(1,&memory);gl.importMemory(memory,info.allocationSize,HANDLE_WIN32,handle);CloseHandle(handle);glGenTextures(1,&tex);glBindTexture(GL_TEXTURE_2D,tex);gl.textureStorage(GL_TEXTURE_2D,1,want.fmt,W,H,memory,0);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
      if(!glOk("import-image")){rc=19;finishSubmitted(0);break;}
      imported=true;have=want;haveLast=false;++imports;std::printf("{\"interop_import\":%d,\"frame\":%d,\"format\":%d,\"gl_format\":%u,\"allocation\":%llu}\n",imports,frame,int(info.interopImageFormat),want.fmt,U64(info.allocationSize));std::fflush(stdout);
    }
    act=waitAction(haveLast,lastDone,info.dxvkDoneSemaphore_ValueToWait);
    if(act==WaitAction::ErrorDecrease){std::printf("{\"dxvk_done_decreased\":{\"last\":%llu,\"next\":%llu}}\n",lastDone,U64(info.dxvkDoneSemaphore_ValueToWait));rc=18;finishSubmitted(0,false);break;}
    }else if(kind==Interop::NoImage)++noImageFrames;else ++zeroValueFrames;
    const FramePlan plan=planFor(kind,act);
    if(plan.wait){const GLenum layout=GENERAL;U64 waitValue=info.dxvkDoneSemaphore_ValueToWait;gl.semaphoreValue(done,VALUE_NV,&waitValue);gl.wait(done,0,nullptr,1,&tex,&layout);
      if(!glOk("import-wait")){rc=20;finishSubmitted(tex);break;}lastDone=waitValue;haveLast=true;}
    Image img;if(plan.read&&!readback(tex,fb,gl,px,img)){rc=24;finishSubmitted(tex);break;}
    const double t=seconds()-loopBegin;const int slot=sm.stepKind(frame,t,kind!=Interop::Image?Obs::NotReady:plan.read?Obs::Fresh:Obs::SkipEqual,img);
    if(slot>=0){const bool written=writePpm(argv[2],SLOT_NAME[slot],px);
      std::printf("{\"capture_slot\":%d,\"frame\":%d,\"seconds\":%.3f,\"offset_x\":%.1f,\"finite_pixels\":%d,\"green_pixels\":%d,\"fallback_magenta_pixels\":%d,\"nonblack_pixels\":%d,\"accepted\":%s,\"written\":%s}\n",SLOT_NAME[slot],frame,t,double(offset),img.finite,img.green,img.magenta,img.nonblack,oracle(img)?"true":"false",written?"true":"false");std::fflush(stdout);
      if(!written&&!rc)rc=34;}
    if(!finishSubmitted(plan.signalImage?tex:0))rc=21;Sleep(FRAME_SLEEP_MS);
  }
  std::printf("{\"readiness\":{\"phase\":\"%s\",\"failure\":\"%s\",\"frames\":%d,\"fresh_frames\":%d,\"skipped_equal_frames\":%d,\"not_ready_frames\":%d,\"not_ready_no_image_frames\":%d,\"not_ready_zero_value_frames\":%d,\"first_nonblack_frame\":%d,\"first_nonblack_seconds\":%.3f,\"first_valid_frame\":%d,\"first_valid_seconds\":%.3f,\"accepted_images\":%d,\"imports\":%d,\"ready_limit_seconds\":%d}}\n",
    sm.phase==Phase::Done?"done":sm.phase==Phase::Fail?"fail":"incomplete",sm.failure,frame,sm.fresh,sm.skipped,sm.notReady,noImageFrames,zeroValueFrames,sm.firstNonblackFrame,sm.firstNonblackSeconds,sm.firstValidFrame,sm.firstValidSeconds,sm.accepted,imports,readyLimit);std::fflush(stdout);
  if(!rc&&sm.phase==Phase::Fail)rc=std::strcmp(sm.failure,"capture_window_exceeded")?31:32;
  if(!rc&&sm.phase!=Phase::Done)rc=33;   // frame cap reached
  if(!rc&&sm.accepted!=3)rc=22;
  // r4 exit codes kept: 25 DestroyMesh, 26 DestroyMaterial, 27 destroy-gl, 28 context, 29 window, 30 Shutdown deadline.
  // r5 additions: 24 readback, 31 ready window, 32 capture window, 33 frame cap, 34 capture file.
  if(mesh&&!call("DestroyMesh",api.DestroyMesh(mesh))&&!rc)rc=25;if(material&&!call("DestroyMaterial",api.DestroyMaterial(material))&&!rc)rc=26;glFinish();
  dropImport();if(done)gl.deleteSemaphore(1,&done);if(client)gl.deleteSemaphore(1,&client);
  gl.deleteFramebuffer(1,&fb);glDeleteTextures(1,&baseline);
  if(!glOk("destroy-gl")&&!rc)rc=27;
  if(!wglMakeCurrent(nullptr,nullptr)&&!rc)rc=28;if(!wglDeleteContext(ctx)&&!rc)rc=28;
  ReleaseDC(win,dc);if(!DestroyWindow(win)&&!rc)rc=29;pump();
  // Follow the official client's window/context-before-native-shutdown order on this thread.
  std::puts("{\"call\":\"Shutdown-enter\"}");std::fflush(stdout);
  std::atomic<bool> stopped{false};std::thread deadline([&]{for(int n=0;n<300&&!stopped.load();++n)Sleep(50);if(!stopped.load()){std::puts("{\"shutdown_timeout_seconds\":15}");std::fflush(stdout);ExitProcess(30);}});
  const double shutdownBegin=seconds();
  if(!call("Shutdown",api.Shutdown())&&!rc)rc=23;stopped.store(true);deadline.join();
  std::printf("{\"shutdown_seconds\":%.3f}\n",seconds()-shutdownBegin);std::fflush(stdout);
  UnregisterClassW(wc.lpszClassName,wc.hInstance);FreeLibrary(dll);
  std::printf("{\"exit\":%d,\"accepted_images\":%d,\"gameplay\":false,\"revision\":\"r7\"}\n",rc,sm.accepted);return rc;
}
