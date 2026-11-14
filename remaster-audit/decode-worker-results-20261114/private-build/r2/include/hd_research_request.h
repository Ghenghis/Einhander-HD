#ifndef PSXRECOMP_HD_RESEARCH_REQUEST_H
#define PSXRECOMP_HD_RESEARCH_REQUEST_H
#include "gpu_gl_renderer.h"
#include "hd_skin_live.h"
#include "hd_research_event.h"
typedef struct {char op[16],path[1024],label[64];GlResearchLimits limits;} HdResearchRequest;
static int hdr_source_keys_parse(const char **cursor,GlResearchLimits *limits){
 const char *p=hd_skin_live_ws(*cursor);unsigned i,j;if(*p++!='[')return 0;p=hd_skin_live_ws(p);
 if(*p==']'){*cursor=p+1;return 1;}
 for(;;){char key[32];uint32_t words[2]={0,0};p=hd_skin_live_ws(p);
  if(limits->source_key_count>=GL_RESEARCH_SOURCE_KEYS_MAX||!hd_skin_live_ident(&p,key,sizeof key)||strlen(key)!=17||key[8]!='-')return 0;
  for(i=0;i<17;++i){unsigned char c=(unsigned char)key[i];unsigned digit;if(i==8)continue;if(c>='0'&&c<='9')digit=c-'0';else if(c>='A'&&c<='F')digit=c-'A'+10;else return 0;j=i>8;words[j]=(words[j]<<4)|digit;}
  for(i=0;i<limits->source_key_count;++i)if(limits->source_keys[i].texture==words[0]&&limits->source_keys[i].palette==words[1])return 0;
  limits->source_keys[limits->source_key_count].texture=words[0];limits->source_keys[limits->source_key_count++].palette=words[1];
  p=hd_skin_live_ws(p);if(*p==']'){*cursor=p+1;return 1;}if(*p++!=',')return 0;
 }
}
/* Paths accept ordinary JSON slash/backslash/quote escapes only. Embedded
 * control characters, Unicode escapes and overlong strings fail closed. */
static int hdr_path_string(const char **cursor,char *out,size_t cap){
 const char *p=*cursor;size_t n=0;if(*p++!='"')return 0;
 while(*p&&*p!='"'){unsigned char c=(unsigned char)*p++;if(c=='\\'){c=(unsigned char)*p++;if(c!='\\'&&c!='/'&&c!='"')return 0;}if(c<32||c>126||n+1>=cap)return 0;out[n++]=(char)c;}
 if(*p++!='"'||!n)return 0;out[n]=0;*cursor=p;return 1;
}
static const char *hdr_parse_request(const char *json,HdResearchRequest *r){
 const char *p;unsigned fields=0;if(!json||!r)return "Invalid research_capture request";
 memset(r,0,sizeof(*r));strcpy(r->op,"status");r->limits.max_sources=64;r->limits.max_records=5000;r->limits.max_events=8;r->limits.max_frames=3600;r->limits.max_seconds=60;r->limits.max_bytes=33554432;
 p=hd_skin_live_ws(json);if(*p++!='{')return "research_capture requires a JSON object";
 for(;;){char key[64],value[64];unsigned bit=0;int integer=0;p=hd_skin_live_ws(p);if(!hd_skin_live_ident(&p,key,sizeof key))return "Invalid research_capture field";
 p=hd_skin_live_ws(p);if(*p++!=':')return "Invalid research_capture separator";
 if(!strcmp(key,"cmd"))bit=1;else if(!strcmp(key,"id"))bit=2;else if(!strcmp(key,"op"))bit=4;else if(!strcmp(key,"path"))bit=8;else if(!strcmp(key,"label"))bit=16;
 else if(!strcmp(key,"max_sources"))bit=32;else if(!strcmp(key,"max_records"))bit=64;else if(!strcmp(key,"max_events"))bit=128;else if(!strcmp(key,"max_frames"))bit=256;else if(!strcmp(key,"max_seconds"))bit=512;else if(!strcmp(key,"max_bytes"))bit=1024;else if(!strcmp(key,"source_policy"))bit=2048;else if(!strcmp(key,"source_keys"))bit=4096;else return "Unknown research_capture field";
 if(fields&bit)return "Duplicate research_capture field";fields|=bit;p=hd_skin_live_ws(p);
 if(bit==8){if(!hdr_path_string(&p,r->path,sizeof r->path))return "Invalid bounded ASCII capture path";}
 else if(bit==4096){if(!hdr_source_keys_parse(&p,&r->limits))return "Source keys must be at most256 unique uppercase CRC pairs";}
 else if(bit==1||bit==4||bit==16||bit==2048){if(!hd_skin_live_ident(&p,value,sizeof value))return "Invalid research_capture identifier";if(bit==1){if(strcmp(value,"research_capture"))return "Unexpected research command";}else if(bit==4){if(strlen(value)>=sizeof r->op)return "Invalid research operation";strcpy(r->op,value);}else if(bit==2048){if(!strcmp(value,"all"))r->limits.source_policy=GL_RESEARCH_SOURCE_ALL;else if(!strcmp(value,"include"))r->limits.source_policy=GL_RESEARCH_SOURCE_INCLUDE;else if(!strcmp(value,"exclude"))r->limits.source_policy=GL_RESEARCH_SOURCE_EXCLUDE;else return "Unknown source filter policy";}else strcpy(r->label,value);}
 else{if(!hd_skin_live_integer(&p,&integer))return "Capture limits must be whole JSON integers";if(bit!=2&&integer<1)return "Capture limits must be positive";
 if(bit==32)r->limits.max_sources=(unsigned)integer;else if(bit==64)r->limits.max_records=(unsigned)integer;else if(bit==128)r->limits.max_events=(unsigned)integer;else if(bit==256)r->limits.max_frames=(unsigned)integer;else if(bit==512)r->limits.max_seconds=(unsigned)integer;else if(bit==1024)r->limits.max_bytes=(uint64_t)integer;}
 p=hd_skin_live_ws(p);if(*p=='}'){p=hd_skin_live_ws(p+1);if(*p)return "Trailing research command data";break;}if(*p++!=',')return "Invalid research_capture object";}
 if(!(fields&1))return "Missing research_capture command";
 if(!strcmp(r->op,"start")){if(!(fields&8)||fields&16)return "Start requires path and accepts only capture limits";}
 else if(!strcmp(r->op,"mark")){if(!(fields&16)||fields&(8|2016|6144))return "Mark requires only a label";}
 else if(!strcmp(r->op,"status")||!strcmp(r->op,"stop")){if(fields&(8|16|2016|6144))return "Status and stop accept no capture parameters";}
 else return "Unsupported research_capture operation";
 if(r->limits.max_sources>256||r->limits.max_records>20000||r->limits.max_events>32||r->limits.max_frames>18000||r->limits.max_seconds>300||r->limits.max_bytes>134217728)return "Capture limits exceed native hard bounds";
 if((r->limits.source_policy==GL_RESEARCH_SOURCE_ALL)!=(r->limits.source_key_count==0))return "Include/exclude requires nonempty keys; all accepts none";
 return NULL;
}
static int hdr_json_escape(const char *s,char *out,size_t cap){size_t n=0;while(*s){unsigned char c=(unsigned char)*s++;if(c<32)return 0;if(c=='"'||c=='\\'){if(n+2>=cap)return 0;out[n++]='\\';}else if(n+1>=cap)return 0;out[n++]=(char)c;}out[n]=0;return 1;}
#endif
