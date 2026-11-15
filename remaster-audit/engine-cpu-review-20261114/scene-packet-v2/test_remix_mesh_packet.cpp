// Deliberate host fixtures. This is not a game capture or live material handle.
#include "remix_mesh_packet.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <initializer_list>
#include <type_traits>
using namespace einhd;
struct Fixture {
  PgxpView views[3]{};
  int16_t rt[9]={4096,0,0,0,4096,0,0,0,4096};
  int32_t tr[3]={0,0,100};
  int missing=-1,dead=-1,mixed=-1;
  bool shared_seq=false;
  MeshInput input;
  void refresh() {
    for(int i=0;i<3;++i)for(int a=0;a<3;++a){views[i].mac[a]=int64_t(tr[a])*4096;for(int c=0;c<3;++c)views[i].mac[a]+=int64_t(rt[a*3+c])*views[i].v[c];}
    // Independent fixture encoding of the GTE producer's recorded schema.
    uint32_t hash=2166136261u;
    uint32_t words[15]{};for(int a=0;a<9;++a)words[a]=uint16_t(rt[a]);
    for(int a=0;a<3;++a)words[9+a]=uint32_t(tr[a]);
    words[12]=views[0].h;words[13]=uint32_t(views[0].ofx);words[14]=uint32_t(views[0].ofy);
    for(uint32_t word:words)for(unsigned shift=0;shift<32;shift+=8){hash^=(word>>shift)&255u;hash*=16777619u;}
    for(auto& view:views)view.xform_hash=hash;
  }
  Fixture() {
    input.frame=42;input.material_identity=0x1122334455667788ull;
    input.material=reinterpret_cast<remixapi_MaterialHandle>(uintptr_t(0x100));
    const int16_t points[3][3]={{0,0,0},{20,0,0},{0,20,0}};
    for(int i=0;i<3;++i){
      input.packet_address[i]=0x1000+uint32_t(i)*4;input.packet_word[i]=0x12340000+uint32_t(i);
      input.sdk_vertex_color[i]=0xFF808080u;input.uv[i][0]=i==1?1.f:0.f;input.uv[i][1]=i==2?1.f:0.f;
      views[i].packed=input.packet_word[i];views[i].frame=42;views[i].rtp_seq=i+1;
      views[i].flags=PGXP_VIEW_SF|PGXP_VIEW_RTP_COMMITTED;views[i].h=256;views[i].xform_hash=123;views[i].cmd=0x01;
      std::memcpy(views[i].v,points[i],sizeof points[i]);
    }refresh();
  }
  static int lookup(void* c,uint32_t a,uint32_t w,PgxpView* out) {
    auto& f=*static_cast<Fixture*>(c);int i=int((a-0x1000)/4);
    if(i<0||i>2||f.missing==i||w!=f.input.packet_word[i])return PGXP_SRC_NATIVE;
    *out=f.views[i];return PGXP_SRC_DATAFLOW;
  }
  static int transform(void* c,uint64_t seq,int16_t rt[9],int32_t tr[3],uint32_t* frame,uint32_t* ra) {
    auto& f=*static_cast<Fixture*>(c);int i=f.shared_seq?0:int(seq)-1;if(i<0||i>2||f.dead==i)return 0;
    std::memcpy(rt,f.rt,sizeof f.rt);std::memcpy(tr,f.tr,sizeof f.tr);if(f.mixed==i)rt[0]++;
    *frame=f.views[i].frame;*ra=0x80001000+uint32_t(i)*4;return 1;
  }
  MeshSource source(){return {this,lookup,transform};}
};
static int checks=0,failed=0;
#define CHECK(x) do{++checks;if(!(x)){std::fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);++failed;}}while(0)
int main() {
  static_assert(!std::is_copy_constructible<MeshPacket>::value,"No dangling pointer copies");
  MeshPacket out;
  {Fixture f;CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None);
   CHECK(out.mesh.surfaces_values==&out.surface&&out.surface.vertices_values==out.vertices);
   CHECK(out.mesh.sType==REMIXAPI_STRUCT_TYPE_MESH_INFO&&out.surface.indices_count==3);
   CHECK(out.vertices[1].position[0]==20&&out.vertices[1].position[2]==0);
   CHECK(out.combined_tr[2]==100&&out.projection_h==256);
   CHECK(out.vertices[0].normal[2]==1&&out.vertices[0].color==f.input.sdk_vertex_color[0]);
   auto hash=out.mesh.hash;f.tr[0]=37;f.refresh();CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None);
   CHECK(out.mesh.hash==hash&&out.combined_tr[0]==37); // Model resource stable; combined view transform distinct.
   f.input.material_identity++;CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None&&out.mesh.hash!=hash);
  }
  auto reject=[&](Fixture& f,MeshReject expected){
    CHECK(build_mesh_packet(f.input,f.source(),out)==expected);
    CHECK(out.mesh.surfaces_count==0&&out.surface.vertices_values==nullptr);};
  {Fixture f;f.missing=1;reject(f,MeshReject::DataflowMiss);}
  {Fixture f;f.input.packet_address[0]=0xFFFFFFFFu;reject(f,MeshReject::ImmediateWord);}
  {Fixture f;f.views[1].packed++;reject(f,MeshReject::PacketMismatch);}
  {Fixture f;f.views[1].frame--;reject(f,MeshReject::StaleFrame);}
  {Fixture f;f.views[1].flags&=~PGXP_VIEW_RTP_COMMITTED;reject(f,MeshReject::Uncommitted);}
  for(uint16_t flag: {uint16_t(PGXP_VIEW_IR_SAT),uint16_t(PGXP_VIEW_MAC1_OVF44),uint16_t(PGXP_VIEW_MAC3_WRAP32),uint16_t(PGXP_VIEW_WS_SQUASH),uint16_t(PGXP_VIEW_DOME)})
    {Fixture f;f.views[1].flags|=flag;reject(f,MeshReject::ProjectionDiverged);}
  {Fixture f;f.dead=1;reject(f,MeshReject::TransformUnavailable);}
  {Fixture f;f.mixed=1;reject(f,MeshReject::MixedTransform);}
  {Fixture f;f.views[1].h++;reject(f,MeshReject::MixedTransform);}
  {Fixture f;f.views[1].mac[0]++;reject(f,MeshReject::MacMismatch);}
  {Fixture f;f.input.uv[0][0]=std::numeric_limits<float>::quiet_NaN();reject(f,MeshReject::InvalidUv);}
  {Fixture f;f.input.uv[0][0]=1.01f;reject(f,MeshReject::InvalidUv);}
  {Fixture f;f.input.material=nullptr;reject(f,MeshReject::MaterialNotReady);}
  {Fixture f;std::memcpy(f.views[2].v,f.views[1].v,sizeof f.views[2].v);f.refresh();reject(f,MeshReject::Degenerate);}
  {Fixture f;MeshSource missing;CHECK(build_mesh_packet(f.input,missing,out)==MeshReject::MissingSource);}
  {Fixture f;f.input.uv[0][0]=-0.f;CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None);uint64_t hash=out.mesh.hash;
   f.input.uv[0][0]=0.f;CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None&&hash==out.mesh.hash);}
  // RT corruption can hide behind V=(0,0,0), where MAC recomputation alone
  // cannot constrain any rotation component. The producer hash must catch it.
  {Fixture f;f.mixed=0;reject(f,MeshReject::TransformHashMismatch);}
  {Fixture f;f.views[0].xform_hash^=1;reject(f,MeshReject::TransformHashMismatch);}
  {Fixture f;f.views[0].ofx=1;reject(f,MeshReject::TransformHashMismatch);}
  {Fixture f;f.rt[1]=-1024;f.tr[0]=-17;f.views[0].ofx=-32768;f.views[0].ofy=65536;
   for(int i=1;i<3;++i){f.views[i].ofx=f.views[0].ofx;f.views[i].ofy=f.views[0].ofy;}f.refresh();
   CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None);}
  {Fixture f;f.shared_seq=true;for(int i=0;i<3;++i){f.views[i].rtp_seq=1;f.views[i].cmd=0x30;f.views[i].lane=uint8_t(i);}
   CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None);
   CHECK(out.vertices[1].position[0]==20&&out.vertices[2].position[1]==20);}
  {Fixture f;f.views[1].cmd=0x30;f.views[1].lane=3;reject(f,MeshReject::CommandMetadataInvalid);}
  {Fixture f;f.views[1].lane=1;reject(f,MeshReject::CommandMetadataInvalid);}
  {Fixture f;f.views[1].cmd=0xFF;reject(f,MeshReject::CommandMetadataInvalid);}
  {Fixture f;CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None);uint64_t hash=out.mesh.hash;
   f.input.sdk_vertex_color[1]^=1;CHECK(build_mesh_packet(f.input,f.source(),out)==MeshReject::None&&out.mesh.hash!=hash);}
  // Native quad split: first (0,1,2), second (2,1,3); both keep the model
  // winding and shared edge endpoints. A later batch layer must deduplicate.
  {Fixture first,second;MeshPacket a,b;
   const int16_t points[3][3]={{0,20,0},{20,0,0},{20,20,0}};
   const float uv[3][2]={{0,1},{1,0},{1,1}};
   for(int i=0;i<3;++i){std::memcpy(second.views[i].v,points[i],sizeof points[i]);std::memcpy(second.input.uv[i],uv[i],sizeof uv[i]);}
   second.refresh();CHECK(build_mesh_packet(first.input,first.source(),a)==MeshReject::None);
   CHECK(build_mesh_packet(second.input,second.source(),b)==MeshReject::None);
   CHECK(std::memcmp(&a.vertices[2].position,&b.vertices[0].position,sizeof a.vertices[2].position)==0);
   CHECK(std::memcmp(&a.vertices[1].position,&b.vertices[1].position,sizeof a.vertices[1].position)==0);
   CHECK(a.vertices[0].normal[2]==1&&b.vertices[0].normal[2]==1);
   CHECK(b.vertices[2].texcoord[0]==1&&b.vertices[2].texcoord[1]==1);}
  std::printf("checks %d failures %d\n",checks,failed);return failed?1:0;
}
