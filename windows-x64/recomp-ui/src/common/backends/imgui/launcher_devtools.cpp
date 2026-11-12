// launcher_devtools.cpp — DEVTOOLS panel: debug-server client + memcard editor.
//
// Windows builds use winsock2 (ws2_32 already linked by recomp_ui.cmake).
// Every server feature degrades to a status line when no debug build is up.

#include "launcher_devtools.h"

#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#include "imgui.h"

// ---- platform socket shim --------------------------------------------------
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
typedef int socklen_t;
typedef SOCKET DevSocket;
#define DEV_INVALID_SOCKET INVALID_SOCKET
static int ws_booted = 0;
static void ws_init(void) {
    if (!ws_booted) { WSADATA w; WSAStartup(MAKEWORD(2, 2), &w); ws_booted = 1; }
}
static DevSocket sock_connect_tcp(unsigned short port) {
    ws_init();
    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) return DEV_INVALID_SOCKET;
    DWORD to = 400;
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, (const char*)&to, sizeof(to));
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, (const char*)&to, sizeof(to));
    struct sockaddr_in a; memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons(port);
    a.sin_addr.s_addr = htonl(0x7F000001);            // 127.0.0.1
    u_long nonblocking = 1;
    ioctlsocket(s, FIONBIO, &nonblocking);
    if (connect(s, (struct sockaddr*)&a, sizeof(a)) != 0) {
        if (WSAGetLastError() != WSAEWOULDBLOCK) {
            closesocket(s); return DEV_INVALID_SOCKET;
        }
        fd_set ready; FD_ZERO(&ready); FD_SET(s, &ready);
        struct timeval timeout = {0, 250000};
        if (select(0, NULL, &ready, NULL, &timeout) <= 0) {
            closesocket(s); return DEV_INVALID_SOCKET;
        }
        int error = 0, length = sizeof(error);
        if (getsockopt(s, SOL_SOCKET, SO_ERROR, (char*)&error, &length) != 0 || error) {
            closesocket(s); return DEV_INVALID_SOCKET;
        }
    }
    nonblocking = 0;
    ioctlsocket(s, FIONBIO, &nonblocking);
    return s;
}
static int sock_send_all(DevSocket s, const char* b, int n) {
    int sent = 0;
    while (sent < n) {
        int r = send(s, b + sent, n - sent, 0);
        if (r <= 0) return 0;
        sent += r;
    }
    return 1;
}
static int sock_recv_line(DevSocket s, char* out, int cap) {
    int i = 0;
    while (i < cap - 1) {
        char c;
        int r = recv(s, &c, 1, 0);
        if (r <= 0) { out[i] = 0; return -1; }
        if (c == '\n') { out[i] = 0; return i; }
        out[i++] = c;
    }
    out[i] = 0;
    return -2;
}
static void sock_close(DevSocket s) { if (s != DEV_INVALID_SOCKET) closesocket(s); }
#else
// POSIX fallback — same API.
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
typedef int DevSocket;
#define DEV_INVALID_SOCKET (-1)
static int sock_connect_tcp(unsigned short port) {
    int s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return -1;
    struct timeval tv = {0, 400 * 1000};
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    struct sockaddr_in a; memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons(port);
    a.sin_addr.s_addr = htonl(0x7F000001);
    int flags = fcntl(s, F_GETFL, 0);
    fcntl(s, F_SETFL, flags | O_NONBLOCK);
    if (connect(s, (struct sockaddr*)&a, sizeof(a)) != 0) {
        fd_set ready; FD_ZERO(&ready); FD_SET(s, &ready);
        struct timeval timeout = {0, 250000};
        if (select(s + 1, NULL, &ready, NULL, &timeout) <= 0) { close(s); return -1; }
        int error = 0; socklen_t length = sizeof(error);
        if (getsockopt(s, SOL_SOCKET, SO_ERROR, &error, &length) != 0 || error) { close(s); return -1; }
    }
    fcntl(s, F_SETFL, flags);
    return s;
}
static int sock_send_all(int s, const char* b, int n) {
    int sent = 0;
    while (sent < n) {
        int r = (int)send(s, b + sent, n - sent, 0);
        if (r <= 0) return 0;
        sent += r;
    }
    return 1;
}
static int sock_recv_line(int s, char* out, int cap) {
    int i = 0;
    while (i < cap - 1) {
        char c; ssize_t r = recv(s, &c, 1, 0);
        if (r <= 0) { out[i] = 0; return -1; }
        if (c == '\n') { out[i] = 0; return i; }
        out[i++] = c;
    }
    out[i] = 0; return -2;
}
static void sock_close(int s) { if (s >= 0) close(s); }
#endif

// ---- debug-server client ----------------------------------------------------
static unsigned short s_dbg_port = 4370;
static char s_last_resp[16384] = "";
static int  s_connected = 0;

static void configure_debug_port(void) {
    static bool initialized = false;
    if (initialized) return;
    initialized = true;
    const char* value = getenv("EIN_DEBUG_PORT");
    if (!value || !value[0]) return;
    char* end = NULL;
    long port = strtol(value, &end, 10);
    if (end && !*end && port > 0 && port <= 65535)
        s_dbg_port = (unsigned short)port;
}

