static int json_get_int(const char *json, const char *key, int def)
{
    /* Raw scan (NOT via json_get_str): integer fields keep bare-decimal
     * semantics and must not go through the hex normalization above.
     * Quoted numbers are accepted too (base 0 handles "123" and "0x7B"). */
    char pattern[128];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(json, pattern);
    if (!p) return def;
    p += strlen(pattern);
    while (*p == ' ' || *p == ':') p++;
    if (*p == '"') p++;
    if (*p == '-' || (*p >= '0' && *p <= '9'))
        return (int)strtol(p, NULL, 0);
    return def;
}
