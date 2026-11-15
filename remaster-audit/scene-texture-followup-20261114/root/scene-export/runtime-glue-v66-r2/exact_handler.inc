/* PRIVATE default-OFF scene observer control. Executes at emulation safe point. */
static void handle_scene_capture(int id,const char *json) {
    int rc=SCENE_OK;
    if(json_get_int(json,"cancel",0)==1)rc=scene_runtime_cancel();
    if(json_get_int(json,"arm",0)==1)rc=scene_runtime_arm((uint32_t)s_frame_count);
    int index=json_get_int(json,"index",-1);
    SceneCaptureInfo i={0};int ir=scene_runtime_info(&i);
    if(rc!=SCENE_OK||ir!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc!=SCENE_OK?rc:ir);return;}
    if(index>=0) {
        int generation=json_get_int(json,"generation",-1);
        if(generation<0){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,SCENE_BAD_ARGUMENT);return;}
        char record[8192];rc=scene_runtime_json((uint32_t)index,(uint32_t)generation,record,sizeof record);
        if(rc!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc);return;}
        send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v3\",\"record\":%s}",id,record);return;
    }
    send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v3\",\"mode\":%u,\"frame\":%u,\"generation\":%u,\"count\":%u,\"capacity\":%u,\"textured_seen\":%u,\"malformed\":%u,\"overflow\":%u,\"geometry_qualified\":%u,\"missing_vertices\":%u,\"other_commands\":%u,\"complete_interval\":%s,\"untextured_polygons\":%u,\"textured_sprites\":%u,\"untextured_rects\":%u,\"lines\":%u,\"vram_fills\":%u,\"lag0_vertices\":%u,\"lag1_vertices\":%u,\"mixed_lag_primitives\":%u,\"ws_rejected_vertices\":%u,\"owner_errors\":%u,\"geometry_types_complete\":%s}",id,i.mode,i.frame,i.generation,i.count,i.capacity,i.textured_seen,i.malformed,i.overflow,i.qualified,i.missing_vertices,i.other_commands,i.complete?"true":"false",i.untextured_polygons,i.textured_sprites,i.untextured_rects,i.lines,i.vram_fills,i.lag0_vertices,i.lag1_vertices,i.mixed_lag_primitives,i.ws_rejected_vertices,i.owner_errors,i.geometry_types_complete?"true":"false");
}

