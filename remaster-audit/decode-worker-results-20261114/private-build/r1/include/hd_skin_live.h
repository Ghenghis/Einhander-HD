/* Small strict wire contract + all-or-nothing CPU-only palette transaction. */
#ifndef PSXRECOMP_HD_SKIN_LIVE_H
#define PSXRECOMP_HD_SKIN_LIVE_H
#include "hd_skin_material.h"
#include <limits.h>
#include <stdio.h>

typedef struct {
    int set;
    char player_profile[64], enemy_profile[64];
    int player_strength_percent, enemy_strength_percent;
    char diagnostic_player_keys[HD_SKIN_DIAGNOSTIC_CSV_CAP], diagnostic_enemy_keys[HD_SKIN_DIAGNOSTIC_CSV_CAP];
    int preserve_accents;
} HdSkinLiveRequest;

/* Syntax only. The renderer separately requires every experimental identity
 * to have a registered replacement, and rejects known animated effect families.
 * A diagnostic scope is reversible and never promotes a semantic binding. */
static const char *hd_skin_diagnostic_parse(const char *text,HdSkinKey keys[HD_SKIN_MAX_DIAGNOSTIC_KEYS],int *count) {
    const char *p=text;int n=0;
    *count=0;
    if(!text || !strcmp(text,"configured"))return NULL;
    if(!*p)return "Diagnostic keys must be nonempty or configured";
    for(;;){
        uint32_t texture=0,palette=0;int i;
        if(n>=HD_SKIN_MAX_DIAGNOSTIC_KEYS)return "Diagnostic scope exceeds 128 keys per channel";
        for(i=0;i<17;++i){int digit;if(!*p)return "Malformed diagnostic key";
            if(i==8){if(*p++!='-')return "Malformed diagnostic key";continue;}
            digit=hd_skin_hex_digit(*p++);if(digit<0)return "Malformed diagnostic key";
            if(i<8)texture=(texture<<4)|(uint32_t)digit;else palette=(palette<<4)|(uint32_t)digit;
        }
        if(texture==0xE584DC41u || texture==0x1FD36785u)return "Animated effect keys are excluded from material diagnostics";
        for(i=0;i<n;++i)if(keys[i].texture==texture && keys[i].palette==palette)return "Duplicate diagnostic key";
        keys[n].texture=texture;keys[n++].palette=palette;
        if(!*p){*count=n;return NULL;}
        if(*p++!=',' || !*p)return "Malformed diagnostic key list";
    }
}

static const char *hd_skin_live_commit(HdSkinConfig *player,HdSkinConfig *enemy,int ready,
        const char *player_id,int player_percent,const char *enemy_id,int enemy_percent) {
    const HdSkinProfile *p,*e;
    if(!ready)return "OpenGL HD material renderer is not ready";
    if(!player || !enemy || !player->valid || !enemy->valid || !player->key_count || !enemy->key_count)
        return "Material key configuration is not initialized";
    if(!player_id || !enemy_id)return "Both profile IDs are required";
    p=hd_skin_find_profile(player_id); e=hd_skin_find_profile(enemy_id);
    if(!p && strcmp(player_id,"stock"))return "Unsupported player profile";
    if(!e && strcmp(enemy_id,"stock"))return "Unsupported enemy profile";
    if(player_percent<0 || player_percent>100 || enemy_percent<0 || enemy_percent>100)
        return "Both strength_percent values must be integers from 0 to 100";
    /* Validation is complete before either channel changes. The debug server
     * invokes this on the emulation thread, between draws, not its I/O thread. */
    player->profile=p; player->strength=player_percent/100.0f; player->enabled=p && player_percent>0;
    enemy->profile=e; enemy->strength=enemy_percent/100.0f; enemy->enabled=e && enemy_percent>0;
    return NULL;
}

