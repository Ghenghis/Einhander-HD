/* stb_impl.c - the stb_image implementation for host tests of the pack TU, with the runtime's exact flags
 * (psx_window_icon.cpp: STBI_ONLY_PNG + STBI_NO_STDIO). Test support only. */
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_PNG
#define STBI_NO_STDIO
#include "stb_image.h"
