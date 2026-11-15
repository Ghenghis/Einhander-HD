"""Read one prepared executable and its source/config hooks without executing it."""
from pathlib import Path
import datetime as dt,hashlib,json,psutil,struct
R=Path('C:/github/Einhander');N=Path(__file__).resolve().parent
E=R/'remaster-audit/dev-center-evidence/stage1-completion-20261112'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity([11])
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(data):return hashlib.sha256(data).hexdigest()
exe=E/'v68-unassisted-r1/hd-on_rewind-off/runtime/Einhander_Recompiled.exe'
raw=exe.read_bytes();need(sha(raw)=='5c1436ff778701d981410da61046aca60c0da60215a5f724523197b58199dfaa','prepared executable changed')
def u16(at):return struct.unpack_from('<H',raw,at)[0]
def u32(at):return struct.unpack_from('<I',raw,at)[0]
need(raw[:2]==b'MZ','not PE');pe=u32(0x3c);need(raw[pe:pe+4]==b'PE\0\0','bad PE')
coff=pe+4;opt=coff+20;need(u16(opt)==0x20b and u16(coff)==0x8664,'expected AMD64 PE32+')
sections=[];sec=opt+u16(coff+16)
for i in range(u16(coff+2)):
    at=sec+40*i;sections.append(dict(virtual_size=u32(at+8),rva=u32(at+12),raw_size=u32(at+16),raw_offset=u32(at+20)))
def offset(rva):
    for s in sections:
        delta=rva-s['rva']
        if 0<=delta<s['raw_size']:
            at=s['raw_offset']+delta;need(at<len(raw),'RVA outside file');return at
    raise ValueError('RVA not backed by raw section')
def string(at):
    end=raw.find(b'\0',at,min(len(raw),at+1024));need(end>=at,'unterminated PE name');return raw[at:end].decode('ascii')
imports=[];import_rva=u32(opt+112+8);import_size=u32(opt+112+12)
if import_rva:
    base=offset(import_rva)
    for i in range(min(import_size//20+1,4096)):
        at=base+20*i;values=struct.unpack_from('<5I',raw,at)
        if not any(values):break
        original,_,_,name,thunk=values;symbols=[];table=offset(original or thunk)
        for k in range(65536):
            value=struct.unpack_from('<Q',raw,table+8*k)[0]
            if not value:break
            symbols.append('#'+str(value&0xffff) if value>>63 else string(offset(value)+2))
        imports.append(dict(dll=string(offset(name)),symbols=symbols))
files=[E/'sampling-build-v58-frame-phases/main.cpp',
       E/'sampling-build-v68-recorder-reserve-r1/src/gpu_gl_renderer.c',
       R/'windows-x64/psxrecomp/runtime/src/gpu_vk_renderer.c',
       E/'v68-unassisted-r1/hd-on_rewind-off/runtime/settings.toml']
pins=[];hooks=[]
terms=('SDL_GL_CONTEXT_PROFILE','SDL_GL_CONTEXT_MAJOR_VERSION','SDL_GL_CONTEXT_MINOR_VERSION',
       'configure_core_gl_context_attributes();','g_gl_active = (gl_renderer_init_context',
       'SDL_GL_CreateContext','glGetString(GL_VERSION)','SDL_GL_SwapWindow(s_win)',
       'depthTestEnable =','SDL_Vulkan_LoadLibrary(NULL)','const GpuRenderBackend VK_BACKEND','renderer          =')
for path in files:
    data=path.read_bytes();relative=path.relative_to(R).as_posix();pins.append(dict(path=relative,sha256=sha(data),bytes=len(data)))
    for i,line in enumerate(data.decode('utf-8').splitlines(),1):
        if any(term in line for term in terms):hooks.append(dict(path=relative,line=i,text=line.strip()))
out=N/'renderer-api-hook-map-r1';out.mkdir(exist_ok=False)
result=dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),metadata_only=True,
    executable=dict(path=exe.relative_to(R).as_posix(),sha256=sha(raw),bytes=len(raw),machine='AMD64',imports=imports),
    source_and_configuration=pins,hooks=hooks,
    selected_prepared_renderer='opengl',requested_gl_context=dict(major=3,minor=3,profile='core'),
    actual_running_context_version=None,actual_running_context_profile=None,executable_started=False,
    gpu_run=False,game_run=False,dlss_qualified=False,ray_tracing_qualified=False,
    existing_vulkan='Real implementation behind PSX_HAVE_VULKAN; runtime loader, geometry and swapchain. Header status comment is obsolete.',
    depth_limit='Vulkan depth test/write disabled; its depth-stencil allocation mirrors PSX mask bits, not qualified 3D depth.',
    hd_parity='No hd_texture/hd_skin identifiers in targeted canonical Vulkan file search; full HD/material/UI parity not audited.',
    inference_limits=['Imports show linked availability, not the active rendering API; Vulkan is dynamically loaded.',
        'Source/config requests do not establish actual running context or physical GPU identity.',
        'No dynamic LoadLibrary inventory or GPU capture was performed.'],
    official_sources=[
        'https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS.md',
        'https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_G.md',
        'https://github.com/baldurk/renderdoc/blob/v1.x/README.md'],
    next_hooks=['Keep existing native/HD paths and complete actual owned present/adapter/profile observation.',
        'Reuse current phase stamps around swap; add timings only where asset/decode/upload/audio scopes are missing.',
        'Review existing Vulkan HD/material/UI parity before considering a backend switch.',
        'Bind ordered capture, exact material content and completion/invalidation before compositor/3D transport.',
        'DLSS needs supported API integration plus correct depth, dense motion, camera constants and resource lifecycle; FG also needs HUD/UI handling.'])
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(out=str(out),executable_sha256=sha(raw),import_dlls=[i['dll'] for i in imports],hook_count=len(hooks),game_run=False,gpu_run=False)))
