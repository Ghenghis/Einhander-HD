/* CPU-only fixture for the GL identity patch (claude-einhander). No GL, no window, no DLL.
 * The code under test is NOT retyped here: build_gl_identity_fixture.r0.py extracts the added
 * lines of hunk 1 from the pinned patch into gl_identity_extracted.inc, byte-for-byte.
 * glGetString is a local stub so the capture path runs without any driver.
 *
 * Usage: test_gl_identity.exe RESULT.json STDOUT_CAPTURE.txt
 * Exit 0 only when every check passed; the JSON line records each check. */
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef unsigned char GLubyte;
typedef unsigned int GLenum;
#define GL_VENDOR 0x1F00
#define GL_RENDERER 0x1F01
#define GL_VERSION 0x1F02

static const GLubyte *stub_vendor, *stub_renderer, *stub_version;
static int stub_calls;
static const GLubyte *glGetString(GLenum name) {
    ++stub_calls;
    return name == GL_VENDOR ? stub_vendor : name == GL_RENDERER ? stub_renderer :
           name == GL_VERSION ? stub_version : NULL;
}

#include "gl_identity_extracted.inc"

static int checks, failures;
static char failed_names[2048];
static void check(int ok, const char *name) {
    ++checks;
    if (!ok) {
        ++failures;
        if (strlen(failed_names) + strlen(name) + 2 < sizeof failed_names) {
            strcat(failed_names, name); strcat(failed_names, ",");
        }
    }
}

static int copy_case(const char *in, const char *expect, int expect_truncated) {
    char out[GL_IDENTITY_CHARS];
    memset(out, 'X', sizeof out);
    const int truncated = gl_identity_copy(out, (const GLubyte *)in);
    return truncated == expect_truncated && strcmp(out, expect) == 0;
}

static char *read_all(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    char *buf = (char *)calloc(1, 65536);
    *size = buf ? fread(buf, 1, 65535, f) : 0;
    fclose(f);
    return buf;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    char long127[128], long128[129], long4096[4097], expect127[128];
    memset(long127, 'a', 127); long127[127] = 0;
    memset(long128, 'b', 128); long128[128] = 0;
    memset(long4096, 'c', 4096); long4096[4096] = 0;
    memset(expect127, 'b', 127); expect127[127] = 0;
    char expect4096[128]; memset(expect4096, 'c', 127); expect4096[127] = 0;

    check(copy_case(NULL, "?", 0), "copy_null");
    check(copy_case("", "?", 0), "copy_empty");
    check(copy_case("NVIDIA Corporation", "NVIDIA Corporation", 0), "copy_plain");
    check(copy_case("a\"b\\c\x01\x7f\xc3\xa9", "a?b?c????", 0), "copy_sanitize_quote_backslash_ctrl_del_utf8");
    check(copy_case("\x01\x02", "??", 0), "copy_all_nonprintable_kept_length");
    check(copy_case(" ", " ", 0), "copy_space_kept");
    check(copy_case(long127, long127, 0), "copy_exact_bound_127_not_truncated");
    check(copy_case(long128, expect127, 1), "copy_128_truncated_to_127");
    check(copy_case(long4096, expect4096, 1), "copy_4096_truncated_to_127");

    /* Capture: stdout goes to a file so the one emitted line can be checked exactly. */
    if (!freopen(argv[2], "wb", stdout)) return 3;
    stub_vendor = (const GLubyte *)"NVIDIA Corporation";
    stub_renderer = (const GLubyte *)"FIXTURE GeForce RTX 3090 Ti/PCIe/SSE2";
    stub_version = (const GLubyte *)"4.6.0 FIXTURE 000.00";
    gl_identity_capture();
    const int calls_after_first = stub_calls;
    stub_renderer = (const GLubyte *)"FIXTURE GeForce RTX 3060/PCIe/SSE2";
    gl_identity_capture();          /* first-only: must not query or print again */
    fflush(stdout);
    fclose(stdout);

    size_t size = 0;
    char *text = read_all(argv[2], &size);
    const char *expect_line =
        "psxrecomp: GL identity vendor=\"NVIDIA Corporation\" "
        "renderer=\"FIXTURE GeForce RTX 3090 Ti/PCIe/SSE2\" version=\"4.6.0 FIXTURE 000.00\" truncated=0\n";
    check(text != NULL, "capture_stdout_readable");
    check(text && strcmp(text, expect_line) == 0, "capture_exact_single_line");
    check(calls_after_first == 3, "capture_three_queries");
    check(stub_calls == 3, "capture_first_only_no_second_query");
    check(s_gl_id_captured == 1, "capture_flag_set");
    check(strcmp(s_gl_id_renderer, "FIXTURE GeForce RTX 3090 Ti/PCIe/SSE2") == 0, "capture_cache_immutable");
    free(text);

    FILE *r = fopen(argv[1], "wb");
    if (!r) return 4;
    fprintf(r, "{\"fixture\":\"gl-identity\",\"revision\":\"r0\",\"checks\":%d,\"failures\":%d,"
               "\"failed\":\"%s\",\"passed\":%s,\"gl_used\":false}\n",
            checks, failures, failed_names, failures ? "false" : "true");
    fclose(r);
    return failures ? 1 : 0;
}
