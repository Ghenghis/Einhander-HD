#define main einhander_unused_runtime_main
#include "../windows-x64/psxrecomp/runtime/src/main.cpp"
#undef main
extern "C" int hd_gpu_cache_regression(const char*);
extern "C" int hd_native_edge_regression(const char*);
int main(int argc,char**argv) {
    if((argc!=2&&argc!=3) || SDL_Init(SDL_INIT_VIDEO)!=0)return 2;
    SDL_Window*window=SDL_CreateWindow("HD GPU cache regression",0,0,320,240,SDL_WINDOW_OPENGL|SDL_WINDOW_HIDDEN);
    if(!window)return 3;
    gr_set_backend(GR_BACKEND_OPENGL);gpu_init();gr_set_scale(4);
    gl_renderer_set_cpu_auth_dual(0); // Explicitly apply the isolated environment policy.
    if(!gl_renderer_init_context(window))return 4;
    gpu_write_gp0(0xE3000000);gpu_write_gp0(0xE407FFFF);gpu_write_gp0(0xE5000000);
    return argc==3?hd_native_edge_regression(argv[1]):hd_gpu_cache_regression(argv[1]);
}
