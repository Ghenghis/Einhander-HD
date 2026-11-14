/* PRIVATE default-OFF scene observer control. Executes at emulation safe point. */
static void handle_scene_capture(int id,const char *json) {
    int rc=SCENE_OK;
    if(json_get_int(json,"cancel",0)==1)rc=scene_runtime_cancel();
    if(json_get_int(json,"arm",0)==1)rc=scene_runtime_arm((uint32_t)s_frame_count);
    int index=json_get_int(json,"index",-1);
    SceneCaptureInfo i={0};int ir=scene_runtime_info(&i);
    if(rc!=SCENE_OK||ir!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc!=SCENE_OK?rc:ir);return;}
    if(index>=0) {
        char record[8192];rc=scene_runtime_json((uint32_t)index,record,sizeof record);
        if(rc!=SCENE_OK){send_fmt("{\"id\":%d,\"ok\":false,\"error\":%d}",id,rc);return;}
        send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v2\",\"record\":%s}",id,record);return;
    }
    send_fmt("{\"id\":%d,\"ok\":true,\"schema\":\"gp0-scene-v2\",\"mode\":%u,\"frame\":%u,\"count\":%u,\"capacity\":%u,\"textured_seen\":%u,\"malformed\":%u,\"overflow\":%u,\"geometry_qualified\":%u,\"missing_vertices\":%u,\"other_commands\":%u,\"complete_interval\":%s}",id,i.mode,i.frame,i.count,i.capacity,i.textured_seen,i.malformed,i.overflow,i.qualified,i.missing_vertices,i.other_commands,i.complete?"true":"false");
}

