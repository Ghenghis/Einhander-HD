/* ein-material-v3: selective player/enemy palette materials for proven HD keys.
 * This header is shared by the renderer and standalone contract/GPU tests.
 * It changes sampled RGB only. Original UVs, geometry, alpha/STP, blending,
 * scene lighting and the stock/default path remain authoritative. */
#ifndef PSXRECOMP_HD_SKIN_MATERIAL_H
#define PSXRECOMP_HD_SKIN_MATERIAL_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>

#define HD_SKIN_MATERIAL_CONTRACT "ein-material-v3"
#define HD_SKIN_VERIFIED_TEXTURE 0x5CC44E5Fu
#define HD_SKIN_VERIFIED_PALETTE 0x053D9A00u
#define HD_SKIN_DEFAULT_STRENGTH 0.75f

typedef struct {
    const char *id;
    uint32_t primary_rgb, accent_rgb;
} HdSkinProfile;

/* Exact collection identifiers and its first two palette swatches. These are
 * color transforms of real atlases, independent of the concept illustrations. */
static const HdSkinProfile hd_skin_profiles[] = {
    {"aurora-teal",        0x16E6CDu, 0x53F6FFu},
    {"solar-orange",       0xFF6A13u, 0xFFBE37u},
    {"ultraviolet-violet",  0x9B43FFu, 0xEF50FFu},
    {"glacier-blue",       0x3D9EFFu, 0xA5F4FFu},
    {"crimson-red",        0xE51A37u, 0xFF5C51u},
    {"toxic-lime",         0xB7FF16u, 0x4FE36Au},
    {"gold-obsidian",      0xF3BD4Au, 0xFFE7A0u},
    {"pearl-magenta",      0xF2F4FFu, 0xFF4AC5u},
    {"aurora-gilt",        0x16E6CDu, 0xF3BD4Au},
    {"crimson-regalia",    0xE51A37u, 0xFFD16Au},
    {"glacier-gilt",       0x3D9EFFu, 0xE8C46Au},
    {"neon-circuit",       0x00F0FFu, 0xFF32D2u},
    {"ultraviolet-grid",   0x8426FFu, 0x38F6FFu},
    {"reactor-lime",       0xB6FF00u, 0xF8FF59u}
};
#define HD_SKIN_PROFILE_COUNT ((int)(sizeof(hd_skin_profiles) / sizeof(hd_skin_profiles[0])))

typedef struct { uint32_t texture, palette; } HdSkinKey;
#define HD_SKIN_MAX_KEYS 8
#define HD_SKIN_MAX_DIAGNOSTIC_KEYS 128
#define HD_SKIN_DIAGNOSTIC_CSV_CAP (HD_SKIN_MAX_DIAGNOSTIC_KEYS*18)
static const HdSkinKey hd_skin_player_keys[] = {
    {HD_SKIN_VERIFIED_TEXTURE,HD_SKIN_VERIFIED_PALETTE},
    {0x724E77DAu,0x21FDE894u},{0x7E3ADD56u,0x21FDE894u},
    {0xB16492B1u,0x21FDE894u},{0xE2F3477Cu,0x21FDE894u}
};
/* Observed Stage 1 green/yellow enemy upload strips. Their ownership is
 * capture-backed, not an assertion of exclusivity in every stage/route.
 * The broad 2294438F native page intentionally remains excluded. */
static const HdSkinKey hd_skin_enemy_keys[] = {
    {0x3594C110u,0x527B28B9u},{0x3FE0776Du,0x527B28B9u},
    {0x6BB2A2A3u,0x527B28B9u},{0x784BFD39u,0x527B28B9u},
    {0xDEA9D15Cu,0x527B28B9u},{0x05C32A1Eu,0x527B28B9u}
};

typedef struct {
    const HdSkinProfile *profile;
    float strength;
    int enabled;
    int valid;
    HdSkinKey keys[HD_SKIN_MAX_KEYS];
    int key_count;
    /* Temporary exact-key color probes never change the configured allowlist
     * or establish actor ownership. They are cleared explicitly or on restart. */
    HdSkinKey diagnostic_keys[HD_SKIN_MAX_DIAGNOSTIC_KEYS];
    int diagnostic_key_count, diagnostic_scope, preserve_accents;
} HdSkinConfig;

static const HdSkinProfile *hd_skin_find_profile(const char *id) {
    int i;
    if (!id || !id[0] || !strcmp(id, "stock")) return NULL;
    for (i = 0; i < HD_SKIN_PROFILE_COUNT; ++i)
        if (!strcmp(hd_skin_profiles[i].id, id)) return &hd_skin_profiles[i];
    return NULL;
}

