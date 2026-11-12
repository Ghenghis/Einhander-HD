#define NOMINMAX
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include "hd_research_capture.h"

namespace fs=std::filesystem;
static int checks=0,failures=0;
static fs::path base;
static unsigned case_number=0;
static void expect(bool condition,const char *what){++checks;if(!condition){++failures;std::fprintf(stderr,"FAIL: %s\n",what);}}
static fs::path fresh(const char *name){auto p=base/(std::to_string(++case_number)+"-"+name);fs::create_directory(p);return p;}
static std::string content(const fs::path &p){std::ifstream f(p,std::ios::binary);return std::string(std::istreambuf_iterator<char>(f),{});}
static void put(const fs::path &p,const std::string &s){std::ofstream f(p,std::ios::binary);f.write(s.data(),s.size());}
static HdResearchCapture start(const fs::path &p,HdResearchLimits limits=hdrc_default_limits()){
    HdResearchCapture s{};char error[160];
    expect(hdrc_start(&s,p.string().c_str(),&limits,100,1000,error,sizeof error)==1,"start private absolute directory");
    expect(s.active && s.files==1 && !s.bytes_written && !error[0],"start state and receipt file count");return s;
}
int main(int argc,char **argv){
    if(argc!=2)return 2;base=fs::absolute(argv[1]);if(!fs::is_directory(base))return 2;
    {
        auto p=fresh("basic");auto s=start(p);auto limits=s.limits;char error[80];
        expect(!hdrc_start(&s,p.string().c_str(),&limits,0,0,error,sizeof error) && s.active,"repeated start preserves active session");
        expect(hdrc_json(&s,"{\"ok\":true}\r\n",101,1001)==1,"JSON accepts one trailing newline");
        const unsigned char bytes[]={0,7,255,2,0};
        expect(hdrc_blob(&s,"texture.words.bin",bytes,sizeof bytes,102,1002)==1,"atomic binary blob");
        expect(content(p/"texture.words.bin")==std::string((const char*)bytes,sizeof bytes),"atomic blob has exact binary content");
        expect(!fs::exists(p/"texture.words.bin.part"),"successful blob leaves no part");
        expect(hdrc_blob(&s,"empty.bin",nullptr,0,103,1003)==1 && fs::file_size(p/"empty.bin")==0,"empty blob is explicit valid evidence");
        expect(s.records==1 && s.files==3 && s.bytes_written==17,"successful bytes/records/files accounted");
        expect(content(p/"capture.jsonl")=="{\"ok\":true}\n","JSON has exactly one line");
        hdrc_stop(&s,"manual_stop");expect(!s.active && !s.receipt_file && !std::strcmp(s.stop_reason,"manual_stop"),"stop closes receipt");
        hdrc_stop(&s,"different");expect(!std::strcmp(s.stop_reason,"manual_stop"),"stop idempotent preserves cause");
        expect(!hdrc_tick(&s,100,1000),"inactive tick does not reactivate");
    }
    {
        auto p=fresh("soft-caps");auto l=hdrc_default_limits();l.max_sources=l.max_events=l.max_records=1;auto s=start(p,l);
        expect(hdrc_claim_source(&s,100,1000)==1 && !hdrc_claim_source(&s,100,1000) && s.active && s.sources==1,"source cap is soft");
        expect(hdrc_json(&s,"{}",100,1000)==1 && !hdrc_json(&s,"{}",100,1000) && s.active && s.records==1,"record cap is soft");
        expect(hdrc_claim_event(&s,100,1000)==1 && !hdrc_claim_event(&s,100,1000) && s.active && s.events==1,"event cap is soft independent");
        expect(hdrc_blob(&s,"later-event.json","{}",2,100,1000)==1,"explicit snapshot still possible after soft caps");
        hdrc_stop(&s,"done");
    }
    for(int which=0;which<6;++which){
        auto p=fresh("invalid-limits");HdResearchCapture s{};auto l=hdrc_default_limits();char error[160];
        if(which==0)l.max_sources=257;if(which==1)l.max_records=20001;if(which==2)l.max_events=33;
        if(which==3)l.max_frames=18001;if(which==4)l.max_seconds=301;if(which==5)l.max_bytes=128u*HDRC_MIB+1;
        expect(!hdrc_start(&s,p.string().c_str(),&l,100,1000,error,sizeof error),"over-limit configuration rejected");
        expect(!fs::exists(p/"capture.jsonl") && !s.active && error[0],"limits validated before opening");
    }
    for(int which=0;which<6;++which){
        auto p=fresh("zero-limit");HdResearchCapture s{};auto l=hdrc_default_limits();char error[160];
        if(which==0)l.max_sources=0;if(which==1)l.max_records=0;if(which==2)l.max_events=0;
        if(which==3)l.max_frames=0;if(which==4)l.max_seconds=0;if(which==5)l.max_bytes=0;
        expect(!hdrc_start(&s,p.string().c_str(),&l,100,1000,error,sizeof error) && !fs::exists(p/"capture.jsonl"),"zero limit rejected before open");
    }
    {
        auto p=fresh("maximum-limits");HdResearchLimits l={256,20000,32,18000,300,128u*HDRC_MIB};auto s=start(p,l);hdrc_stop(&s,"done");
        expect(hdrc_default_limits().max_frames==3600 && hdrc_default_limits().max_seconds==60,"documented defaults");
    }
    for(int which=0;which<5;++which){
        auto p=fresh("expiry");auto l=hdrc_default_limits();l.max_seconds=1;l.max_frames=10;auto s=start(p,l);
        expect(hdrc_tick(&s,109,1999)==1 && s.start_frame==100 && s.start_ms==1000,"status never renews lease");
        if(which==0)expect(!hdrc_json(&s,"{}",110,1999) && !std::strcmp(s.stop_reason,"frame_limit"),"frame cap before JSON write");
        if(which==1)expect(!hdrc_blob(&s,"late.bin","x",1,109,2000) && !std::strcmp(s.stop_reason,"time_limit"),"time cap before blob write");
        if(which==2)expect(!hdrc_claim_source(&s,99,1500) && !std::strcmp(s.stop_reason,"frame_reset"),"frame rollback hard stop");
        if(which==3)expect(!hdrc_claim_event(&s,109,999) && !std::strcmp(s.stop_reason,"clock_rollback"),"clock rollback hard stop");
        if(which==4)expect(!hdrc_tick(&s,110,2000) && !s.active,"plain status enforces expiry");
        expect(fs::file_size(p/"capture.jsonl")==0,"expired operation writes no receipt bytes");
    }
    {
        auto p=fresh("rollback-above-start");auto s=start(p);
        expect(hdrc_tick(&s,150,1800)==1 && s.last_frame==150 && s.last_ms==1800,"tick tracks latest monotonic observation");
        expect(!hdrc_json(&s,"{}",140,1900) && !s.active && !std::strcmp(s.stop_reason,"frame_reset"),"restored frame above start still hard stops");
        expect(fs::file_size(p/"capture.jsonl")==0,"above-start rollback writes no data");
    }
    {
        auto p=fresh("clock-above-start");auto s=start(p);
        expect(hdrc_tick(&s,150,1800)==1,"clock rollback setup");
        expect(!hdrc_blob(&s,"late.bin","x",1,151,1700) && !s.active && !std::strcmp(s.stop_reason,"clock_rollback"),"clock rollback above start stops before blob");
        expect(!fs::exists(p/"late.bin.part"),"clock rollback creates no partial blob");
    }
    {
        auto p=fresh("byte-reserve");auto l=hdrc_default_limits();l.max_bytes=4;auto s=start(p,l);
        expect(hdrc_json(&s,"{}",100,1000)==1 && s.bytes_written==3,"small successful receipt budget");
        expect(!hdrc_blob(&s,"too-large.bin","xx",2,100,1000) && !s.active && !std::strcmp(s.stop_reason,"byte_limit"),"reserve bytes before blob open");
        expect(s.bytes_written==3 && !fs::exists(p/"too-large.bin.part") && !fs::exists(p/"too-large.bin"),"failed reservation does not write");
    }
    {
        auto p=fresh("byte-boundary");auto l=hdrc_default_limits();l.max_bytes=4;auto s=start(p,l);
        expect(hdrc_blob(&s,"exact.bin","1234",4,100,1000)==1 && s.bytes_written==4,"exact byte boundary accepted");
        expect(!hdrc_tick(&s,100,1000) && !std::strcmp(s.stop_reason,"byte_limit"),"byte boundary hard stops on tick");
        expect(fs::file_size(p/"exact.bin")==4,"disk payload never exceeds byte budget");
    }
    {
        auto p=fresh("file-cap");auto s=start(p);bool okay=true;
        for(unsigned i=0;i<HDRC_MAX_FILES-1;++i){auto leaf="blob-"+std::to_string(i)+".bin";okay=hdrc_blob(&s,leaf.c_str(),nullptr,0,100,1000)&&okay;}
        expect(okay && s.files==HDRC_MAX_FILES,"all successful files counted through hard cap");
        expect(!hdrc_blob(&s,"overflow.bin",nullptr,0,100,1000) && !s.active && !std::strcmp(s.stop_reason,"file_limit"),"file cap hard stops");
        expect(!fs::exists(p/"overflow.bin") && std::distance(fs::directory_iterator(p),fs::directory_iterator{})==HDRC_MAX_FILES,"no file beyond hard cap");
    }
    {
        auto p=fresh("existing-receipt");put(p/"capture.jsonl","prior-evidence");HdResearchCapture s{};char error[160];auto l=hdrc_default_limits();
        expect(!hdrc_start(&s,p.string().c_str(),&l,100,1000,error,sizeof error),"receipt create is exclusive");
        expect(content(p/"capture.jsonl")=="prior-evidence","existing receipt preserved");
    }
    {
        auto p=fresh("existing-final");put(p/"taken.bin","keep");auto s=start(p);
        expect(!hdrc_blob(&s,"taken.bin","new",3,100,1000) && !s.active,"final promotion never overwrites");
        expect(content(p/"taken.bin")=="keep" && !fs::exists(p/"taken.bin.part"),"preexisting final unchanged and owned part cleaned");
        expect(s.files==1 && s.bytes_written==0,"failed blob not counted successful");
    }
    {
        auto p=fresh("existing-part");put(p/"taken.bin.part","keep-part");auto s=start(p);
        expect(!hdrc_blob(&s,"taken.bin","new",3,100,1000) && content(p/"taken.bin.part")=="keep-part","preexisting part never overwritten or removed");
        expect(!fs::exists(p/"taken.bin"),"failed part create leaves no final");
    }
    const char* leaves[]={"../escape.bin","a/b.bin","a\\b.bin","C:bad.bin",".hidden","a..bin","trail.","space name","NUL.bin","CON","LPT1.png","COM9.bin","line\nfeed",""};
    for(const char* leaf:leaves){auto p=fresh("bad-leaf");auto s=start(p);expect(!hdrc_blob(&s,leaf,"x",1,100,1000) && !s.active && s.files==1,"unsafe blob leaf rejected without writing");}
    {
        auto p=fresh("bad-directory");auto l=hdrc_default_limits();char error[160];
        std::vector<std::string> paths={"","relative","C:relative",(p/"missing").string(),p.string()+"/../elsewhere",p.string()+"/./nested",p.string()+"\n"};
        for(auto &path:paths){HdResearchCapture s{};expect(!hdrc_start(&s,path.c_str(),&l,100,1000,error,sizeof error) && !s.active,"invalid directory rejected");}
        expect(!fs::exists(p/"capture.jsonl"),"invalid directory attempts create nothing");
    }
    {
        auto p=fresh("write-error");auto s=start(p);std::fclose(s.receipt_file);s.receipt_file=std::fopen((p/"capture.jsonl").string().c_str(),"rb");
        expect(s.receipt_file!=nullptr,"error fixture opens valid read-only stream");
        expect(!hdrc_json(&s,"{}",100,1000) && !s.active && s.records==0 && s.bytes_written==0,"IO write failure stops capture and leaves counts");
        expect(fs::file_size(p/"capture.jsonl")==0,"IO failed receipt has no committed payload");
    }
    {
        auto p=fresh("multiline");auto s=start(p);expect(!hdrc_json(&s,"{}\n{}",100,1000) && !s.active,"embedded line breaks rejected");
        expect(fs::file_size(p/"capture.jsonl")==0,"invalid line writes nothing");
    }
    {
        auto p=fresh("line-cap");auto s=start(p);std::string line(HDRC_MAX_JSON_LINE+1,'x');
        expect(!hdrc_json(&s,line.c_str(),100,1000) && !s.active,"record length bounded before write");
    }
    std::printf("{\"pass\":%s,\"checks\":%d,\"failures\":%d,\"cases\":[\"strict_limits_before_open\",\"exclusive_receipt\",\"atomic_binary_blob\",\"no_overwrite_final_or_part\",\"safe_paths\",\"soft_independent_count_caps\",\"hard_time_frame_byte_file_caps\",\"rollback_and_no_lease_renewal\",\"write_error_stop\",\"bounded_single_line_records\"],\"game_launched\":false}\n",failures?"false":"true",checks,failures);
    return failures?1:0;
}
