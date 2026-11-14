from pathlib import Path
n=Path(__file__).resolve().parent;p=n/'test_scene_capture.cpp';s=p.read_text()
s=s.replace('scene_capture_get(', 'test_get(').replace('scene_capture_json(', 'test_json(')
s=s.replace('state{0xabcde,-13,21,0,0,319,239,1,1}', 'state{0xabcde,-13,21,0,0,319,239,1,1,0,319,1}')
a='static void arm(uint32_t frame=100)'
helpers='''static int test_get(uint32_t token,uint32_t index,ScenePrimitive *out) {
    SceneCaptureInfo i{};if(int rc=scene_capture_info(token,&i))return rc;
    return scene_capture_get(token,index,i.generation,out);
}
static int test_json(uint32_t token,uint32_t index,char *out,size_t cap) {
    SceneCaptureInfo i{};if(int rc=scene_capture_info(token,&i))return rc;
    return scene_capture_json(token,index,i.generation,out,cap);
}
'''
assert s.count(a)==1;s=s.replace(a,helpers+a,1)
a='ScenePrimitive last{};CHECK(test_get(7,SCENE_CAPACITY-1,&last)==0);CHECK(last.ordinal==SCENE_CAPACITY-1);'
assert s.count(a)==1;s=s.replace(a,'ScenePrimitive last{};CHECK(test_get(7,SCENE_CAPACITY-1,&last)==SCENE_BAD_STATE);CHECK(last.word_count==0);',1)
a='seed(0x24);arm();capture(103);CHECK(scene_capture_info(7,&i)==0);CHECK(!i.complete&&i.malformed==1);'
assert s.count(a)==1;s=s.replace(a,'seed(0x24);arm();command_at(7,103,words,count,0x1000,&state);scene_capture_tick(7,104);CHECK(scene_capture_info(7,&i)==0);CHECK(!i.complete&&i.malformed==1);CHECK(test_get(7,0,&last)==SCENE_BAD_STATE);',1)
a='    std::printf("checks %d failures %d record_bytes'
tests=r'''    // Generation, complete-only reads and lifecycle boundaries.
    seed(0x24);arm();SceneCaptureInfo gen{};CHECK(scene_capture_info(7,&gen)==0);
    CHECK(scene_capture_arm(7,100)==SCENE_BAD_STATE);
    CHECK(command_at(7,101,words,count,0x1000,&state)==0);
    CHECK(scene_capture_arm(7,101)==SCENE_BAD_STATE);CHECK(test_get(7,0,&last)==SCENE_BAD_STATE);
    CHECK(scene_capture_tick(7,102)==0);CHECK(test_get(7,0,&last)==0);CHECK(last.eligible_triangle_mask==1);
    const uint32_t old_generation=gen.generation;
    arm();CHECK(command_at(7,101,words,count,0x1000,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(scene_capture_get(7,0,old_generation,&last)==SCENE_BAD_STATE);CHECK(last.word_count==0);
    CHECK(test_get(7,0,&last)==0);CHECK(last.generation!=old_generation);
    seed(0x24);arm();views[0].flags&=uint16_t(~PGXP_VIEW_SF);expect_reason(SCENE_DIVERGED);
    for(int depth=0;depth<3;++depth)for(int blend=0;blend<4;++blend) {
        seed(0x34);arm();words[5]=(words[5]&0xffffu)|(uint32_t((depth<<7)|(blend<<5))<<16);
        auto q=capture();CHECK(q.depth==depth&&q.blend_mode==blend);
        for(int j=0;j<3;++j){CHECK(q.vertex[j].u==5+j*3&&q.vertex[j].v==10+j*4);CHECK(q.vertex[j].rgb==(j?0x654321u+uint32_t(j):0x123456u));}
    }
    // Per-half oversize and native signed 11-bit coordinates, independent of provenance.
    seed(0x2c);arm();const int xs[4]={-600,600,-600,-500};
    for(int j=0;j<4;++j){words[1+j*2]=(words[1+j*2]&0xffff0000u)|uint16_t(xs[j]);views[j].packed=words[1+j*2];}
    auto oversize=capture();CHECK(oversize.oversize_mask==3&&oversize.eligible_triangle_mask==0);CHECK(oversize.vertex[0].native_x==-600);
    seed(0x2c);arm();words[7]=(words[7]&0xffff0000u)|uint16_t(-1000);views[3].packed=words[7];
    auto half=capture();CHECK(half.oversize_mask==2&&half.eligible_triangle_mask==1);
    seed(0x24);arm();SceneDrawState outside=state;outside.effective_left=500;outside.effective_right=700;
    CHECK(command_at(7,101,words,count,0x1000,&outside)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(test_get(7,0,&last)==0);CHECK(last.clip_out_mask==1&&last.eligible_triangle_mask==0);
    seed(0x24);arm();outside=state;outside.native_screen_mapping=0;
    CHECK(command_at(7,101,words,count,0x1000,&outside)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(test_get(7,0,&last)==0);CHECK(last.screen_mapping_known==0&&last.eligible_triangle_mask==0);
    // Mixed valid ages are explicit and ineligible for rendering until qualified.
    seed(0x24);arm();views[0].frame=100;transform_frame[0]=100;
    auto mixed_age=capture();CHECK(mixed_age.qualified&&mixed_age.mixed_lag&&mixed_age.eligible_triangle_mask==0);
    CHECK(scene_capture_info(7,&i)==0);CHECK(i.lag0_vertices==2&&i.lag1_vertices==1&&i.mixed_lag_primitives==1);
    // Omitted drawing families cannot silently become full geometry coverage.
    seed(0x24);arm();for(int op:{0x20,0x64,0x60,0x48,0x02}) {
        uint32_t cmd=uint32_t(op)<<24;CHECK(command_at(7,101,&cmd,1,0xffffffffu,nullptr)==0);
    }
    CHECK(scene_capture_tick(7,102)==0);CHECK(scene_capture_info(7,&i)==0);
    CHECK(i.complete&&!i.geometry_types_complete&&i.untextured_polygons==1&&i.textured_sprites==1&&i.untextured_rects==1&&i.lines==1&&i.vram_fills==1);
    seed(0x24);arm();for(int j=0;j<SCENE_CAPACITY;++j)CHECK(command_at(7,101,words,count,0x1000,&state)==0);
    CHECK(scene_capture_tick(7,102)==0);CHECK(test_get(7,SCENE_CAPACITY-1,&last)==0);
    seed(0x24);arm();CHECK(command_at(7,101,words,13,0x1000,&state)==SCENE_BAD_ARGUMENT);CHECK(scene_capture_tick(7,102)==0);CHECK(test_get(7,0,&last)==SCENE_BAD_STATE);
    seed(0x24);arm();CHECK(command_at(7,101,words,count,0x1000,nullptr)==SCENE_BAD_ARGUMENT);
    CHECK(scene_capture_tick(7,99)==0);CHECK(scene_capture_info(7,&i)==0);CHECK(!i.complete);
'''
assert s.count(a)==1;s=s.replace(a,tests+a,1);p.write_text(s)
p=n/'run_host.py';s=p.read_text().replace("out=n/'host-r5'","out=n/'host-r6'");p.write_text(s)
print('Prepared reviewed collector boundary cases')
