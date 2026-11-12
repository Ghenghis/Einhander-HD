// launcher_devtools.h — DEVTOOLS panel (PSX debug-server client + memcard editor).
//
// A developer surface composed into the SETTINGS view for systems that list
// "devtools" in their panels_settings. It does not read capability from the
// game name; it talks to the engine's debug server (TCP 127.0.0.1:4370,
// one-line JSON commands) when a debug-enabled build is running, and edits
// PSX .mcd memory-card images directly on disk.
//
// Tabs: Overview, Player, Armory, Encounters, Graphics, Input, Research,
// Storage and Console. RAM writes acknowledge every byte and read back the
// result. Unknown weapon/stage/boss structures remain evidence-gated.
// Graphics presets update the normal launcher's next-launch settings.
// Persistent assists and autoplay live in tools/ein_bridge.py; the native
// panel never writes RAM automatically during UI redraws.
//
// Panel gating mirrors the rest of the registry: the console profile decides
// whether the panel is composed at all; debug-server features degrade
// gracefully to "server not running" when the game is not up.

#ifndef LAUNCHER_DEVTOOLS_H
#define LAUNCHER_DEVTOOLS_H

#include "launcher_model.h"
#include "launcher_theme.h"

#ifdef __cplusplus
extern "C" {
#endif

// Panel draw entry (registered as "devtools" in the backend's kPanelRegistry).
void launcher_devtools_draw(LauncherModel* m, const LauncherTheme* th);

// ---- debug-server TCP client (line-JSON protocol) ----
// All functions are safe to call without a running server; failures return a
// readable diagnostic. Connections and receives use short bounded timeouts.
// Implemented per-platform; Windows uses winsock2 (already linked: ws2_32).

// Send one JSON command line, return the first complete response or diagnostic.
// The returned pointer is only valid until the next devtools_send call.
const char* launcher_devtools_send(const char* json_line);

// True if the server accepted a connection on the last send.
int launcher_devtools_connected(void);

// ---- PSX memory-card (.mcd) editor ----
// 128 KiB image: sector0 "MC" header, 15 dir frames at 128B each (sector 1..15),
// data blocks of 8192B starting at sector 64. Same layout as tools/save_editor.py.

typedef struct {
    int  free;          // 1 if dir entry is free (status 0xA0)
    int  used;          // 1 if dir entry is a used block (0x51/0x52/0x53)
    char code[24];      // product code + name, e.g. "BASCUS-94243PILOT01"
} LauncherDevCardBlock;

// Read the 15 directory blocks of a card image. Returns count populated (-1 on
// unreadable/invalid card).
int launcher_devtools_card_list(const char* path, LauncherDevCardBlock* out15);

// Inject a structurally-valid named save block (dir entry + SC title frame +
// SCUS data frame) into a free dir slot. Returns 0 on success.
int launcher_devtools_card_inject(const char* path, int slot, const char* name);

// Mark a used block free (status 0xA0, checksum fixed). Returns 0 on success.
int launcher_devtools_card_delete(const char* path, int slot);

#ifdef __cplusplus
}
#endif

#endif // LAUNCHER_DEVTOOLS_H
