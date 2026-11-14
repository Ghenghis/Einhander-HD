/* Bounded, CPU-only research evidence sink. Call from one owning thread.
 * No guest RAM access, input injection, GL calls or background work.
 * Caller initializes HdResearchCapture to zero before first use. */
#ifndef PSXRECOMP_HD_RESEARCH_CAPTURE_H
#define PSXRECOMP_HD_RESEARCH_CAPTURE_H
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <sys/stat.h>
#include <fcntl.h>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#include <direct.h>
#else
#include <unistd.h>
#include <limits.h>
#endif

#define HDRC_MAX_FILES 1024u
#define HDRC_MAX_JSON_LINE 65536u
#define HDRC_MIB (UINT64_C(1024)*UINT64_C(1024))

typedef struct {
    unsigned max_sources,max_records,max_events,max_frames,max_seconds;
    uint64_t max_bytes;
} HdResearchLimits;
typedef struct {
    int active;
    char directory[1024],stop_reason[64];
    FILE *receipt_file;
    HdResearchLimits limits;
    uint64_t start_frame,start_ms,bytes_written;
    uint64_t last_frame,last_ms;
    unsigned sources,records,events,files;
} HdResearchCapture;

static HdResearchLimits hdrc_default_limits(void) {
    HdResearchLimits out={64u,5000u,8u,3600u,60u,32u*HDRC_MIB};return out;
}
static int hdrc_limits_valid(const HdResearchLimits *p) {
    return p && p->max_sources && p->max_sources<=256u &&
        p->max_records && p->max_records<=20000u && p->max_events && p->max_events<=32u &&
        p->max_frames && p->max_frames<=18000u && p->max_seconds && p->max_seconds<=300u &&
        p->max_bytes && p->max_bytes<=128u*HDRC_MIB;
}
static void hdrc_error(char *out,int capacity,const char *message) {
    if(out && capacity>0)snprintf(out,(size_t)capacity,"%s",message);
}
static void hdrc_stop(HdResearchCapture *s,const char *reason) {
    int failed=0;
    if(!s)return;
    if(!s->active && !s->receipt_file && s->stop_reason[0])return;
    if(s->receipt_file){
        failed=fflush(s->receipt_file)!=0;
        if(fclose(s->receipt_file)!=0)failed=1;
        s->receipt_file=NULL;
    }
    s->active=0;
    snprintf(s->stop_reason,sizeof s->stop_reason,"%s",failed?"receipt_flush_error":reason&&reason[0]?reason:"stopped");
}
static int hdrc_fail(HdResearchCapture *s,const char *reason) {hdrc_stop(s,reason);return 0;}

/* All paths must already be absolute existing directories. Dot components,
 * control characters and device/UNC paths are rejected; no directory creation.
 * Backend owns its higher-level workspace scoping/canonical session directory. */
