#ifndef PSXRECOMP_STARVATION_WATCHDOG_TIME_H
#define PSXRECOMP_STARVATION_WATCHDOG_TIME_H
#include <stdint.h>

/* A heartbeat observed after the sampled clock is fresh, not UINT64_MAX old.
 * Keep the original strict timeout comparison and explicit disabled state. */
static int starvation_watchdog_expired(uint64_t heartbeat, uint64_t now,
                                      uint64_t timeout, uint64_t *elapsed) {
    const uint64_t age = heartbeat && now >= heartbeat ? now - heartbeat : 0;
    if (elapsed) *elapsed = age;
    return heartbeat && timeout && age > timeout;
}
#endif
