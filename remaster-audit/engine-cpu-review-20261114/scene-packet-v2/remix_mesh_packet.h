#pragma once
// CPU staging only. No SDK entry point is called by this module.
#include "pgxp.h"
#include "remix_c.h"
#include <cstdint>

namespace einhd {
enum class MeshReject {
  None, MissingSource, ImmediateWord, DataflowMiss, PacketMismatch,
  StaleFrame, Uncommitted, ProjectionDiverged, TransformUnavailable,
  MixedTransform, TransformHashMismatch, CommandMetadataInvalid, MacMismatch, InvalidUv, MaterialNotReady, Degenerate
};
struct MeshSource {
  void* context{};
  int (*lookup)(void*,uint32_t,uint32_t,PgxpView*){};
  int (*transform)(void*,uint64_t,int16_t[9],int32_t[3],uint32_t*,uint32_t*){};
};
struct MeshInput {
  uint32_t packet_address[3]{};
  uint32_t packet_word[3]{};
  // Caller must apply GP0 texture-window mask/offset, tpage/CLUT and material
  // atlas mapping before normalization. This module does not decode GP0.
  float uv[3][2]{};
  uint32_t sdk_vertex_color[3]{}; // Caller supplies SDK color, not raw PSX RGB.
  uint32_t frame{};
  // Caller must reject unsupported STP/semitransparent/raw-texture draws.
  // This prototype has no faithful PSX material/compositing path yet.
  uint64_t material_identity{};
  remixapi_MaterialHandle material{}; // Must be a real live handle at submission.
};
struct MeshPacket {
  remixapi_HardcodedVertex vertices[3]{};
  uint32_t indices[3]{};
  remixapi_MeshInfoSurfaceTriangles surface{};
  // mesh.hash is a content/resource hash, not a stable replacement/instance
  // anchor. Color/UV animation may require a different immutable resource.
  remixapi_MeshInfo mesh{};
  // The PSX combines camera and object here. This is NOT model-to-world data.
  int16_t combined_rt[9]{};
  int32_t combined_tr[3]{};
  uint16_t projection_h{};
  int32_t projection_ofx{},projection_ofy{};
  uint32_t caller_ra[3]{};
  MeshPacket()=default;
  MeshPacket(const MeshPacket&)=delete;
  MeshPacket& operator=(const MeshPacket&)=delete;
  MeshPacket(MeshPacket&&)=delete;
  MeshPacket& operator=(MeshPacket&&)=delete;
};
// Output owns all arrays referenced by mesh/surface and must remain alive.
// Use stable-address storage, not a relocating vector of MeshPacket values.
// Coordinates/normals remain in guest model space. No SDK camera handedness,
// winding conversion, camera-facing correction or mirrored-instance policy
// is implied. Quad halves must use native (0,1,2) and (2,1,3) ordering.
// Failure clears output so a previous successful packet cannot escape.
MeshReject build_mesh_packet(const MeshInput&,const MeshSource&,MeshPacket&);
const char* mesh_reject_name(MeshReject);
}