const char* launcher_devtools_send(const char* json_line) {
    configure_debug_port();
    DevSocket s = sock_connect_tcp(s_dbg_port);
    s_connected = 0;
    if (s == DEV_INVALID_SOCKET) {
        snprintf(s_last_resp, sizeof(s_last_resp), "No debug server at 127.0.0.1:%u. Launch a debug-enabled game and retry.", s_dbg_port);
        return s_last_resp;
    }
    char line[2048];
    if (!json_line || !json_line[0] || strlen(json_line) + 2 > sizeof(line)) {
        sock_close(s);
        snprintf(s_last_resp, sizeof(s_last_resp), "Command is empty or exceeds the 2046-byte limit.");
        return s_last_resp;
    }
    snprintf(line, sizeof(line), "%s\n", json_line);
    if (!sock_send_all(s, line, (int)strlen(line))) {
        sock_close(s);
        snprintf(s_last_resp, sizeof(s_last_resp), "Debug command could not be sent.");
        return s_last_resp;
    }
    int received = sock_recv_line(s, s_last_resp, sizeof(s_last_resp));
    sock_close(s);
    if (received <= 0) {
        snprintf(s_last_resp, sizeof(s_last_resp), "%s", received == -2
            ? "Response exceeds the panel limit. Use a bounded probe in the browser development workspace."
            : "Debug server did not return a complete response before the timeout.");
        return s_last_resp;
    }
    s_connected = 1;
    return s_last_resp;
}

int launcher_devtools_connected(void) { return s_connected; }

// ---- .mcd card editor -------------------------------------------------------
#define CARD_SIZE    131072
#define SECTOR       128
#define BLOCK_SZ     8192
#define DATA_START   (64 * SECTOR)
#define NDIR         15

static uint8_t xsum(const uint8_t* b) {
    uint8_t x = 0; for (int i = 0; i < 127; i++) x ^= b[i]; return x;
}

static int card_load(const char* path, uint8_t* d /*CARD_SIZE*/) {
    if (!path || !path[0] || !d) return -1;
    FILE* f = fopen(path, "rb");
    if (!f) return -1;
    size_t n = fread(d, 1, CARD_SIZE, f);
    fclose(f);
    if (n != CARD_SIZE || d[0] != 'M' || d[1] != 'C') return -1;
    return 0;
}

static int card_save(const char* path, const uint8_t* d) {
    if (!path || !path[0] || !d) return -1;
    FILE* f = fopen(path, "wb");
    if (!f) return -1;
    size_t n = fwrite(d, 1, CARD_SIZE, f);
    int ok = (fflush(f) == 0); ok &= (fclose(f) == 0);
    return (n == CARD_SIZE && ok) ? 0 : -1;
}

int launcher_devtools_card_list(const char* path, LauncherDevCardBlock* out) {
    uint8_t* d = (uint8_t*)malloc(CARD_SIZE);
    if (!d) return -1;
    if (card_load(path, d) != 0) { free(d); return -1; }
    for (int i = 0; i < NDIR; i++) {
        const uint8_t* f = d + SECTOR * (1 + i);
        out[i].free = (f[0] == 0xA0);
        out[i].used = (f[0] >= 0x51 && f[0] <= 0x53);
        snprintf(out[i].code, sizeof(out[i].code), "%.20s", f + 10);
        if (f[0] == 0xA0) out[i].code[0] = 0;
    }
    free(d);
    return NDIR;
}

int launcher_devtools_card_inject(const char* path, int slot, const char* name) {
    if (!name || !name[0]) name = "EINHANDER";
    uint8_t* d = (uint8_t*)malloc(CARD_SIZE);
    if (!d) return -1;
    if (card_load(path, d) != 0) { free(d); return -1; }
    if (slot < 0) {
        for (int i = 0; i < NDIR; i++) {           // first free slot
            if (d[SECTOR * (1 + i)] == 0xA0) { slot = i; break; }
        }
    }
    if (slot < 0 || slot >= NDIR || d[SECTOR * (1 + slot)] != 0xA0) { free(d); return -1; }

    // directory entry (128B): status + size + link + product/name + checksum
    uint8_t* f = d + SECTOR * (1 + slot);
    memset(f, 0, SECTOR);
    f[0] = 0x51;                                   // first+last block, used
    f[4] = BLOCK_SZ & 0xFF; f[5] = (BLOCK_SZ >> 8) & 0xFF;
    f[8] = 0xFF; f[9] = 0xFF;
    char code[24]; snprintf(code, sizeof(code), "BASCUS-94243%s", name);
    memcpy(f + 10, code, strlen(code) > 20 ? 20 : strlen(code));
    f[127] = xsum(f);

    // block data: title frame "SC" + icon flag + region frame "SCUS-94243"
    uint8_t* b = d + DATA_START + slot * BLOCK_SZ;
    memset(b, 0, BLOCK_SZ);
    b[0] = 'S'; b[1] = 'C'; b[2] = 0x11; b[3] = 1; // SC, 1 icon frame, 1 block
    const char* title = "EINHANDER";
    memcpy(b + 4, title, strlen(title));
    char rcode[32]; snprintf(rcode, sizeof(rcode), "SCUS-94243%s", name);
    memcpy(b + SECTOR, rcode, strlen(rcode) > 28 ? 28 : strlen(rcode));

    int rc = card_save(path, d);
    free(d);
    return rc;
}

int launcher_devtools_card_delete(const char* path, int slot) {
    uint8_t* d = (uint8_t*)malloc(CARD_SIZE);
    if (!d) return -1;
    if (card_load(path, d) != 0 || slot < 0 || slot >= NDIR) { free(d); return -1; }
    uint8_t* f = d + SECTOR * (1 + slot);
    memset(f, 0, SECTOR);
    f[0] = 0xA0; f[8] = 0xFF; f[9] = 0xFF;
    f[127] = xsum(f);
    int rc = card_save(path, d);
    free(d);
    return rc;
}