static int hdrc_directory(const char *path,char out[1024]) {
    size_t i,n,start;
    if(!path || !(n=strlen(path)) || n>=960u)return 0;
    for(i=0;i<n;++i)if((unsigned char)path[i]<32u || (unsigned char)path[i]==127u)return 0;
#ifdef _WIN32
    if(n<3 || !isalpha((unsigned char)path[0]) || path[1]!=':' || (path[2]!='/' && path[2]!='\\'))return 0;
    for(i=2;i<n;++i)if(path[i]==':' || path[i]=='"' || path[i]=='<' || path[i]=='>' || path[i]=='|' || path[i]=='?' || path[i]=='*')return 0;
#else
    if(path[0]!='/')return 0;
#endif
    start=0;
    for(i=0;i<=n;++i){
        if(i==n || path[i]=='/' || path[i]=='\\'){
            size_t length=i-start;
            if((length==1 && path[start]=='.') || (length==2 && path[start]=='.' && path[start+1]=='.'))return 0;
#ifdef _WIN32
            if(length && (path[i-1]=='.' || path[i-1]==' '))return 0; /* Win32 path aliases */
#endif
            start=i+1;
        }
    }
#ifdef _WIN32
    {
        struct _stat info;
        if(!_fullpath(out,path,1024) || _stat(out,&info)!=0 || !(info.st_mode&_S_IFDIR))return 0;
    }
#else
    {
        char resolved[PATH_MAX];struct stat info;
        if(!realpath(path,resolved) || strlen(resolved)>=960u || stat(resolved,&info)!=0 || !S_ISDIR(info.st_mode))return 0;
        snprintf(out,1024,"%s",resolved);
    }
#endif
    n=strlen(out);
    if(n>=960u)return 0;
    while(n>3 && (out[n-1]=='/' || out[n-1]=='\\'))out[--n]=0;
    return 1;
}
static int hdrc_safe_leaf(const char *leaf) {
    size_t i,n,base=0;char stem[16];
    if(!leaf || !(n=strlen(leaf)) || n>160u || !isalnum((unsigned char)leaf[0]) || leaf[n-1]=='.' || strstr(leaf,".."))return 0;
    for(i=0;i<n;++i){
        unsigned char c=(unsigned char)leaf[i];
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))return 0;
        if(!base && c=='.')base=i;
    }
    if(!base)base=n;
    if(base<sizeof stem){
        for(i=0;i<base;++i)stem[i]=(char)toupper((unsigned char)leaf[i]);stem[base]=0;
        if(!strcmp(stem,"CON")||!strcmp(stem,"PRN")||!strcmp(stem,"AUX")||!strcmp(stem,"NUL")||
           (base==4 && (!memcmp(stem,"COM",3)||!memcmp(stem,"LPT",3)) && stem[3]>='1'&&stem[3]<='9'))return 0;
    }
    return 1;
}
static int hdrc_path(const HdResearchCapture *s,const char *leaf,int part,char out[1200]) {
    int count=snprintf(out,1200,"%s/%s%s",s->directory,leaf,part?".part":"");
    return count>0 && count<1200;
}
static FILE *hdrc_open_exclusive(const char *path) {
    int descriptor;FILE *file;
#ifdef _WIN32
    descriptor=_open(path,_O_WRONLY|_O_CREAT|_O_EXCL|_O_BINARY,_S_IREAD|_S_IWRITE);
    if(descriptor<0)return NULL;
    file=_fdopen(descriptor,"wb");if(!file){_close(descriptor);_unlink(path);}
#else
    descriptor=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);
    if(descriptor<0)return NULL;
    file=fdopen(descriptor,"wb");if(!file){close(descriptor);unlink(path);}
#endif
    return file;
}
static void hdrc_remove_owned_part(const char *path) {
#ifdef _WIN32
    _unlink(path);
#else
    unlink(path);
#endif
}
static int hdrc_promote_no_replace(const char *part,const char *final) {
#ifdef _WIN32
    return MoveFileExA(part,final,MOVEFILE_WRITE_THROUGH)!=0;
#else
    /* Atomic no-replace visibility on POSIX: hard-link the fully closed part,
     * then remove only our private temporary name. Existing final is untouched. */
    if(link(part,final)!=0)return 0;
    if(unlink(part)!=0)return 0;
    return 1;
#endif
}
static int hdrc_start(HdResearchCapture *s,const char *directory,const HdResearchLimits *limits,
        uint64_t frame,uint64_t now_ms,char *error,int error_capacity) {
    HdResearchLimits chosen=limits?*limits:hdrc_default_limits();
    HdResearchCapture next;char path[1200];FILE *file;
    if(!s){hdrc_error(error,error_capacity,"Missing recorder state");return 0;}
    if(s->active || s->receipt_file){hdrc_error(error,error_capacity,"Recorder is already active");return 0;}
    if(!hdrc_limits_valid(&chosen)){hdrc_error(error,error_capacity,"Invalid recorder limits");return 0;}
    memset(&next,0,sizeof next);
    if(!hdrc_directory(directory,next.directory)){hdrc_error(error,error_capacity,"Recorder requires an existing absolute directory without traversal");return 0;}
    if(!hdrc_path(&next,"capture.jsonl",0,path) || !(file=hdrc_open_exclusive(path))){
        hdrc_error(error,error_capacity,"Cannot exclusively create capture.jsonl");return 0;
    }
    next.active=1;next.receipt_file=file;next.limits=chosen;next.start_frame=frame;next.start_ms=now_ms;next.files=1;
    next.last_frame=frame;next.last_ms=now_ms;
    *s=next;hdrc_error(error,error_capacity,"");return 1;
}
/* Status never extends a lease. Counts are soft per-operation caps; elapsed
 * time, frames, storage and IO errors stop the whole capture. */
