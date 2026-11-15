static uint8_t s_gte_div_table[0x101];
static bool    s_gte_div_table_init = false;
static void gte_init_div_table() {
    for (uint32_t divisor = 0x8000; divisor < 0x10000; divisor += 0x80) {
        uint32_t xa = 512;
        for (unsigned i = 1; i < 5; i++)
            xa = (xa * (1024u * 512u - ((divisor >> 7) * xa))) >> 18;
        s_gte_div_table[(divisor >> 7) & 0xFF] =
            (uint8_t)(((xa + 1) >> 1) - 0x101);
    }
    s_gte_div_table[0x100] = s_gte_div_table[0xFF];
    s_gte_div_table_init = true;
}
static int32_t gte_calc_recip(uint16_t divisor) {
    int32_t x    = 0x101 + s_gte_div_table[(((divisor & 0x7FFF) + 0x40) >> 7)];
    int32_t tmp  = (((int32_t)divisor * -x) + 0x80) >> 8;
    int32_t tmp2 = ((x * (131072 + tmp)) + 0x80) >> 8;
    return tmp2;
}
// count leading zeros of a 16-bit value (0 -> 16)
static inline unsigned gte_clz16(uint16_t v) {
    unsigned n = 0;
    for (int b = 15; b >= 0; --b) { if (v & (1u << b)) break; ++n; }
    return n;
}
static int32_t gte_divide(uint16_t H, uint16_t SZ3, uint32_t& FLAG) {
    if (!s_gte_div_table_init) gte_init_div_table();
    // Hardware: overflow flag + saturate when 2*SZ3 <= H (includes SZ3 == 0).
    if ((uint32_t)SZ3 * 2 <= (uint32_t)H) {
        FLAG |= FLAG_DIV_OVF;
        return 0x1FFFF;
    }
    unsigned shift_bias = gte_clz16(SZ3);
    uint32_t dividend = (uint32_t)H   << shift_bias;
    uint32_t divisor  = (uint32_t)SZ3 << shift_bias;
    uint32_t result = (uint32_t)(((uint64_t)dividend *
                                  (uint32_t)gte_calc_recip((uint16_t)(divisor | 0x8000))
                                  + 32768) >> 16);
    if (result > 0x1FFFF) result = 0x1FFFF;   // 17-bit saturate (no flag; matches hw path)
    return (int32_t)result;
}