// ---- development workspace -------------------------------------------------
// Only explicit clicks contact the game. Browser assists run independently of
// launcher redraws, so native widgets never pretend to freeze RAM in the game.
static char s_raw_cmd[1024] = "{\"cmd\":\"gpu_state\"}";
static char s_cheat_status[256] = "";
static char s_card_status[256] = "";
static char s_card_name[64] = "PILOT01";
static int s_card_slot = 0, s_ss_slot = 0;
static bool s_bot_enabled = false;
static char s_demo_status[256] = "At the title screen, release input and wait for native demo play.";
static LauncherDevCardBlock s_blocks[15];
static int s_blocks_slot = -1, s_blocks_n = 0;
static bool s_research_writes = false;
static char s_probe_status[256] = "";

static bool response_ok(const char* response) {
    if (!response) return false;
    const char* p = strstr(response, "\"ok\"");
    if (!p || !(p = strchr(p, ':'))) return false;
    do { ++p; } while (*p == ' ' || *p == '\t');
    return strncmp(p, "true", 4) == 0;
}

static bool read_value(uint32_t address, int width, uint32_t* value) {
    if (!value || width < 1 || width > 4) return false;
    char json[160];
    snprintf(json, sizeof(json), "{\"cmd\":\"read_ram\",\"addr\":\"0x%08X\",\"len\":%d}", address, width);
    const char* response = launcher_devtools_send(json);
    if (!response_ok(response)) return false;
    const char* hex = strstr(response, "\"hex\"");
    if (!hex || !(hex = strchr(hex, ':'))) return false;
    do { ++hex; } while (*hex == ' ' || *hex == '\t');
    if (*hex++ != '"') return false;
    const char* end = strchr(hex, '"');
    if (!end || end - hex < width * 2) return false;
    uint32_t result = 0;
    for (int i = 0; i < width; ++i) {
        char byte[3] = {hex[i * 2], hex[i * 2 + 1], 0};
        if (!byte[0] || !byte[1] || !strchr("0123456789abcdefABCDEF", byte[0]) || !strchr("0123456789abcdefABCDEF", byte[1])) return false;
        result |= (uint32_t)strtoul(byte, NULL, 16) << (i * 8);
    }
    *value = result;
    return true;
}

static bool write_value(uint32_t address, uint32_t value, int width) {
    for (int i = 0; i < width; ++i) {
        char json[160];
        snprintf(json, sizeof(json), "{\"cmd\":\"write_ram\",\"addr\":\"0x%08X\",\"val\":\"0x%02X\"}", address + i, (value >> (i * 8)) & 255);
        if (!response_ok(launcher_devtools_send(json))) {
            snprintf(s_cheat_status, sizeof(s_cheat_status), "Write failed at byte %d of %d. See the server response below.", i + 1, width);
            return false;
        }
    }
    uint32_t actual = 0;
    if (!read_value(address, width, &actual)) {
        snprintf(s_cheat_status, sizeof(s_cheat_status), "Write acknowledged at 0x%08X; readback could not be verified.", address);
        return false;
    }
    snprintf(s_cheat_status, sizeof(s_cheat_status), actual == value
        ? "0x%08X: wrote %u; %d-byte readback matches."
        : "0x%08X: wrote %u; %d-byte readback changed (game may update this field).",
        address, value, width);
    return actual == value;
}

static void dbg_status_line(void) {
    configure_debug_port();
    ImGui::TextDisabled("127.0.0.1:%u  |  %s", s_dbg_port,
        s_connected ? "last request answered" : "connection not verified");
}

static void workspace_link(void) {
    const char* url = getenv("EIN_DEV_URL");
    if (!url || !url[0]) url = "http://127.0.0.1:8090";
#if IMGUI_VERSION_NUM >= 19100
    ImGui::TextLinkOpenURL("Open development workspace", url);
#else
    ImGui::TextWrapped("Development workspace: %s", url);
#endif
    ImGui::TextWrapped("Start tools/ein_bridge.py for persistent assists, asset-pack authoring and visual comparison.");
}

static void workspace_section_link(const char* label, const char* suffix) {
    const char* base = getenv("EIN_DEV_URL");
    if (!base || !base[0]) base = "http://127.0.0.1:8090";
    char url[1200];
    size_t length = strcspn(base, "?#");
    while (length && base[length - 1] == '/') --length;
    snprintf(url, sizeof(url), "%.*s/%s", (int)length, base, suffix);
#if IMGUI_VERSION_NUM >= 19100
    ImGui::TextLinkOpenURL(label, url);
#else
    ImGui::TextWrapped("%s: %s", label, url);
#endif
}

static unsigned recorder_response_count(const char* field) {
    char key[64]; snprintf(key, sizeof(key), "\"%s\":", field);
    const char* value = strstr(s_last_resp, key);
    return value ? (unsigned)strtoul(value + strlen(key), NULL, 10) : 0;
}

