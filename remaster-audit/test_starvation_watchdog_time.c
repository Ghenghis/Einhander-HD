#include "../windows-x64/psxrecomp/runtime/src/starvation_watchdog_time.h"
#include <stdio.h>
static int checks, failures;
#define CHECK(x) do {++checks;if(!(x)){++failures;printf("FAIL line%d\n",__LINE__);}} while(0)
int main(void) {
    uint64_t age=99, hb=UINT64_C(187224521717);
    CHECK(!starvation_watchdog_expired(hb+153,hb,4000000,&age)&&age==0);
    CHECK(!starvation_watchdog_expired(hb,hb,4000000,&age)&&age==0);
    CHECK(!starvation_watchdog_expired(hb,hb+1443,4000000,&age)&&age==1443);
    CHECK(!starvation_watchdog_expired(hb,hb+4000000,4000000,&age)&&age==4000000);
    CHECK(starvation_watchdog_expired(hb,hb+4000001,4000000,&age)&&age==4000001);
    CHECK(!starvation_watchdog_expired(0,hb,4000000,&age)&&age==0);
    CHECK(!starvation_watchdog_expired(hb,hb+9000000,0,&age)&&age==9000000);
    CHECK(!starvation_watchdog_expired(UINT64_MAX-100,UINT64_MAX-50,4000000,&age)&&age==50);
    CHECK(starvation_watchdog_expired(1,UINT64_MAX,4000000,&age));
    printf("{\"checks\":%d,\"failures\":%d}\n",checks,failures);
    return failures?1:0;
}