static int hdrc_tick(HdResearchCapture *s,uint64_t frame,uint64_t now_ms) {
    if(!s || !s->active)return 0;
    if(frame<s->last_frame)return hdrc_fail(s,"frame_reset");
    if(now_ms<s->last_ms)return hdrc_fail(s,"clock_rollback");
    if(frame-s->start_frame>=s->limits.max_frames)return hdrc_fail(s,"frame_limit");
    if(now_ms-s->start_ms>=(uint64_t)s->limits.max_seconds*1000u)return hdrc_fail(s,"time_limit");
    if(s->bytes_written>=s->limits.max_bytes)return hdrc_fail(s,"byte_limit");
    if(s->files>=HDRC_MAX_FILES)return hdrc_fail(s,"file_limit");
    s->last_frame=frame;s->last_ms=now_ms;
    return 1;
}
static int hdrc_reserve(HdResearchCapture *s,uint64_t bytes,unsigned files) {
    if(bytes>s->limits.max_bytes-s->bytes_written)return hdrc_fail(s,"byte_limit");
    if(files>HDRC_MAX_FILES-s->files)return hdrc_fail(s,"file_limit");
    return 1;
}
static int hdrc_json(HdResearchCapture *s,const char *jsonline,uint64_t frame,uint64_t now_ms) {
    size_t n=0,i;
    if(!hdrc_tick(s,frame,now_ms))return 0;
    if(s->records>=s->limits.max_records)return 0;
    if(!jsonline)return hdrc_fail(s,"invalid_json_line");
    while(n<=HDRC_MAX_JSON_LINE && jsonline[n])++n;
    if(!n || n>HDRC_MAX_JSON_LINE)return hdrc_fail(s,"json_line_limit");
    if(jsonline[n-1]=='\n')--n;
    if(n && jsonline[n-1]=='\r')--n;
    if(!n)return hdrc_fail(s,"invalid_json_line");
    for(i=0;i<n;++i)if((unsigned char)jsonline[i]<32u && jsonline[i]!='\t')return hdrc_fail(s,"invalid_json_line");
    if(!hdrc_reserve(s,(uint64_t)n+1u,0))return 0;
    if(!s->receipt_file || fwrite(jsonline,1,n,s->receipt_file)!=n || fputc('\n',s->receipt_file)==EOF || fflush(s->receipt_file)!=0)
        return hdrc_fail(s,"receipt_write_error");
    s->bytes_written+=(uint64_t)n+1u;++s->records;return 1;
}
static int hdrc_blob(HdResearchCapture *s,const char *safe_leaf,const void *data,size_t length,
        uint64_t frame,uint64_t now_ms) {
    char part[1200],final[1200];FILE *file;int failed;
    if(!hdrc_tick(s,frame,now_ms))return 0;
    if(!hdrc_safe_leaf(safe_leaf) || (!data && length))return hdrc_fail(s,"invalid_blob_path_or_data");
    if(!hdrc_path(s,safe_leaf,1,part) || !hdrc_path(s,safe_leaf,0,final))return hdrc_fail(s,"blob_path_limit");
    if(!hdrc_reserve(s,(uint64_t)length,1))return 0;
    if(!(file=hdrc_open_exclusive(part)))return hdrc_fail(s,"blob_create_error");
    failed=length && fwrite(data,1,length,file)!=length;
    if(fflush(file)!=0)failed=1;
    if(fclose(file)!=0)failed=1;
    if(failed){hdrc_remove_owned_part(part);return hdrc_fail(s,"blob_write_error");}
    if(!hdrc_promote_no_replace(part,final)){hdrc_remove_owned_part(part);return hdrc_fail(s,"blob_commit_error");}
    s->bytes_written+=(uint64_t)length;++s->files;return 1;
}
static int hdrc_claim_source(HdResearchCapture *s,uint64_t frame,uint64_t now_ms) {
    if(!hdrc_tick(s,frame,now_ms) || s->sources>=s->limits.max_sources)return 0;
    ++s->sources;return 1;
}
static int hdrc_claim_event(HdResearchCapture *s,uint64_t frame,uint64_t now_ms) {
    if(!hdrc_tick(s,frame,now_ms) || s->events>=s->limits.max_events)return 0;
    ++s->events;return 1;
}
#endif
