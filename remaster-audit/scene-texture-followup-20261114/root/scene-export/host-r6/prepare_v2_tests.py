from pathlib import Path
n=Path(__file__).resolve().parent;p=n/'test_scene_capture.cpp';s=p.read_text()
s=s.replace('scene_capture_command(', 'command_at(')
a='static void arm(uint32_t frame=100)'
wrapper='''// Existing contiguous controls plus explicit scatter/decrement cases below.
static int command_at(uint32_t token,uint32_t frame,const uint32_t *w,int count0,uint32_t base,const SceneDrawState *st) {
    uint32_t sources[12];for(int j=0;j<12;++j)sources[j]=base==0xffffffffu?base:base+uint32_t(j)*4;
    return scene_capture_command(token,frame,w,count0,sources,st);
}
'''
assert s.count(a)==1;s=s.replace(a,wrapper+a,1)
a='    std::printf("checks %d failures %d record_bytes'
new='''    // A GP0 primitive may span linked-list nodes or decrementing DMA.
    // Never derive individual vertex addresses from its first word.
    for(int kind=0;kind<3;++kind) {
        seed(0x3c);arm();uint32_t sources[12];
        for(int j=0;j<12;++j)sources[j]=kind==0?0x4000-uint32_t(j)*4:0x4000+uint32_t(j)*0x100;
        if(kind==2)sources[0]=0xffffffffu; // immediate header, but tracked vertices
        for(int j=0;j<4;++j)addresses[j]=sources[1+j*3];
        CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
        ScenePrimitive q{};CHECK(scene_capture_get(7,0,&q)==0);CHECK(q.qualified);
        CHECK(!std::memcmp(q.word_sources,sources,size_t(count)*4));
        for(int j=0;j<4;++j)CHECK(q.vertex[j].address==addresses[j]);
    }
    seed(0x24);arm();uint32_t sources[12];for(int j=0;j<12;++j)sources[j]=0x1000+uint32_t(j)*4;
    sources[3]=0xffffffffu;
    CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    ScenePrimitive partial{};CHECK(scene_capture_get(7,0,&partial)==0);CHECK(!partial.qualified&&partial.vertex[1].reason==SCENE_IMMEDIATE);
    seed(0x24);arm();sources[3]=0x100d;
    CHECK(scene_capture_command(7,101,words,count,sources,&state)==0);CHECK(scene_capture_tick(7,102)==0);
    CHECK(scene_capture_get(7,0,&partial)==0);CHECK(!partial.qualified&&partial.vertex[1].reason==SCENE_INVALID_ADDRESS);
'''
assert s.count(a)==1;s=s.replace(a,new+a,1);p.write_text(s)
p=n/'run_host.py';s=p.read_text().replace("out=n/'host-r3'","out=n/'host-r4'")
s=s.replace("assert packet['indices']==", "assert packet['word_sources']==[0x1000+j*4 for j in range(12)]\n        assert packet['indices']==")
p.write_text(s)
print('Prepared per-word source tests; no execution')
