// Actual CPU GTE/PGXP producer -> transport -> CPU SDK-layout staging.
// Synthetic guest instructions and dummy material; not a game/SDK render.
extern "C" int gte_rtp_ring_get_xform(uint64_t,int16_t[9],int32_t[3],uint32_t*,uint32_t*);
static int bridge_lookups=0,bridge_transforms=0;
static int bridge_lookup(void*,uint32_t address,uint32_t word,PgxpView* view) {
    ++bridge_lookups;
    return pgxp_get_precise_vertex_view(address,word,view);
}
static int bridge_transform(void*,uint64_t sequence,int16_t rt[9],int32_t tr[3],uint32_t* frame,uint32_t* ra) {
    ++bridge_transforms;
    return gte_rtp_ring_get_xform(sequence,rt,tr,frame,ra);
}
static void t_real_producer_bridge() {
    using namespace einhd;
    gpu_texture_correction_set(0);gpu_view_census_set(1);pgxp_view_census_reset();
    s_frame_count=4242;
    const uint32_t base=0x801E0000u;
    const int idx[3]={1,3,5};
    const int16_t points[3][3]={{0,0,0},{20,0,0},{0,20,0}};
    MeshInput input;input.frame=4242;input.material_identity=0xEE1234u;
    input.material=reinterpret_cast<remixapi_MaterialHandle>(uintptr_t(0x100));
    for(int i=0;i<3;++i){input.packet_address[i]=base+4u*uint32_t(idx[i]);input.sdk_vertex_color[i]=0xFF808080u;input.uv[i][0]=i==1?1.f:0.f;input.uv[i][1]=i==2?1.f:0.f;}
    auto project_packet=[&](int32_t translation_x){
        CPUState cpu{};Xf x=XF;x.tr[0]=translation_x;load_xf(cpu,x);
        for(int lane=0;lane<3;++lane)set_v(cpu,lane,points[lane][0],points[lane][1],points[lane][2]);
        gte_execute(&cpu,RTPT1);
        gp0_cmd_buf[0]=0x24808080u;gp0_cmd_source_addr=base;
        for(int lane=0;lane<3;++lane){input.packet_word[lane]=swc2(cpu,12+lane,input.packet_address[lane]);gp0_cmd_buf[idx[lane]]=input.packet_word[lane];}
    };
    project_packet(XF.tr[0]);
    PgxpView views[3]{};
    for(int i=0;i<3;++i){CHECK(pgxp_get_precise_vertex_view(input.packet_address[i],input.packet_word[i],&views[i])==PGXP_SRC_DATAFLOW);CHECK(views[i].cmd==0x30&&views[i].lane==i);}
    CHECK(views[0].rtp_seq==views[1].rtp_seq&&views[0].rtp_seq==views[2].rtp_seq);
    MeshSource source{nullptr,bridge_lookup,bridge_transform};MeshPacket packet;
    CHECK(build_mesh_packet(input,source,packet)==MeshReject::None);
    CHECK(bridge_lookups==3&&bridge_transforms==3);
    CHECK(packet.mesh.surfaces_values==&packet.surface&&packet.surface.vertices_values==packet.vertices);
    for(int i=0;i<3;++i)for(int axis=0;axis<3;++axis)CHECK(packet.vertices[i].position[axis]==points[i][axis]);
    CHECK(std::memcmp(packet.combined_rt,XF.rt,sizeof XF.rt)==0&&std::memcmp(packet.combined_tr,XF.tr,sizeof XF.tr)==0);
    CHECK(packet.projection_h==XF.h&&packet.projection_ofx==XF.ofx&&packet.projection_ofy==XF.ofy);
    const uint64_t hash=packet.mesh.hash;
    harness_prepare_texture_triangle(1,3,5);CHECK(census().kind[0].all_hit==1&&census().kind[0].hit_committed==3);
    project_packet(XF.tr[0]+10);
    CHECK(build_mesh_packet(input,source,packet)==MeshReject::None&&packet.mesh.hash==hash&&packet.combined_tr[0]==XF.tr[0]+10);
    input.frame++;CHECK(build_mesh_packet(input,source,packet)==MeshReject::StaleFrame);
    CHECK(packet.mesh.surfaces_count==0&&packet.surface.vertices_values==nullptr);input.frame--;
    // Actual shadow invalidation by a partial write must deny the CPU bridge.
    psx_pgxp_store(nullptr,SH(8),input.packet_address[0],input.packet_word[0]);
    CHECK(build_mesh_packet(input,source,packet)==MeshReject::DataflowMiss);
    CHECK(packet.mesh.surfaces_count==0&&packet.surface.vertices_values==nullptr);
    gpu_view_census_set(0);
}