static void draw_research_recorder(void) {
    static char status[256] = "Recorder status has not been refreshed.";
    workspace_section_link("Open research recorder", "#research");
    ImGui::TextWrapped("Start and mark bounded read-only runs in the workspace. Source receipts are sampled; CPU VRAM can be stale. Recorder settings and event history are managed there.");
    if (ImGui::Button("Refresh recorder status")) {
        launcher_devtools_send("{\"cmd\":\"research_capture\",\"op\":\"status\"}");
        if (s_connected &&
            strstr(s_last_resp, "\"contract\":\"ein-research-v1\"")) {
            snprintf(status, sizeof(status), "%s | sources %u | receipts %u | events %u | files %u",
                strstr(s_last_resp, "\"active\":true") ? "Recording" : "Inactive",
                recorder_response_count("sources"), recorder_response_count("records"),
                recorder_response_count("events"), recorder_response_count("files"));
        } else snprintf(status, sizeof(status), "Recorder unavailable or runtime does not support ein-research-v1. See server response.");
    }
    ImGui::TextWrapped("%s", status);
    ImGui::Separator();
}

static void probe_field(const char* label, uint32_t address, int width, const char* evidence) {
    ImGui::PushID(label);
    if (ImGui::SmallButton("Read")) {
        uint32_t value = 0;
        if (read_value(address, width, &value))
            snprintf(s_probe_status, sizeof(s_probe_status), "%s: %u (0x%X), %d byte(s) at 0x%08X", label, value, value, width, address);
        else
            snprintf(s_probe_status, sizeof(s_probe_status), "%s: read failed. See the server response below.", label);
    }
    ImGui::SameLine();
    ImGui::Text("%s  [0x%08X / u%d]", label, address, width * 8);
    ImGui::TextDisabled("%s", evidence);
    ImGui::PopID();
}

static void draw_overview(void) {
    ImGui::TextDisabled("DEVELOPMENT OPERATIONS");
    ImGui::TextWrapped("A workspace for playable experiments, measured graphics and documented game state.");
    ImGui::Spacing();
    if (ImGui::Button("Check game connection")) launcher_devtools_send("{\"cmd\":\"gpu_state\"}");
    ImGui::SameLine();
    if (ImGui::Button("Release injected input")) {
        s_bot_enabled = false;
        launcher_devtools_send("{\"cmd\":\"clear_input\"}");
    }
    ImGui::Spacing();
    ImGui::TextWrapped("PLAYER: lives and invulnerability timer controls with readback.");
    ImGui::TextWrapped("ARMORY: mapped ammo and pod fields, with research writes gated.");
    ImGui::TextWrapped("ENCOUNTERS: capture checkpoints; stage and boss warps require verification.");
    ImGui::TextWrapped("GRAPHICS: windowed launch presets and real renderer captures.");
    ImGui::TextWrapped("RESEARCH: address probes, trace tools and the original debug console.");
    ImGui::Separator();
    workspace_link();
}

static void draw_player(void) {
    ImGui::TextDisabled("PLAYER ASSISTS / US SCUS-94243");
    ImGui::TextWrapped("Changes apply once to a running game. Countdown timers resume immediately. Persistent assists are managed in the browser workspace.");
    static int lives = 3, invincibility = 165;
    ImGui::SetNextItemWidth(110);
    ImGui::InputInt("Lives (0-99)", &lives);
    if (lives < 0) lives = 0;
    if (lives > 99) lives = 99;
    if (ImGui::Button("Set lives")) write_value(0x800813C4, (uint32_t)lives, 1);
    ImGui::SameLine();
    if (ImGui::Button("Read lives")) {
        uint32_t v;
        if (read_value(0x800813C4, 1, &v)) lives = (int)v;
    }
    ImGui::SetNextItemWidth(110);
    ImGui::InputInt("Invulnerability timer (0-255)", &invincibility);
    if (invincibility < 0) invincibility = 0;
    if (invincibility > 255) invincibility = 255;
    if (ImGui::Button("Set timer")) write_value(0x80085718, (uint32_t)invincibility, 1);
    ImGui::SameLine();
    if (ImGui::Button("Clear invulnerability")) write_value(0x80085718, 0, 1);
    ImGui::Separator();
    probe_field("Lives", 0x800813C4, 1, "Mapped in DEBUG_FINDINGS; validate behavior in the active game mode.");
    probe_field("Invulnerability countdown", 0x80085718, 1, "Mapped timer; a one-time write does not establish an infinite lock.");
    ImGui::Spacing();
    workspace_link();
}

