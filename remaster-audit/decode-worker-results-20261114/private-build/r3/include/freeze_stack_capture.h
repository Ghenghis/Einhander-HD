#ifndef PSXRECOMP_FREEZE_STACK_CAPTURE_H
#define PSXRECOMP_FREEZE_STACK_CAPTURE_H
#ifdef _WIN32
#include <windows.h>
#include <stdint.h>
#include <string.h>

#define FREEZE_STACK_BYTES 65536u
typedef struct FreezeStackSnapshot {
    CONTEXT context;
    uintptr_t region_low, region_high, base;
    SIZE_T size;
    unsigned char bytes[FREEZE_STACK_BYTES];
} FreezeStackSnapshot;

/* No allocation, stdio, symbol lookup or stack walking while suspended.
 * Exactly one resume balances our suspend, including every failure path. */
static int freeze_capture_stack(HANDLE thread,DWORD thread_id,FreezeStackSnapshot *out) {
    if (!thread || !out || thread_id==GetCurrentThreadId()) return 0;
    memset(out,0,sizeof(*out));
    out->context.ContextFlags=CONTEXT_FULL;
    if (SuspendThread(thread)==(DWORD)-1) return 0;
    int captured=GetThreadContext(thread,&out->context)!=0;
    if (captured) {
#if defined(_M_X64) || defined(__x86_64__)
        out->base=(uintptr_t)out->context.Rsp;
#else
        out->base=(uintptr_t)out->context.Esp;
#endif
        MEMORY_BASIC_INFORMATION memory;
        if (VirtualQuery((LPCVOID)out->base,&memory,sizeof(memory))==sizeof(memory)) {
            out->region_low=(uintptr_t)memory.BaseAddress;
            out->region_high=out->region_low+memory.RegionSize;
            if (out->region_high>out->base) {
                SIZE_T wanted=out->region_high-out->base,got=0;
                if (wanted>FREEZE_STACK_BYTES)wanted=FREEZE_STACK_BYTES;
                if (ReadProcessMemory(GetCurrentProcess(),(LPCVOID)out->base,out->bytes,wanted,&got))
                    out->size=got;
            }
        }
    }
    if (ResumeThread(thread)==(DWORD)-1)return 0;
    return captured;
}

/* 1 = cached bytes, 0 = outside captured stack, -1 = unavailable stack bytes.
 * Module/unwind-table reads may fall back to ReadProcessMemory after resume. */
static int freeze_stack_read_cached(const FreezeStackSnapshot *s,uintptr_t address,
                                    void *out,SIZE_T bytes) {
    if (address>=s->base && address-s->base<=s->size && bytes<=s->size-(address-s->base)) {
        memcpy(out,s->bytes+(address-s->base),bytes);return 1;
    }
    if (address>=s->region_low && address<s->region_high)return -1;
    return 0;
}
#endif
#endif