static const char *hd_skin_live_ws(const char *p){while(*p==' '||*p=='\t'||*p=='\r'||*p=='\n')++p;return p;}
static int hd_skin_live_ident(const char **cursor,char *out,size_t capacity){
    const char *p=*cursor;size_t n=0;
    if(*p++!='"')return 0;
    while(*p && *p!='"'){
        unsigned char c=(unsigned char)*p++;
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-') || n+1>=capacity)return 0;
        out[n++]=(char)c;
    }
    if(*p++!='"' || !n)return 0;
    out[n]=0;*cursor=p;return 1;
}
static int hd_skin_live_key_text(const char **cursor,char *out,size_t capacity){
    const char *p=*cursor;size_t n=0;
    if(*p++!='"')return 0;
    while(*p && *p!='"'){
        unsigned char c=(unsigned char)*p++;
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c==',') || n+1>=capacity)return 0;
        out[n++]=(char)c;
    }
    if(*p++!='"' || !n)return 0;
    out[n]=0;*cursor=p;return 1;
}
static int hd_skin_live_integer(const char **cursor,int *out){
    const char *p=*cursor;int negative=0;unsigned long value=0;
    if(*p=='-'){negative=1;++p;}
    if(*p<'0'||*p>'9' || (*p=='0'&&p[1]>='0'&&p[1]<='9'))return 0;
    do{
        unsigned digit=(unsigned)(*p++-'0');
        if(value>((unsigned long)INT_MAX+(unsigned)negative-digit)/10u)return 0;
        value=value*10u+digit;
    }while(*p>='0'&&*p<='9');
    *out=negative?(value==(unsigned long)INT_MAX+1u?INT_MIN:-(int)value):(int)value;
    *cursor=p;return 1;
}

/* This command intentionally accepts a flat object of known fields only.
 * No duplicate/nested/escaped keys, numeric strings, fractions or partial
 * setter objects can be misread as a successful read-only request. */
static const char *hd_skin_live_parse(const char *json,HdSkinLiveRequest *out){
    const char *p;unsigned fields=0;
    if(!json || !out)return "Invalid skin_material request";
    memset(out,0,sizeof(*out));out->preserve_accents=-1;p=hd_skin_live_ws(json);
    if(*p++!='{')return "skin_material requires a JSON object";
    for(;;){
        char key[64],value[64];unsigned bit=0;int integer=0;
        p=hd_skin_live_ws(p);
        if(!hd_skin_live_ident(&p,key,sizeof key))return "Invalid or missing skin_material field";
        p=hd_skin_live_ws(p);if(*p++!=':')return "Invalid skin_material field separator";
        if(!strcmp(key,"cmd"))bit=1;
        else if(!strcmp(key,"id"))bit=2;
        else if(!strcmp(key,"player_profile"))bit=4;
        else if(!strcmp(key,"player_strength_percent"))bit=8;
        else if(!strcmp(key,"enemy_profile"))bit=16;
        else if(!strcmp(key,"enemy_strength_percent"))bit=32;
        else if(!strcmp(key,"diagnostic_player_keys"))bit=64;
        else if(!strcmp(key,"diagnostic_enemy_keys"))bit=128;
        else if(!strcmp(key,"preserve_accents"))bit=256;
        else return "Unknown skin_material field";
        if(fields&bit)return "Duplicate skin_material field";
        fields|=bit;p=hd_skin_live_ws(p);
        if(bit==64 || bit==128){
            if(!hd_skin_live_key_text(&p,bit==64?out->diagnostic_player_keys:out->diagnostic_enemy_keys,
                    sizeof out->diagnostic_player_keys))return "Diagnostic keys must be bounded exact-key CSV strings";
        }else if(bit==256){
            if(!strncmp(p,"true",4)){out->preserve_accents=1;p+=4;}
            else if(!strncmp(p,"false",5)){out->preserve_accents=0;p+=5;}
            else return "preserve_accents must be a JSON boolean";
        }else if(bit==1 || bit==4 || bit==16){
            if(!hd_skin_live_ident(&p,value,sizeof value))return "Profile IDs must be bounded JSON strings";
            if(bit==1){if(strcmp(value,"skin_material"))return "Unexpected material command";}
            else if(bit==4)snprintf(out->player_profile,sizeof out->player_profile,"%s",value);
            else snprintf(out->enemy_profile,sizeof out->enemy_profile,"%s",value);
        }else{
            if(!hd_skin_live_integer(&p,&integer))return "Strengths and id must be whole JSON integers";
            if(bit==8)out->player_strength_percent=integer;
            else if(bit==32)out->enemy_strength_percent=integer;
        }
        p=hd_skin_live_ws(p);
        if(*p=='}'){p=hd_skin_live_ws(p+1);if(*p)return "Trailing data after material command";break;}
        if(*p++!=',')return "Invalid skin_material object";
    }
    if(!(fields&1))return "Missing skin_material command";
    if((fields&60) && (fields&60)!=60)return "A live set requires both profiles and both strength_percent fields";
    out->set=(fields&508)!=0;
    return NULL;
}
#endif