static void draw_armory(void) {
    ImGui::TextDisabled("LOADOUT LABORATORY");
    ImGui::TextWrapped("Inspect ammo and durability without guessing gun identity, capacity, or pickup retention. These legacy fields require gameplay verification for each ship and slot.");
    probe_field("Active gunpod ammo", 0x80084832, 2, "Legacy mapped u16; gun identity and ownership are not established.");
    probe_field("Secondary ammo counter", 0x80084834, 2, "Legacy mapped u16; semantics can vary by equipment.");
    ImGui::Separator();
    ImGui::Checkbox("Enable experimental writes", &s_research_writes);
    ImGui::TextWrapped("Readback proves bytes changed; it does not prove equipment behavior. Restore stock by restarting the game.");
    static int ammo = 99, ammo2 = 15;
    ImGui::SetNextItemWidth(110);
    ImGui::InputInt("Ammo A (0-65535)", &ammo);
    ImGui::SetNextItemWidth(110);
    ImGui::InputInt("Ammo B (0-65535)", &ammo2);
    if (ammo < 0) ammo = 0;
    if (ammo > 65535) ammo = 65535;
    if (ammo2 < 0) ammo2 = 0;
    if (ammo2 > 65535) ammo2 = 65535;
    ImGui::BeginDisabled(!s_research_writes);
    if (ImGui::Button("Apply ammo A")) write_value(0x80084832, (uint32_t)ammo, 2);
    ImGui::SameLine();
    if (ImGui::Button("Apply ammo B")) write_value(0x80084834, (uint32_t)ammo2, 2);
    ImGui::EndDisabled();
    ImGui::Spacing();
    static int pod_slot = 0, durability = 960;
    static const char* pod_names[] = {"Primary A / 0x80084830", "Primary B / 0x80084980", "Secondary A / 0x80084B62", "Secondary B / 0x80084CB2"};
    static const uint32_t pod_addresses[] = {0x80084830, 0x80084980, 0x80084B62, 0x80084CB2};
    ImGui::SetNextItemWidth(240);
    ImGui::Combo("Pod candidate", &pod_slot, pod_names, 4);
    ImGui::SetNextItemWidth(110);
    ImGui::InputInt("Durability (0-65535)", &durability);
    if (durability < 0) durability = 0;
    if (durability > 65535) durability = 65535;
    ImGui::BeginDisabled(!s_research_writes);
    if (ImGui::Button("Apply candidate durability")) write_value(pod_addresses[pod_slot], (uint32_t)durability, 2);
    ImGui::EndDisabled();
    ImGui::TextWrapped("0x03C0 (960) comes from legacy pod-integrity notes. These are player-pod candidates; enemy and boss shielding remain unmapped.");
    ImGui::Spacing();
    ImGui::BeginDisabled();
    ImGui::Button("Equip specific weapon");
    ImGui::SameLine();
    ImGui::Button("Lock weapon ownership");
    ImGui::EndDisabled();
    ImGui::TextWrapped("Needs research: weapon IDs, per-ship mount limits, drop logic, pickup timers and enemy/boss shield structures. No verified writes are available yet.");
}

static void draw_encounters(void) {
    ImGui::TextDisabled("MISSION / BOSS WORKBENCH");
    ImGui::TextWrapped("Revisit encounters using captured checkpoints after validating restore behavior. Capture a separate checkpoint at each mission or boss; a RAM stage number alone does not initialize overlays, enemies or geometry.");
    ImGui::BeginDisabled();
    ImGui::Button("Warp to stage");
    ImGui::SameLine();
    ImGui::Button("Fight selected boss");
    ImGui::SameLine();
    ImGui::Button("Edit enemy shields");
    ImGui::EndDisabled();
    ImGui::TextWrapped("Unavailable: verified scene-loading sequence and encounter/shield addresses. Prior stage-region writes can black-screen the game. The Storage tab exposes explicit checkpoint capture and experimental restore.");
    ImGui::Separator();
    if (ImGui::Button("Inspect game frame")) launcher_devtools_send("{\"cmd\":\"frame\"}");
    ImGui::SameLine();
    if (ImGui::Button("Inspect save-state support")) launcher_devtools_send("{\"cmd\":\"savestate_status\"}");
    ImGui::Spacing();
    ImGui::TextWrapped("Validation order: title and ship selection, stage entrance, midboss, route branches, stage boss, transition, reload. Preserve a stock comparison capture for every encounter.");
}

static void apply_graphics_preset(LauncherModel* m, int width, int raster) {
    if (!m) return;
    m->s.fullscreen = 0;
    if (m->has_window_size) m->s.window_width = width;
    if (m->has_supersampling) m->s.supersampling = raster;
    snprintf(s_cheat_status, sizeof(s_cheat_status), "Next launch: windowed, %d px width, %dx raster. Apply with the launcher's normal settings flow.", width, raster);
}

static void draw_graphics(LauncherModel* m) {
    workspace_section_link("Open material laboratory", "?skinArea=materials#skins");
    ImGui::TextDisabled("WINDOWED QUALITY / NEXT LAUNCH");
    ImGui::TextWrapped("Window size, internal raster scale and replacement-art detail are separate measurements. A large screenshot alone cannot certify a 4K remaster.");
    ImGui::BeginDisabled(!m || !m->has_window_size || !m->has_supersampling);
    if (ImGui::Button("Desktop / 1280 px / 6x")) apply_graphics_preset(m, 1280, 6);
    ImGui::SameLine();
    if (ImGui::Button("1440p target / 2560 px / 6x")) apply_graphics_preset(m, 2560, 6);
    if (ImGui::Button("4K target / 3840 px / 9x")) apply_graphics_preset(m, 3840, 9);
    ImGui::EndDisabled();
    ImGui::TextWrapped("Height follows the selected aspect ratio; 2560x1440 and 3840x2160 require 16:9. Native 4:3 remains available. GPU cost and pacing must be measured for the selected scale.");
    if (m) {
        ImGui::Text("Window: %s  |  Fullscreen: %s", launcher_model_window_size_label(m), launcher_model_fullscreen_label(m));
        ImGui::Text("Raster: %s  |  Aspect: %s", launcher_model_supersampling_label(m), launcher_model_aspect_label(m));
    }
    ImGui::Separator();
    ImGui::TextDisabled("CAPTURE / PROOF");
    if (ImGui::Button("Capture composed frame")) launcher_devtools_send("{\"cmd\":\"present_shot\",\"path\":\"dev_present.png\"}");
    ImGui::SameLine();
    if (ImGui::Button("Check capture completion")) launcher_devtools_send("{\"cmd\":\"present_shot_seq\"}");
    if (ImGui::Button("GPU dimensions")) launcher_devtools_send("{\"cmd\":\"gpu_state\"}");
    ImGui::SameLine();
    if (ImGui::Button("Measure frame pacing")) launcher_devtools_send("{\"cmd\":\"frame_perf\"}");
    ImGui::SameLine();
    if (ImGui::Button("Geometry coverage")) launcher_devtools_send("{\"cmd\":\"geom_correction\"}");
    ImGui::TextWrapped("Capture is queued for the next present; only completion with wrote=1 proves a file was saved. dev_present.png is written in the running game's working directory.");
    ImGui::Separator();
    ImGui::TextDisabled("SKINS / EFFECTS AUTHORING");
    ImGui::TextWrapped("The browser workspace provides pack inspection and authoring. Ship skins, weapon camouflage and explosion/fire replacements need an identified source texture, palette-safe replacement, runtime matching and in-game review before activation.");
    workspace_link();
}

