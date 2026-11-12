// Native contract harness: exact exported API functions extracted from the
// renderer + exact production debug handler, with CPU renderer state fixtures.
// No SDL context, GL operation, runtime launch, or filesystem mutation occurs.
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "gpu_gl_renderer.h"
#include "gpu_render.h"
#include "hd_skin_live.h"
#include "hd_skin_detail.h"
#include "hd_texture_pack.h"

static HdSkinConfig s_hd_skin,s_hd_skin_enemy;
typedef struct {HdSkinDetailConfig config;unsigned texture;int width,height;} HdSkinDetailTexture;
static HdSkinDetailTexture s_hd_detail_player,s_hd_detail_enemy;
static void *s_ctx;
static HdTexturePack *s_hd_pack;
static int s_raster_ok,s_hd_state;
static unsigned s_hd_prog;
static uint64_t s_hd_live_generation,s_frame_count=1234;
static GrBackend test_backend=GR_BACKEND_OPENGL;
GrBackend gr_backend(void){return test_backend;}
static void *hd_tex_find(uint32_t texture,uint32_t palette){
    return ((texture==0x6BCA3D83u && palette==0xD298C690u) ||
            (texture==0x724E77DAu && palette==0x21FDE894u) ||
            (texture==0xE584DC41u && palette==0x12345678u))?(void*)1:nullptr;
}
int hd_texture_pack_lookup(const HdTexturePack *pack,uint32_t texture,uint32_t palette,HdTexturePackEntry *out){
    if(!pack)return HD_TEXTURE_LOOKUP_ERROR;
    if(texture==0xFACE0000u && palette==1u)return HD_TEXTURE_LOOKUP_AMBIGUOUS;
    if(hd_tex_find(texture,palette) ||
        (texture>=0x20000000u && texture<0x20000100u && palette==0x30000000u+(texture-0x20000000u))){
        if(out){std::memset(out,0,sizeof *out);out->texture_hash=texture;out->palette_hash=palette;out->replacement_path="fixture.png";}
        return HD_TEXTURE_LOOKUP_FOUND;
    }
    return HD_TEXTURE_LOOKUP_NONE;
}

#include "hd_skin_live_renderer_api.h" // exact compiled API source, not a reimplementation

static char response[8192];
static int response_required=0;
static int requests=0,checks=0,failures=0;
static void send_fmt(const char *format,...){va_list args;va_start(args,format);response_required=std::vsnprintf(response,sizeof response,format,args);va_end(args);}
static void send_err(int id,const char *message){send_fmt("{\"id\":%d,\"ok\":false,\"error\":\"%s\"}",id,message);}
#include "hd_skin_live_debug.h"

static void check(bool value,const char*label){++checks;if(!value){++failures;std::fprintf(stderr,"FAIL %s\n",label);}}
static void reset(){
    hd_skin_config_parse(&s_hd_skin,"aurora-teal","724E77DA-21FDE894,7E3ADD56-21FDE894,B16492B1-21FDE894,E2F3477C-21FDE894","0.75");
    hd_skin_config_parse_channel(&s_hd_skin_enemy,"gold-obsidian",nullptr,"0.65",1);
    std::memset(&s_hd_detail_player,0,sizeof s_hd_detail_player);std::memset(&s_hd_detail_enemy,0,sizeof s_hd_detail_enemy);
    hd_skin_detail_parse(&s_hd_detail_player.config,"player.png",nullptr,nullptr);
    hd_skin_detail_parse(&s_hd_detail_enemy.config,"enemy.png",nullptr,nullptr);
    s_hd_detail_player.texture=11;s_hd_detail_enemy.texture=22;
    s_ctx=(void*)1;s_raster_ok=1;s_hd_state=1;s_hd_pack=(HdTexturePack*)1;s_hd_prog=7;
    test_backend=GR_BACKEND_OPENGL;s_hd_live_generation=0;response[0]=0;
}
static void request(const char *json){++requests;response[0]=0;handle_skin_material(9,json);}
static void rejected_without_mutation(const char *json){
    const auto player=s_hd_skin,enemy=s_hd_skin_enemy;
    const auto pdetail=s_hd_detail_player,edetail=s_hd_detail_enemy;
    uint64_t generation=s_hd_live_generation;
    request(json);
    check(std::strstr(response,"\"ok\":false")!=nullptr,"rejected request reports failure");
    check(!std::memcmp(&player,&s_hd_skin,sizeof player),"player unchanged on rejected request");
    check(!std::memcmp(&enemy,&s_hd_skin_enemy,sizeof enemy),"enemy unchanged on rejected request");
    check(!std::memcmp(&pdetail,&s_hd_detail_player,sizeof pdetail)&&!std::memcmp(&edetail,&s_hd_detail_enemy,sizeof edetail),"detail ownership unchanged");
    check(generation==s_hd_live_generation,"generation unchanged on rejection");
}

