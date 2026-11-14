#ifndef HD_TEXTURE_IDENTITY_H
#define HD_TEXTURE_IDENTITY_H
/* glue_harness stand-in for the private pack-v6 additive header (harness HdTexturePixels). */
#include <stdint.h>
enum {
    HD_TEXTURE_IDENTITY_OK = 0,
    HD_TEXTURE_IDENTITY_NO_LEASE = -1,      /* null pixels / no lease / no image */
    HD_TEXTURE_IDENTITY_UNAVAILABLE = -2,   /* identity mode off (or image decoded before it was enabled) */
    HD_TEXTURE_IDENTITY_MISMATCH = -3       /* rgba/width/height/stride differ from the leased image */
};
int hd_texture_pixels_identity(const HdTexturePixels* pixels, uint64_t* level0_x4, int* has_cutout);
#endif