static int hd_skin_hex_digit(char value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

/* A strict CSV allowlist. A caller cannot broaden ownership by passing an
 * arbitrary texture identity. More keys require source/ownership evidence and
 * an explicit code change here. Empty configuration selects the proven key. */
static int hd_skin_keys_parse(HdSkinConfig *out, const char *keys, int enemy) {
    const char *p = keys;
    const HdSkinKey *allowed = enemy ? hd_skin_enemy_keys : hd_skin_player_keys;
    const int count = enemy ? (int)(sizeof hd_skin_enemy_keys / sizeof hd_skin_enemy_keys[0])
                            : (int)(sizeof hd_skin_player_keys / sizeof hd_skin_player_keys[0]);
    out->key_count = 0;
    if (!p || !p[0]) {
        memcpy(out->keys,allowed,(size_t)count*sizeof(*allowed));
        out->key_count=count;
        return 1;
    }
    for (;;) {
        uint32_t texture = 0, palette = 0;
        int i, found = 0, duplicate = 0;
        while (*p && isspace((unsigned char)*p)) ++p;
        for (i = 0; i < 17; ++i) {
            int digit;
            if (!*p) return 0;
            if (i == 8) { if (*p++ != '-') return 0; continue; }
            digit = hd_skin_hex_digit(*p++);
            if (digit < 0) return 0;
            if (i < 8) texture = (texture << 4) | (uint32_t)digit;
            else palette = (palette << 4) | (uint32_t)digit;
        }
        for (i=0;i<count;++i)
            if (texture==allowed[i].texture && palette==allowed[i].palette) found=1;
        if (!found) return 0;
        for (i=0;i<out->key_count;++i)
            if (texture==out->keys[i].texture && palette==out->keys[i].palette) duplicate=1;
        if (!duplicate) {
            if (out->key_count>=HD_SKIN_MAX_KEYS) return 0;
            out->keys[out->key_count].texture=texture;
            out->keys[out->key_count++].palette=palette;
        }
        while (*p && isspace((unsigned char)*p)) ++p;
        if (!*p) return 1;
        if (*p++ != ',') return 0;
    }
}

static int hd_skin_keys_valid(const char *keys) {
    HdSkinConfig config;
    return hd_skin_keys_parse(&config,keys,0);
}

/* 1 = active; 0 = stock/zero strength; -1 = invalid, safely stock. */
static int hd_skin_config_parse_channel(HdSkinConfig *out, const char *id,
                                const char *keys, const char *strength, int enemy) {
    char *end = NULL;
    float amount = HD_SKIN_DEFAULT_STRENGTH;
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    if (!id || !id[0] || !strcmp(id, "stock")) {
        if (!hd_skin_keys_parse(out,keys,enemy)) return -1;
        out->valid=1;
        return 0;
    }
    out->profile = hd_skin_find_profile(id);
    if (!out->profile || !hd_skin_keys_parse(out,keys,enemy)) return -1;
    if (strength && strength[0]) {
        amount = strtof(strength, &end);
        if (end == strength || !end || *end || !isfinite(amount) || amount < 0.0f || amount > 1.0f)
            return -1;
    }
    out->strength = amount;
    out->enabled = amount > 0.0f;
    out->valid = 1;
    return out->enabled;
}

static int hd_skin_config_parse(HdSkinConfig *out, const char *id,
                                const char *keys, const char *strength) {
    return hd_skin_config_parse_channel(out,id,keys,strength,0);
}

static int hd_skin_key_matches(const HdSkinConfig *config,
                                     uint32_t texture, uint32_t palette) {
    int i;
    if (!config || !config->valid) return 0;
    const HdSkinKey *keys=config->diagnostic_scope?config->diagnostic_keys:config->keys;
    const int count=config->diagnostic_scope?config->diagnostic_key_count:config->key_count;
    for (i=0;i<count;++i)
        if (keys[i].texture==texture && keys[i].palette==palette) return 1;
    return 0;
}

static int hd_skin_material_matches(const HdSkinConfig *config,
                                     uint32_t texture, uint32_t palette) {
    return config && config->enabled && config->profile && hd_skin_key_matches(config,texture,palette);
}

static void hd_skin_color_components(uint32_t rgb, float out[3]) {
    out[0] = (float)((rgb >> 16) & 255u) / 255.0f;
    out[1] = (float)((rgb >> 8) & 255u) / 255.0f;
    out[2] = (float)(rgb & 255u) / 255.0f;
}

/* Shared shader kernel. Source saturation gates paint, preserving neutral
 * machined parts. Warm source markings select the accent swatch. The target
 * hue is projected toward gray as needed to stay in gamut at the SAME luma;
 * no clamping/clipped-highlight shortcut is used. Luma is Rec.709-weighted
 * sampled RGB, not a claim of linear-light or physically based rendering. */
#define HD_SKIN_MATERIAL_GLSL \
    "uniform int u_skin_enabled;\n" \
    "uniform vec3 u_skin_primary;\n" \
    "uniform vec3 u_skin_accent;\n" \
    "uniform float u_skin_strength;\n" \
    "uniform int u_skin_preserve_accents;\n" \
    "float hd_skin_accent_mask(vec3 source){\n" \
    "  return smoothstep(0.06,0.20,source.r-source.b)*smoothstep(0.05,0.18,source.g-source.b)*smoothstep(0.25,0.50,source.g/max(source.r,0.0001))*smoothstep(-0.06,-0.01,source.r-source.g);\n" \
    "}\n" \
    "vec3 hd_skin_material(vec3 source){\n" \
    "  if(u_skin_enabled == 0 || u_skin_strength <= 0.0) return source;\n" \
    "  float hi=max(source.r,max(source.g,source.b));\n" \
    "  float lo=min(source.r,min(source.g,source.b));\n" \
    "  float saturation=(hi-lo)/max(hi,0.0001);\n" \
    "  float paint=smoothstep(0.12,0.35,saturation)*smoothstep(0.04,0.16,hi);\n" \
    "  if(u_skin_preserve_accents!=0) paint*=1.0-hd_skin_accent_mask(source);\n" \
    "  float warm=smoothstep(0.03,0.18,source.r-source.b);\n" \
    "  vec3 color=mix(u_skin_primary,u_skin_accent,warm);\n" \
    "  vec3 weights=vec3(0.2126,0.7152,0.0722);\n" \
    "  float luma=dot(source,weights);\n" \
    "  vec3 target=color/max(dot(color,weights),0.0001);\n" \
    "  float extent=max(target.r,max(target.g,target.b))-1.0;\n" \
    "  float gamut=extent>0.0?clamp((1.0-luma)/max(luma*extent,0.0001),0.0,1.0):1.0;\n" \
    "  vec3 mapped=vec3(luma)+gamut*(luma*target-vec3(luma));\n" \
    "  return mix(source,mapped,paint*u_skin_strength);\n" \
    "}\n"

/* CPU reference for unit checks and measured GPU/CPU comparisons; never used
 * to rewrite PNGs or reinterpret the source alpha classes. */
static float hd_skin_smoothstep(float lo, float hi, float value) {
    float t = (value - lo) / (hi - lo);
    if (t < 0.0f) t = 0.0f;
    if (t > 1.0f) t = 1.0f;
    return t * t * (3.0f - 2.0f * t);
}

static float hd_skin_accent_mask_reference(const float source[4]) {
    return hd_skin_smoothstep(0.06f,0.20f,source[0]-source[2]) *
        hd_skin_smoothstep(0.05f,0.18f,source[1]-source[2]) *
        hd_skin_smoothstep(0.25f,0.50f,source[1]/fmaxf(source[0],0.0001f)) *
        hd_skin_smoothstep(-0.06f,-0.01f,source[0]-source[1]);
}

static void hd_skin_material_reference_ex(const HdSkinProfile *profile, float strength,
                                        int preserve_accents,
                                        const float source[4], float output[4]) {
    float primary[3], accent[3], color[3], target[3], luma, color_luma;
    float hi, lo, paint, warm, extent, gamut;
    int i;
    memcpy(output, source, 4 * sizeof(float));
    if (!profile || strength <= 0.0f) return;
    hd_skin_color_components(profile->primary_rgb, primary);
    hd_skin_color_components(profile->accent_rgb, accent);
    hi = fmaxf(source[0], fmaxf(source[1], source[2]));
    lo = fminf(source[0], fminf(source[1], source[2]));
    paint = hd_skin_smoothstep(0.12f, 0.35f, (hi-lo)/fmaxf(hi,0.0001f)) *
            hd_skin_smoothstep(0.04f, 0.16f, hi);
    if(preserve_accents)paint*=1.0f-hd_skin_accent_mask_reference(source);
    warm = hd_skin_smoothstep(0.03f, 0.18f, source[0]-source[2]);
    for (i=0;i<3;++i) color[i] = primary[i] + warm*(accent[i]-primary[i]);
    luma = source[0]*0.2126f + source[1]*0.7152f + source[2]*0.0722f;
    color_luma = fmaxf(color[0]*0.2126f + color[1]*0.7152f + color[2]*0.0722f,0.0001f);
    for (i=0;i<3;++i) target[i] = color[i]/color_luma;
    extent = fmaxf(target[0],fmaxf(target[1],target[2]))-1.0f;
    gamut = extent>0.0f ? fminf(1.0f,fmaxf(0.0f,(1.0f-luma)/fmaxf(luma*extent,0.0001f))) : 1.0f;
    for (i=0;i<3;++i) {
        float mapped=luma+gamut*(luma*target[i]-luma);
        output[i]=source[i]+paint*strength*(mapped-source[i]);
    }
}

static void hd_skin_material_reference(const HdSkinProfile *profile, float strength,
                                        const float source[4], float output[4]) {
    hd_skin_material_reference_ex(profile,strength,0,source,output);
}

#endif
