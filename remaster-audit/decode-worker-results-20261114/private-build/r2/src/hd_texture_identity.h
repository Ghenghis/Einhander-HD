#ifndef HD_TEXTURE_IDENTITY_H
#define HD_TEXTURE_IDENTITY_H
/* PRIVATE v6 additive header (claude-einhander; renderer-v61-classmip DESIGN-V6.md). hd_texture_pack.h and the public
 * HdTexturePixels are unchanged. With PSXRECOMP_HD_DECODE_IDENTITY=1 (exactly, read once at pack open) the decode
 * worker computes the HDCM-X4 level-0 identity and has-cutout truth of each decoded image before publishing it Ready.
 * hd_texture_pixels_identity returns them in O(1) for a VALID acquired lease whose rgba/width/height/stride still match
 * the leased image. It cannot validate a forged lease pointer. */
#include <stdint.h>
#include "hd_texture_pack.h"
#ifdef __cplusplus
extern "C" {
#endif
enum {
    HD_TEXTURE_IDENTITY_OK = 0,
    HD_TEXTURE_IDENTITY_NO_LEASE = -1,      /* null pixels / no lease / no image */
    HD_TEXTURE_IDENTITY_UNAVAILABLE = -2,   /* identity mode off (or image decoded before it was enabled) */
    HD_TEXTURE_IDENTITY_MISMATCH = -3       /* rgba/width/height/stride differ from the leased image */
};
int hd_texture_pixels_identity(const HdTexturePixels* pixels, uint64_t* level0_x4, int* has_cutout);
#ifdef __cplusplus
}
#endif
#endif