static void draw_research_addresses(void) {
    ImGui::TextDisabled("ADDRESS NOTEBOOK / RESEARCH CANDIDATES");
    ImGui::TextWrapped("US SCUS-94243 only. Legacy notes are hypotheses until behavior is verified. Raw reads are available here; unknown scene, boss and ship structures are intentionally unwritable.");
    probe_field("Hyper flag", 0x80085709, 1, "Legacy note: 0xFF on; behavior unverified in current build.");
    probe_field("Hits counter", 0x80085710, 1, "Legacy notes disagree on width; only a byte is read here.");
    probe_field("Pod durability A", 0x80084830, 2, "Legacy candidate: 0x03C0; requires equipment and scene verification.");
    probe_field("Pod durability B", 0x80084980, 2, "Legacy candidate: 0x03C0; requires equipment and scene verification.");
    probe_field("Secondary integrity A", 0x80084B62, 2, "Legacy candidate; not a verified enemy shield field.");
    probe_field("Secondary integrity B", 0x80084CB2, 2, "Legacy candidate; not a verified enemy shield field.");
    probe_field("Score multiplier", 0x80081326, 1, "Legacy note: 0x28; only the documented byte is accessed.");
    ImGui::Checkbox("Enable experimental writes##research", &s_research_writes);
    ImGui::BeginDisabled(!s_research_writes);
    if (ImGui::Button("Hyper flag on")) write_value(0x80085709, 255, 1);
    ImGui::SameLine();
    if (ImGui::Button("Hyper flag off")) write_value(0x80085709, 0, 1);
    if (ImGui::Button("Legacy score multiplier / 40")) write_value(0x80081326, 40, 1);
    ImGui::SameLine();
    if (ImGui::Button("Legacy gallery flags")) {
        if (write_value(0x801FEC9C, 65535, 2)) write_value(0x801FEC9E, 65535, 2);
    }
    ImGui::EndDisabled();
    ImGui::TextWrapped("Legacy writes can change game state. Byte readback is reported; unlock and gameplay effects still require independent verification.");
    ImGui::Separator();
}

static void draw_console(void) {
    ImGui::TextDisabled("RAW DEBUG COMMAND");
    ImGui::TextWrapped("Commands run against the selected local debug server. read_ram uses len and returns hex; write_ram writes exactly one byte.");
    ImGui::SetNextItemWidth(-80);
    bool enter = ImGui::InputText("##raw", s_raw_cmd, sizeof(s_raw_cmd), ImGuiInputTextFlags_EnterReturnsTrue);
    ImGui::SameLine();
    if (ImGui::Button("Send") || enter) launcher_devtools_send(s_raw_cmd);
    if (ImGui::Button("Read 16 RAM bytes")) snprintf(s_raw_cmd, sizeof(s_raw_cmd), "{\"cmd\":\"read_ram\",\"addr\":\"0x80084830\",\"len\":16}");
    ImGui::SameLine();
    if (ImGui::Button("Copy response")) ImGui::SetClipboardText(s_last_resp);
}

