#include "../windows-x64/psxrecomp/runtime/src/freeze_stack_capture.h"
#include <stdio.h>
static CRITICAL_SECTION held;
static HANDLE ready,release;
static DWORD WINAPI worker(void *unused) {
    (void)unused;EnterCriticalSection(&held);SetEvent(ready);
    WaitForSingleObject(release,INFINITE);LeaveCriticalSection(&held);return 0;
}
static FreezeStackSnapshot snapshot;
int main(void) {
    InitializeCriticalSection(&held);
    ready=CreateEvent(NULL,TRUE,FALSE,NULL);release=CreateEvent(NULL,TRUE,FALSE,NULL);
    DWORD id=0;HANDLE thread=CreateThread(NULL,0,worker,NULL,0,&id);
    if(!thread||WaitForSingleObject(ready,2000)!=WAIT_OBJECT_0)return 2;
    if(!freeze_capture_stack(thread,id,&snapshot))return 3;
    if(!snapshot.size||snapshot.size>FREEZE_STACK_BYTES)return 4;
    unsigned char value=0;
    if(freeze_stack_read_cached(&snapshot,snapshot.base,&value,1)!=1||value!=snapshot.bytes[0])return 5;
    if(freeze_stack_read_cached(&snapshot,snapshot.base+snapshot.size-1,&value,2)!=-1)return 6;
    if(freeze_capture_stack(GetCurrentThread(),GetCurrentThreadId(),&snapshot))return 7;
    SetEvent(release);
    /* This would hang if capture left the lock-owning worker suspended. */
    EnterCriticalSection(&held);LeaveCriticalSection(&held);
    if(WaitForSingleObject(thread,2000)!=WAIT_OBJECT_0)return 8;
    CloseHandle(thread);CloseHandle(ready);CloseHandle(release);DeleteCriticalSection(&held);
    puts("{\"thread_resumed_before_locking\":true,\"bounded_stack_copy\":true,\"self_suspend_rejected\":true}");
    return 0;
}
