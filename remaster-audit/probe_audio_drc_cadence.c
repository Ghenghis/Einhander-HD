/* Controlled audio-clock experiment, not recorded game audio or audible QA.
 * Compile with the project's C compiler and -O2. Runs the actual bridge with
 * a sine producer and 256-frame/48kHz callbacks. No GPU, files or game process.
 */
#define RECOMP_AUDIO_DRC_IMPL
#include "../windows-x64/psxrecomp/runtime/src/recomp_audio_drc.h"
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
static double selected_correction=.005;

static int scenario(const char *name,double producer_rate,int stall) {
    rab_config c;rab_config_defaults(&c);c.channels=2;c.source_rate=44100;c.host_rate=48000;
    c.max_correction=selected_correction;
    rab_bridge b;if(rab_init(&b,&c))return 1;
    int16_t input[8192*2],output[256*2];double produced=0;uint64_t source=0;
    double min_fill=1e20,max_fill=0,min_corr=1e20,max_corr=-1e20,max_slew=0,previous_corr=0;
    const int blocks=120*48000/256;
    for(int n=0;n<blocks;n++) {
        double t=n*256./48000.;
        double rate=producer_rate;
        /* One isolated 300ms producer stall after priming; never catch up. */
        if(stall&&t>=60&&t<60.3)rate=0;
        produced+=rate*256./48000.;
        int frames=(int)floor(produced)-(int)source;
        if(frames<0||frames>8192){rab_free(&b);return 2;}
        for(int i=0;i<frames;i++) {
            int16_t sample=(int16_t)(10000*sin(2*3.141592653589793*440*(source+i)/44100.));
            input[2*i]=input[2*i+1]=sample;
        }
        rab_push(&b,input,frames);source+=frames;rab_pull(&b,output,256);
        double fill=rab_fill_ms(&b);
        if(b.primed&&fill<min_fill)min_fill=fill;if(fill>max_fill)max_fill=fill;
        if(b.corr<min_corr)min_corr=b.corr;if(b.corr>max_corr)max_corr=b.corr;
        if(fabs(b.corr-previous_corr)>max_slew)max_slew=fabs(b.corr-previous_corr);previous_corr=b.corr;
    }
    rab_stats s;rab_get_stats(&b,&s);
    printf("{\"case\":\"%s\",\"seconds\":120,\"producer_hz\":%.3f,\"max_correction\":%.6f,\"starved_output_frames\":%llu,\"overflow_source_frames\":%llu,\"final_fill_ms\":%.3f,\"correction\":%.6f,\"primed_fill_min_ms\":%.3f,\"fill_max_ms\":%.3f,\"correction_min\":%.6f,\"correction_max\":%.6f,\"max_correction_step\":%.8f,\"controlled_synthetic_input\":true}\n",
        name,producer_rate,c.max_correction,(unsigned long long)s.underrun_events,(unsigned long long)s.overflow_drops,
        rab_fill_ms(&b),s.last_correction,min_fill,max_fill,min_corr,max_corr,max_slew);
    int within=producer_rate>=44100*(1-c.max_correction);
    int failed=(within&&!stall&&s.underrun_events!=0) || ((!within||stall)&&s.underrun_events==0) ||
        max_slew>c.slew_pp_per_s/100.*256/48000.+1e-12 || fabs(min_corr)>c.max_correction+1e-12 || fabs(max_corr)>c.max_correction+1e-12;
    rab_free(&b);return failed;
}

int main(int argc,char **argv) {
    if(argc==2)selected_correction=strtod(argv[1],NULL);
    if(argc>2||(selected_correction!=.005&&selected_correction!=.01))return 2;
    int failed=0;
    failed+=scenario("nominal",44100,0);
    failed+=scenario("steady59.9238guestfps",735*59.9238,0);
    failed+=scenario("steady59.4342guestfps",735*59.4342,0);
    failed+=scenario("nominal_with300ms_gap",44100,1);
    return failed?1:0;
}
