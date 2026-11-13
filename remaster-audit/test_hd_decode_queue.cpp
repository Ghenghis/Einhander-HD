#include "../windows-x64/psxrecomp/runtime/src/hd_decode_queue.h"
#include <cstdio>
static int failures=0,checks=0;
static void check(bool pass){++checks;if(!pass)++failures;}
int main(){
    uint64_t key=999;
    {HdDecodeQueue q;for(uint64_t i=0;i<32;++i)check(q.push(i,false));check(!q.push(32,false));
     for(uint64_t i=0;i<32;++i){check(q.take(&key));check(key==i);}check(q.empty());check(!q.take(&key));}
    {HdDecodeQueue q;for(uint64_t i=0;i<32;++i)q.push(i,false);
     check(!q.push(100,true));check(q.take(&key)&&key==0);
     check(!q.push(33,false));check(q.push(100,true));check(q.size()==32);
     check(q.take(&key)&&key==100);check(q.take(&key)&&key==1);}
    {HdDecodeQueue q;q.enable_priority();for(uint64_t i=0;i<28;++i)check(q.push(i,false));
     check(!q.push(28,false));for(uint64_t i=100;i<104;++i)check(q.push(i,true));check(!q.push(104,true));
     for(uint64_t i=100;i<104;++i)check(q.take(&key)&&key==i);
     check(q.push(104,true));check(q.take(&key)&&key==0);check(q.take(&key)&&key==104);
     for(uint64_t i=1;i<28;++i)check(q.take(&key)&&key==i);check(q.empty());}
    {HdDecodeQueue q;for(uint64_t i=0;i<40;++i){check(q.push(i,true));check(q.take(&key)&&key==i);}
     check(q.push(100,false));check(q.push(200,true));check(q.take(&key)&&key==100);check(q.take(&key)&&key==200);}
    std::printf("{\"checks\":%d,\"failures\":%d,\"capacity\":32,\"urgent_burst\":4}\n",checks,failures);return failures?1:0;
}
