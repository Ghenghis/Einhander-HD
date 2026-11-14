/* Included after debug_server.c send helpers. Shared with the native wire
 * contract test so it exercises this exact handler, not a duplicate model. */
#ifndef PSXRECOMP_HD_SKIN_LIVE_DEBUG_H
#define PSXRECOMP_HD_SKIN_LIVE_DEBUG_H
#include "hd_skin_live.h"
#include "gpu_gl_renderer.h"

static void handle_skin_material(int id,const char *json) {
    HdSkinLiveRequest request;
    GlSkinMaterialState state;
    char profiles[2048],error[160];
    const char *problem=hd_skin_live_parse(json,&request);
    size_t used=0;
    int i;
    if(problem){send_err(id,problem);return;}
    if(request.set){
        if(!gl_renderer_skin_material_configure(request.player_profile[0]?request.player_profile:NULL,request.player_strength_percent,
                request.enemy_profile[0]?request.enemy_profile:NULL,request.enemy_strength_percent,
                request.diagnostic_player_keys[0]?request.diagnostic_player_keys:NULL,
                request.diagnostic_enemy_keys[0]?request.diagnostic_enemy_keys:NULL,
                request.preserve_accents,&state,error,sizeof error)){
            send_err(id,error);return;
        }
    }else if(!gl_renderer_skin_material_get(&state)){
        send_err(id,"Material state is unavailable");return;
    }
    profiles[0]=0;
    for(i=0;i<gl_renderer_skin_profile_count();++i){
        const char *profile=gl_renderer_skin_profile_id(i);
        int count=snprintf(profiles+used,sizeof profiles-used,"%s\"%s\"",i?",":"",profile?profile:"");
        if(count<0 || (size_t)count>=sizeof profiles-used){send_err(id,"Material profile list exceeds response bounds");return;}
        used+=(size_t)count;
    }
    send_fmt("{\"id\":%d,\"ok\":true,\"contract\":\"%s\",\"live_palette\":true,"
        "\"ready\":%s,\"opengl_ready\":%s,\"hd_ready\":%s,\"renderer\":\"%s\","
        "\"applied\":%s,\"generation\":%llu,\"frame\":%llu,\"apply_scope\":\"color_only_next_draw\","
        "\"detail_changes\":\"next_launch_only\","
        "\"diagnostic_scope_supported\":true,\"diagnostic_scope_status\":\"temporary_candidate_not_actor_binding\","
        "\"diagnostic_max_keys_per_channel\":%d,\"diagnostic_key_validation\":\"registered_exact_pack_entry_not_render_proof\","
        "\"player\":{\"profile\":\"%s\",\"strength_percent\":%d,\"key_count\":%d,\"detail_active\":%s,\"diagnostic_scope\":%s,\"preserve_accents\":%s,\"keys\":\"%s\"},"
        "\"enemy\":{\"profile\":\"%s\",\"strength_percent\":%d,\"key_count\":%d,\"detail_active\":%s,\"diagnostic_scope\":%s,\"preserve_accents\":%s,\"keys\":\"%s\"},"
        "\"supported_profiles\":[%s]}",
        id,state.contract,state.ready?"true":"false",state.opengl_ready?"true":"false",state.hd_ready?"true":"false",
        state.renderer,request.set?"true":"false",(unsigned long long)state.generation,(unsigned long long)s_frame_count,
        GL_SKIN_DIAGNOSTIC_KEYS_MAX,
        state.player.profile,state.player.strength_percent,state.player.key_count,state.player.detail_active?"true":"false",
        state.player.diagnostic_scope?"true":"false",state.player.preserve_accents?"true":"false",state.player.keys,
        state.enemy.profile,state.enemy.strength_percent,state.enemy.key_count,state.enemy.detail_active?"true":"false",
        state.enemy.diagnostic_scope?"true":"false",state.enemy.preserve_accents?"true":"false",state.enemy.keys,profiles);
}
#endif