int main(){
    reset();GlSkinMaterialState state{};
    check(gl_renderer_skin_material_get(&state)&&state.ready&&state.opengl_ready&&state.hd_ready,"initialized OpenGL HD readiness");
    check(state.player.key_count==4&&state.enemy.key_count==6,"configured key subsets exposed");
    check(state.player.detail_active&&state.enemy.detail_active,"existing detail flags exposed");
    request("{\"cmd\":\"skin_material\"}");
    check(std::strstr(response,"\"applied\":false")&&std::strstr(response,"\"supported_profiles\":[\"stock\""),"read-only response metadata");
    check(s_hd_live_generation==0,"read-only request has no commit");
    std::string sample_get=response;
    request("{\"cmd\":\"skin_material\",\"player_profile\":\"neon-circuit\",\"player_strength_percent\":100,\"enemy_profile\":\"crimson-regalia\",\"enemy_strength_percent\":42}");
    check(std::strstr(response,"\"ok\":true")&&std::strstr(response,"\"applied\":true"),"atomic setter succeeds");
    check(s_hd_skin.profile==hd_skin_find_profile("neon-circuit")&&s_hd_skin_enemy.profile==hd_skin_find_profile("crimson-regalia"),"both selected profiles committed");
    check(s_hd_live_generation==1,"commit generation advances once");
    check(s_hd_skin.key_count==4&&s_hd_skin_enemy.key_count==6,"key subset counts immutable");
    std::string sample_set=response;
    request("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"6BCA3D83-D298C690\",\"preserve_accents\":true}");
    check(std::strstr(response,"\"ok\":true") && s_hd_skin_enemy.diagnostic_scope,"resident exact key diagnostic accepted");
    check(hd_skin_key_matches(&s_hd_skin_enemy,0x6BCA3D83u,0xD298C690u) && !hd_skin_key_matches(&s_hd_skin_enemy,0x3594C110u,0x527B28B9u),"diagnostic replaces effective scope only");
    check(s_hd_skin_enemy.key_count==6 && s_hd_skin_enemy.keys[0].texture==0x3594C110u,"configured allowlist retained");
    gl_renderer_skin_material_get(&state);
    check(state.enemy.key_count==1 && !state.enemy.detail_active && state.enemy.diagnostic_scope,"temporary diagnostic is color-only and explicit");
    check(state.player.preserve_accents && state.enemy.preserve_accents,"accent policy changes both channels atomically");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"12345678-12345678\"}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"player_profile\":\"toxic-lime\",\"player_strength_percent\":99,\"enemy_profile\":\"neon-circuit\",\"enemy_strength_percent\":99,\"diagnostic_enemy_keys\":\"12345678-12345678\",\"preserve_accents\":false}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"E584DC41-12345678\"}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"724E77DA-21FDE894\"}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"6BCA3D83-D298C690,6BCA3D83-D298C690\"}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"6BCA3D83-D298C690,\"}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"preserve_accents\":1}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"preserve_accents\":true,\"preserve_accents\":false}");
    request("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"configured\",\"preserve_accents\":false}");
    gl_renderer_skin_material_get(&state);
    check(!s_hd_skin_enemy.diagnostic_scope && state.enemy.key_count==6 && state.enemy.detail_active,"configured reset restores original scope and detail");
    check(!state.player.preserve_accents && !state.enemy.preserve_accents,"accent preservation is explicitly reversible");
    HdSkinKey parsed[HD_SKIN_MAX_DIAGNOSTIC_KEYS];int parsed_count=0;
    check(!hd_skin_diagnostic_parse("10000000-00000001,10000001-00000001,10000002-00000001,10000003-00000001,10000004-00000001,10000005-00000001,10000006-00000001,10000007-00000001",parsed,&parsed_count)&&parsed_count==8,"eight-key diagnostic boundary accepted");
    check(HD_SKIN_MAX_KEYS==8 && HD_SKIN_MAX_DIAGNOSTIC_KEYS==128 && GL_SKIN_DIAGNOSTIC_KEYS_MAX==128,"configured maximum unchanged; diagnostic maximum128");
    std::string player_csv,enemy_csv,too_many;
    for(int i=0;i<256;++i){char key[32];std::snprintf(key,sizeof key,"%08X-%08X",0x20000000u+i,0x30000000u+i);
        std::string &csv=i<128?player_csv:enemy_csv;if(!csv.empty())csv+=",";csv+=key;}
    check(!hd_skin_diagnostic_parse(player_csv.c_str(),parsed,&parsed_count)&&parsed_count==128,"128 exact keys accepted");
    too_many=player_csv+",20000080-30000080";
    check(hd_skin_diagnostic_parse(too_many.c_str(),parsed,&parsed_count)!=nullptr,"129th diagnostic key rejected");
    check(!hd_tex_find(0x20000000u,0x30000000u),"registered nonresident fixture has no GPU texture");
    std::string max_request="{\"cmd\":\"skin_material\",\"diagnostic_player_keys\":\""+player_csv+"\",\"diagnostic_enemy_keys\":\""+enemy_csv+"\",\"preserve_accents\":true}";
    check(max_request.size()<8192,"maximum dual-channel request fits production8192byte receive bound");
    request(max_request.c_str());gl_renderer_skin_material_get(&state);
    check(std::strstr(response,"\"ok\":true") && state.player.key_count==128 && state.enemy.key_count==128,"registered nonresident palettes accepted in both128key channels");
    check(response_required>0 && response_required<(int)sizeof response,"maximum dual-channel response not truncated");
    check(player_csv==state.player.keys && enemy_csv==state.enemy.keys,"maximum key strings roundtrip without truncation");
    check(!state.player.detail_active && !state.enemy.detail_active,"both temporary scopes disable detail");
    std::string sample_maximum_set=response;
    rejected_without_mutation(("{\"cmd\":\"skin_material\",\"diagnostic_player_keys\":\""+too_many+"\"}").c_str());
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"FACE0000-00000001\"}");
    rejected_without_mutation("{\"cmd\":\"skin_material\",\"diagnostic_enemy_keys\":\"20000000-30000000\"}");
    rejected_without_mutation(("{\"cmd\":\"skin_material\",\"diagnostic_player_keys\":\""+player_csv+",\"}").c_str());
    request("{\"cmd\":\"skin_material\",\"diagnostic_player_keys\":\"configured\",\"diagnostic_enemy_keys\":\"configured\"}");
    gl_renderer_skin_material_get(&state);
    check(state.player.key_count==4 && state.enemy.key_count==6 && !state.player.diagnostic_scope && !state.enemy.diagnostic_scope,"128key scopes restore exact launched subsets");
    check(state.player.detail_active && state.enemy.detail_active,"configured restore resumes both original detail maps");
    const char *invalid[]={
        "{}","{\"id\":1}","{\"cmd\":\"other\"}","{\"cmd\":\"skin_material\",}",
        "{\"cmd\":\"skin_material\"} trailing","{\"cmd\":\"skin_material\",\"unknown\":1}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\"}",
        "{\"cmd\":\"skin_material\",\"player_strength_percent\":25}",
        "{\"cmd\":\"skin_material\",\"cmd\":\"skin_material\"}",
        "{\"cmd\":\"skin_material\",\"id\":2147483648}",
        "{\"cmd\":\"skin_material\",\"id\":-2147483649}",
        "{\"cmd\":\"skin_material\",\"id\":01}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":1.5,\"enemy_profile\":\"stock\",\"enemy_strength_percent\":20}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":\"75\",\"enemy_profile\":\"stock\",\"enemy_strength_percent\":20}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":true,\"enemy_profile\":\"stock\",\"enemy_strength_percent\":20}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":{},\"enemy_profile\":\"stock\",\"enemy_strength_percent\":20}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":101,\"enemy_profile\":\"stock\",\"enemy_strength_percent\":20}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":75,\"enemy_profile\":\"stock\",\"enemy_strength_percent\":-1}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":75,\"enemy_profile\":\"invalid\",\"enemy_strength_percent\":20}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"invalid\",\"player_strength_percent\":75,\"enemy_profile\":\"gold-obsidian\",\"enemy_strength_percent\":20}",
        "{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-teal\",\"player_strength_percent\":75,\"enemy_profile\":\"stock\",\"enemy_strength_percent\":20,\"enemy_strength_percent\":50}"
    };
    for(auto json:invalid)rejected_without_mutation(json);
    const char *valid_set="{\"cmd\":\"skin_material\",\"player_profile\":\"aurora-gilt\",\"player_strength_percent\":75,\"enemy_profile\":\"gold-obsidian\",\"enemy_strength_percent\":75}";
    for(int unavailable=0;unavailable<9;++unavailable){
        reset();
        if(unavailable==0)test_backend=GR_BACKEND_SOFTWARE;
        else if(unavailable==1)test_backend=GR_BACKEND_VULKAN;
        else if(unavailable==2)s_ctx=nullptr;
        else if(unavailable==3)s_raster_ok=0;
        else if(unavailable==4)s_hd_state=0;
        else if(unavailable==5)s_hd_pack=nullptr;
        else if(unavailable==6)s_hd_prog=0;
        else if(unavailable==7)s_hd_skin.valid=0;
        else s_hd_skin_enemy.valid=0;
        gl_renderer_skin_material_get(&state);check(!state.ready,"unsupported/uninitialized state is unavailable");
        rejected_without_mutation(valid_set);
    }
    reset();
    const auto player_keys=s_hd_skin,enemy_keys=s_hd_skin_enemy;
    for(int profile=0;profile<gl_renderer_skin_profile_count();++profile)for(int strength:{0,1,50,99,100}){
        char json[512];const char *name=gl_renderer_skin_profile_id(profile);
        std::snprintf(json,sizeof json,"{\"cmd\":\"skin_material\",\"player_profile\":\"%s\",\"player_strength_percent\":%d,\"enemy_profile\":\"%s\",\"enemy_strength_percent\":%d}",name,strength,name,100-strength);
        request(json);check(std::strstr(response,"\"ok\":true")!=nullptr,"every profile and strength boundary applies");
        gl_renderer_skin_material_get(&state);
        check(!std::strcmp(state.player.profile,name)&&!std::strcmp(state.enemy.profile,name),"getter reports selected pair");
        check(state.player.strength_percent==strength&&state.enemy.strength_percent==100-strength,"integer strengths roundtrip");
        check(!std::memcmp(player_keys.keys,s_hd_skin.keys,sizeof player_keys.keys)&&!std::memcmp(enemy_keys.keys,s_hd_skin_enemy.keys,sizeof enemy_keys.keys),"exact key arrays unchanged");
        check(s_hd_detail_player.texture==11&&s_hd_detail_enemy.texture==22,"no detail asset replacement");
    }
    std::printf("{\"contract\":\"%s\",\"checks\":%d,\"requests_tested\":%d,\"failures\":%d,\"profiles_including_stock\":%d,\"sample_get\":%s,\"sample_set\":%s,\"sample_maximum_set\":%s,\"pass\":%s}\n",HD_SKIN_MATERIAL_CONTRACT,checks,requests,failures,gl_renderer_skin_profile_count(),sample_get.c_str(),sample_set.c_str(),sample_maximum_set.c_str(),failures?"false":"true");
    return failures?1:0;
}
