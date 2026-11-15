#include "remix_mesh_packet.h"
#include <cmath>
#include <cstring>
#include <limits>

namespace einhd {
static_assert(sizeof(remixapi_HardcodedVertex)==64,"Pinned official SDK layout");
static void clear(MeshPacket& o) {
  std::memset(o.vertices,0,sizeof o.vertices);std::memset(o.indices,0,sizeof o.indices);
  o.surface={};o.mesh={};std::memset(o.combined_rt,0,sizeof o.combined_rt);
  std::memset(o.combined_tr,0,sizeof o.combined_tr);std::memset(o.caller_ra,0,sizeof o.caller_ra);
  o.projection_h=0;o.projection_ofx=0;o.projection_ofy=0;
  std::memset(o.source_frame,0,sizeof o.source_frame);std::memset(o.source_lag,0,sizeof o.source_lag);
}
// Stable within this schema: explicit little-endian words, no pointer/frame/view
// transform in the resource hash. Instance identity is deliberately unresolved.
static void hash_word(uint64_t& h,uint64_t w,int bytes) {
  for(int i=0;i<bytes;++i){h^=(w>>(8*i))&255u;h*=1099511628211ull;}
}
// Exact producer schema from gte_view_xform_hash: each signed RT component
// zero-extends through uint16_t, then mixes FOUR little-endian bytes.
static uint32_t transform_hash(const int16_t rt[9],const int32_t tr[3],
                               uint16_t h,int32_t ofx,int32_t ofy) {
  uint32_t hash=2166136261u;
  auto mix=[&](uint32_t w){for(int b=0;b<4;++b){hash^=(w>>(8*b))&255u;hash*=16777619u;}};
  for(int a=0;a<9;++a)mix(uint16_t(rt[a]));
  for(int a=0;a<3;++a)mix(uint32_t(tr[a]));
  mix(h);mix(uint32_t(ofx));mix(uint32_t(ofy));return hash;
}
MeshReject build_mesh_packet(const MeshInput& in,const MeshSource& src,MeshPacket& out) {
  clear(out);
  if(!src.lookup||!src.transform)return MeshReject::MissingSource;
  if(in.max_frame_lag>1)return MeshReject::FramePolicyInvalid;
  if(!in.material||!in.material_identity)return MeshReject::MaterialNotReady;
  PgxpView view[3]{};int16_t rt[3][9]{};int32_t tr[3][3]{};uint32_t ra[3]{};
  for(int i=0;i<3;++i) {
    if(in.packet_address[i]==0xFFFFFFFFu)return MeshReject::ImmediateWord;
    for(int a=0;a<2;++a)
      if(!std::isfinite(in.uv[i][a])||in.uv[i][a]<0.f||in.uv[i][a]>1.f)return MeshReject::InvalidUv;
    if(src.lookup(src.context,in.packet_address[i],in.packet_word[i],&view[i])!=PGXP_SRC_DATAFLOW)
      return MeshReject::DataflowMiss;
    const auto& v=view[i];
    if(v.packed!=in.packet_word[i])return MeshReject::PacketMismatch;
    if(uint32_t(in.frame-v.frame)>in.max_frame_lag)return MeshReject::StaleFrame;
    if(!(v.flags&PGXP_VIEW_RTP_COMMITTED))return MeshReject::Uncommitted;
    if(!((v.cmd==0x01&&v.lane==0)||(v.cmd==0x30&&v.lane<=2)))
      return MeshReject::CommandMetadataInvalid;
    if((v.flags&(PGXP_VIEW_NATIVE_DIVERGED|PGXP_VIEW_WS_SQUASH|PGXP_VIEW_DOME))||v.h==0||v.mac[2]<=0)
      return MeshReject::ProjectionDiverged;
    uint32_t frame=0;
    if(!src.transform(src.context,v.rtp_seq,rt[i],tr[i],&frame,&ra[i]))return MeshReject::TransformUnavailable;
    if(frame!=v.frame)return MeshReject::StaleFrame;
    if(i&&(std::memcmp(rt[0],rt[i],sizeof rt[0])||std::memcmp(tr[0],tr[i],sizeof tr[0])||
           v.h!=view[0].h||v.ofx!=view[0].ofx||v.ofy!=view[0].ofy||v.xform_hash!=view[0].xform_hash))
      return MeshReject::MixedTransform;
    if(transform_hash(rt[i],tr[i],v.h,v.ofx,v.ofy)!=v.xform_hash)
      return MeshReject::TransformHashMismatch;
    for(int axis=0;axis<3;++axis) {
      int64_t mac=int64_t(tr[i][axis])*4096;
      for(int c=0;c<3;++c)mac+=int64_t(rt[i][axis*3+c])*v.v[c];
      if(mac!=v.mac[axis])return MeshReject::MacMismatch;
    }
  }
  double u[3],v[3],normal[3];
  for(int a=0;a<3;++a){u[a]=double(view[1].v[a])-view[0].v[a];v[a]=double(view[2].v[a])-view[0].v[a];}
  normal[0]=u[1]*v[2]-u[2]*v[1];normal[1]=u[2]*v[0]-u[0]*v[2];normal[2]=u[0]*v[1]-u[1]*v[0];
  const double length=std::sqrt(normal[0]*normal[0]+normal[1]*normal[1]+normal[2]*normal[2]);
  if(!(length>0)||!std::isfinite(length))return MeshReject::Degenerate;
  uint64_t hash=14695981039346656037ull;hash_word(hash,1,4);hash_word(hash,in.material_identity,8);
  for(int i=0;i<3;++i) {
    for(int a=0;a<3;++a) {
      out.vertices[i].position[a]=float(view[i].v[a]);
      out.vertices[i].normal[a]=float(normal[a]/length);
      hash_word(hash,uint16_t(view[i].v[a]),2);
    }
    for(int a=0;a<2;++a) {
      const float uv=in.uv[i][a]==0.f?0.f:in.uv[i][a]; // canonicalize -0
      out.vertices[i].texcoord[a]=uv;uint32_t bits;std::memcpy(&bits,&uv,sizeof bits);hash_word(hash,bits,4);
    }
    out.vertices[i].color=in.sdk_vertex_color[i];hash_word(hash,in.sdk_vertex_color[i],4);
    out.indices[i]=uint32_t(i);out.caller_ra[i]=ra[i];
    out.source_frame[i]=view[i].frame;out.source_lag[i]=uint8_t(uint32_t(in.frame-view[i].frame));
  }
  std::memcpy(out.combined_rt,rt[0],sizeof out.combined_rt);std::memcpy(out.combined_tr,tr[0],sizeof out.combined_tr);
  out.projection_h=view[0].h;out.projection_ofx=view[0].ofx;out.projection_ofy=view[0].ofy;
  out.surface.vertices_values=out.vertices;out.surface.vertices_count=3;
  out.surface.indices_values=out.indices;out.surface.indices_count=3;out.surface.material=in.material;
  out.mesh.sType=REMIXAPI_STRUCT_TYPE_MESH_INFO;out.mesh.hash=hash?hash:1;
  out.mesh.surfaces_values=&out.surface;out.mesh.surfaces_count=1;
  return MeshReject::None;
}
const char* mesh_reject_name(MeshReject r) {
  switch(r) {
#define REJECT(x) case MeshReject::x:return #x
    REJECT(None);REJECT(MissingSource);REJECT(ImmediateWord);REJECT(DataflowMiss);REJECT(PacketMismatch);
    REJECT(StaleFrame);REJECT(Uncommitted);REJECT(ProjectionDiverged);REJECT(TransformUnavailable);
    REJECT(MixedTransform);REJECT(TransformHashMismatch);REJECT(CommandMetadataInvalid);REJECT(FramePolicyInvalid);REJECT(MacMismatch);REJECT(InvalidUv);REJECT(MaterialNotReady);REJECT(Degenerate);
#undef REJECT
  }return "Unknown";
}
}