void launcher_devtools_draw(LauncherModel* m, const LauncherTheme* th) {
    if (th) ImGui::TextColored(ImVec4(th->accent2.r, th->accent2.g, th->accent2.b, th->accent2.a), "DEV CONTROL CENTER");
    else ImGui::TextUnformatted("DEV CONTROL CENTER");
    dbg_status_line();
    ImGui::Separator();
    if (ImGui::BeginTabBar("##dev_workspace", ImGuiTabBarFlags_FittingPolicyScroll)) {
        if (ImGui::BeginTabItem("Overview")) { draw_overview(); ImGui::EndTabItem(); }
        if (ImGui::BeginTabItem("Player")) { draw_player(); ImGui::EndTabItem(); }
        if (ImGui::BeginTabItem("Armory")) { draw_armory(); ImGui::EndTabItem(); }
        if (ImGui::BeginTabItem("Encounters")) { draw_encounters(); ImGui::EndTabItem(); }
        if (ImGui::BeginTabItem("Graphics")) { draw_graphics(m); ImGui::EndTabItem(); }
        if (ImGui::BeginTabItem("Input")) {
    // -- PAD injection ---------------------------------------------------------
    ImGui::TextDisabled("PAD — virtual input");
    struct PadBtn { const char* n; int hex; };
    // active-low word: idle 0xFFFF; press = 0xFFFF & ~bit (real PS1 bit order)
    static const PadBtn kPadReal[] = {
        {"Up",0xFFFF&~0x0010},{"Down",0xFFFF&~0x0040},
        {"Left",0xFFFF&~0x0080},{"Right",0xFFFF&~0x0020},
        {"Triangle",0xFFFF&~0x1000},{"Circle",0xFFFF&~0x2000},
        {"Cross",0xFFFF&~0x4000},{"Square",0xFFFF&~0x8000},
        {"Start",0xFFFF&~0x0008},{"Select",0xFFFF&~0x0001},
    };
    for (int i = 0; i < 10; i++) {
        if (i && (i % 5)) ImGui::SameLine();
        if (ImGui::SmallButton(kPadReal[i].n)) {
            char j[160];
            snprintf(j, sizeof(j),
                "{\"cmd\":\"press\",\"buttons\":%d,\"frames\":12}",
                kPadReal[i].hex);
            launcher_devtools_send(j);
        }
    }
    ImGui::Separator();

    // -- Native attract mode: the game supplies its own recorded inputs. -------
    ImGui::TextDisabled("NATIVE DEMO PLAY");
    if (ImGui::Button("Watch native demo")) {
        s_bot_enabled = false;
        const char* response = launcher_devtools_send("{\"cmd\":\"clear_input\"}");
        snprintf(s_demo_status, sizeof(s_demo_status), "%s",
            strstr(response, "\"ok\":true")
                ? "Input released. Wait at the title for the game's native attract sequence."
                : "Input release failed. Check the debug server connection.");
    }
    ImGui::SameLine();
    if (ImGui::Button("Exit demo (Start)")) {
        s_bot_enabled = false;
        launcher_devtools_send("{\"cmd\":\"clear_input\"}");
        const char* response = launcher_devtools_send("{\"cmd\":\"press\",\"buttons\":65527,\"frames\":12}");
        snprintf(s_demo_status, sizeof(s_demo_status), "%s",
            strstr(response, "\"ok\":true") ? "Start sent; injected input expires after 12 frames."
                                               : "Exit command failed. Check the debug server connection.");
    }
    if (ImGui::Button("Release native input")) {
        s_bot_enabled = false;
        const char* response = launcher_devtools_send("{\"cmd\":\"clear_input\"}");
        snprintf(s_demo_status, sizeof(s_demo_status), "%s",
            strstr(response, "\"ok\":true") ? "Input released. Keyboard and controller are available."
                                               : "Input release failed. Check the debug server connection.");
    }
    ImGui::TextWrapped("%s", s_demo_status);
    ImGui::TextWrapped("Browser holds and Robin run separately. Use Release all controls in the development workspace to stop those assists.");
    ImGui::Separator();


            ImGui::TextWrapped("Robin's persistent autoplay and configuration live in the browser development workspace.");
            workspace_link();
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Research")) {
            draw_research_recorder();
            draw_research_addresses();
    // -- DIAGNOSTICS: preset probes that fill the raw console ----------------
    // Clicking a preset copies its JSON into the console box; the user can then
    // hit send or edit params. This covers the deep debug-server surface
    // without hardcoding per-command widgets.
    ImGui::TextDisabled("DIAGNOSTICS — click to load command");
    struct Preset { const char* label; const char* json; };
    static const Preset kDiag[] = {
        {"gpu state",     "{\"cmd\":\"gpu_state\"}"},
        {"gpu opcodes",   "{\"cmd\":\"gpu_opcodes\"}"},
        {"game options",  "{\"cmd\":\"game_options\"}"},
        {"frame pacing",  "{\"cmd\":\"frame_perf\"}"},
        {"present ring",  "{\"cmd\":\"present_ring\",\"n\":12}"},
        {"geom fix",      "{\"cmd\":\"geom_correction\"}"},
        {"quads",         "{\"cmd\":\"capture_quads\"}"},
        {"vram cpu",      "{\"cmd\":\"vram_peek\",\"x\":512,\"y\":256,\"w\":16,\"h\":16}"},
        {"vram fbo",      "{\"cmd\":\"gl_fbo_peek\",\"x\":512,\"y\":256,\"w\":16,\"h\":16}"},
        {"memcard",       "{\"cmd\":\"mc_status\"}"},
        {"pad",           "{\"cmd\":\"pad_status\"}"},
        {"savestate?",    "{\"cmd\":\"savestate_status\"}"},
    };
    static const Preset kTrace[] = {
        {"card trace",    "{\"cmd\":\"card_trace_dump\"}"},
        {"card txn",      "{\"cmd\":\"card_txn_dump\"}"},
        {"sio trace",     "{\"cmd\":\"sio_trace\"}"},
        {"wtrace dump",   "{\"cmd\":\"wtrace_dump\"}"},
        {"wtrace stats",  "{\"cmd\":\"wtrace_stats\"}"},
        {"fntrace dump",  "{\"cmd\":\"fntrace_dump\"}"},
        {"bios dump",     "{\"cmd\":\"bioscall_dump\"}"},
        {"ring stats",    "{\"cmd\":\"gpu_ring_stats\"}"},
        {"ring dump",     "{\"cmd\":\"display_ring_get\"}"},
    };
    for (int i = 0; i < 12; i++) {
        if (i && (i % 3)) ImGui::SameLine();
        if (ImGui::SmallButton(kDiag[i].label))
            snprintf(s_raw_cmd, sizeof(s_raw_cmd), "%s", kDiag[i].json);
    }
    if (ImGui::TreeNode("trace probes##tr")) {
        for (int i = 0; i < 9; i++) {
            if (i && (i % 3)) ImGui::SameLine();
            if (ImGui::SmallButton(kTrace[i].label))
                snprintf(s_raw_cmd, sizeof(s_raw_cmd), "%s", kTrace[i].json);
        }
        ImGui::TreePop();
    }
    ImGui::Spacing();
    ImGui::TextWrapped("Loaded command: %s", s_raw_cmd);
    if (ImGui::Button("Run loaded command")) launcher_devtools_send(s_raw_cmd);


    ImGui::Spacing();
    if (ImGui::Button("Compare CPU / GPU VRAM"))
        launcher_devtools_send("{\"cmd\":\"gl_vram_diff\"}");
    ImGui::TextWrapped("Reports mismatched pixels from the renderer's coherent comparison, including sample coordinates.");

            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Storage")) {
    // -- SAVESTATES -------------------------------------------------------------
    ImGui::TextDisabled("SAVESTATES (load is unreliable — can corrupt VRAM)");
    ImGui::SetNextItemWidth(80);
    ImGui::InputInt("slot", &s_ss_slot);
    if (s_ss_slot < 0) s_ss_slot = 0;
    if (s_ss_slot > 9) s_ss_slot = 9;
    ImGui::SameLine();
    if (ImGui::Button("Save")) {
        char j[160]; snprintf(j, sizeof(j),
            "{\"cmd\":\"savestate\",\"op\":\"save\",\"slot\":%d}", s_ss_slot);
        launcher_devtools_send(j);
    }
    ImGui::SameLine();
    static bool allow_restore = false;
    ImGui::Checkbox("Allow experimental restore", &allow_restore);
    ImGui::BeginDisabled(!allow_restore);
    if (ImGui::Button("Load")) {
        char j[160]; snprintf(j, sizeof(j),
            "{\"cmd\":\"savestate\",\"op\":\"load\",\"slot\":%d}", s_ss_slot);
        launcher_devtools_send(j);
    }
    ImGui::Separator();

    ImGui::EndDisabled();

    // -- MEMORY CARD EDITOR ------------------------------------------------------
    ImGui::TextDisabled("MEMORY CARD EDITOR (writes the configured .mcd directly)");
    for (int slot = 0; slot < 2; slot++) {
        const char* p = m ? m->s.memcard_path[slot] : NULL;
        ImGui::Text("card%d: %s", slot, p && p[0] ? p : "(none)");
        ImGui::SameLine();
        if (ImGui::SmallButton(slot ? "list##1" : "list##0")) {
            s_blocks_n = launcher_devtools_card_list(p, s_blocks);
            s_blocks_slot = slot;
            snprintf(s_card_status, sizeof(s_card_status),
                s_blocks_n == NDIR ? "card%d: %d dir frames" : "card%d unreadable",
                slot, s_blocks_n);
        }
    }
    if (s_blocks_n == NDIR && s_blocks_slot >= 0) {
        for (int i = 0; i < NDIR; i++) {
            ImGui::Text(" [%02d] %s  %s", i,
                s_blocks[i].free ? "free" : "used", s_blocks[i].code);
        }
    }
    static bool allow_card_edits = false;
    ImGui::Checkbox("Enable direct memory-card edits", &allow_card_edits);
    ImGui::TextWrapped("Back up the card first. Inject creates an empty structural block, not a validated game save. Do not edit a card while the game is saving.");
    ImGui::BeginDisabled(!allow_card_edits || !m);
    ImGui::SetNextItemWidth(120);
    ImGui::InputText("block name", s_card_name, sizeof(s_card_name));
    ImGui::SetNextItemWidth(80);
    ImGui::InputInt("slot##c", &s_card_slot);
    if (ImGui::Button("inject block") && s_blocks_slot >= 0) {
        const char* p = m->s.memcard_path[s_blocks_slot];
        int rc = launcher_devtools_card_inject(p, s_card_slot, s_card_name);
        snprintf(s_card_status, sizeof(s_card_status),
            rc == 0 ? "injected '%s' slot %d" : "inject failed (busy slot?)",
            s_card_name, s_card_slot);
        s_blocks_n = launcher_devtools_card_list(p, s_blocks);
    }
    ImGui::SameLine();
    if (ImGui::Button("delete block") && s_blocks_slot >= 0) {
        const char* p = m->s.memcard_path[s_blocks_slot];
        int rc = launcher_devtools_card_delete(p, s_card_slot);
        snprintf(s_card_status, sizeof(s_card_status),
            rc == 0 ? "slot %d freed" : "delete failed", s_card_slot);
        s_blocks_n = launcher_devtools_card_list(p, s_blocks);
    }
    ImGui::EndDisabled();
    if (s_card_status[0]) ImGui::TextDisabled("%s", s_card_status);
    ImGui::Separator();


            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Console")) { draw_console(); ImGui::EndTabItem(); }
        ImGui::EndTabBar();
    }
    if (s_cheat_status[0]) { ImGui::Separator(); ImGui::TextWrapped("%s", s_cheat_status); }
    if (s_probe_status[0]) ImGui::TextWrapped("%s", s_probe_status);
    if (s_last_resp[0] && ImGui::TreeNodeEx("Last server response", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::BeginChild("##dev_response", ImVec2(0, ImGui::GetTextLineHeightWithSpacing() * 6), true);
        ImGui::TextWrapped("%s", s_last_resp);
        ImGui::EndChild();
        ImGui::TreePop();
    }
}
