#ifndef EIN_HD_DECODE_QUEUE_H
#define EIN_HD_DECODE_QUEUE_H
#include <cstddef>
#include <cstdint>
#include <deque>

/* One worker, the original32 pending-job bound, and no cancellations.
 * Until a priority request occurs this is the original FIFO policy. Then
 * four slots are reserved for short-lived uploads; at most four urgent jobs
 * may overtake the oldest normal job. Loading jobs are never interrupted. */
class HdDecodeQueue {
    std::deque<uint64_t> normal_,urgent_;
    unsigned urgent_burst_=0;
    bool priority_mode_=false;
public:
    static constexpr std::size_t capacity=32,reserved=4;
    void enable_priority(){priority_mode_=true;}
    std::size_t size()const{return normal_.size()+urgent_.size();}
    bool empty()const{return normal_.empty()&&urgent_.empty();}
    bool can_push(bool urgent)const{return size()<(priority_mode_&&!urgent?capacity-reserved:capacity);}
    bool push(uint64_t key,bool urgent){
        if(urgent)enable_priority();
        if(!can_push(urgent))return false;
        (urgent?urgent_:normal_).push_back(key);return true;
    }
    bool take(uint64_t *key){
        if(!key||empty())return false;
        if(!urgent_.empty()&&(normal_.empty()||urgent_burst_<reserved)){
            *key=urgent_.front();urgent_.pop_front();if(urgent_burst_<reserved)++urgent_burst_;
        }else{
            *key=normal_.front();normal_.pop_front();urgent_burst_=0;
        }
        return true;
    }
};
#endif
