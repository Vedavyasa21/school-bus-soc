#include <string.h>
#include "priority_scheduler.h"
#include "sensor_input.h"

/* Indexed by ZoneLevel: SAFE, WARNING, CRITICAL */
static const uint32_t SERVICE_MS[3]  = { 3u, 6u, 9u };
static const uint32_t DEADLINE_MS[3] = { 300u, 100u, 40u };

void scheduler_build_event(SchedEvent *ev, uint32_t id, uint32_t arrival_ms,
                           ZoneLevel zone, uint8_t risk, uint8_t confidence,
                           uint16_t distance_cm, SourceTask source)
{
    ev->event_id       = id;
    ev->arrival_ms     = arrival_ms;
    ev->start_ms       = 0;
    ev->finish_ms      = 0;
    ev->service_ms     = SERVICE_MS[(int)zone];
    ev->deadline_ms    = DEADLINE_MS[(int)zone];
    ev->zone           = zone;
    ev->risk           = risk;
    ev->confidence     = confidence;
    ev->distance_cm    = distance_cm;
    ev->source         = source;
    ev->fixed_priority = (uint8_t)source;
}

SourceTask scheduler_source_from_scores(uint8_t us, uint8_t prox, uint8_t motion)
{
    if (us < 20 && prox < 20 && motion < 20) {
        return SRC_ROUTINE;
    }
    if (prox >= us && prox >= motion) {
        return SRC_PROXIMITY;
    }
    if (us >= motion) {
        return SRC_ULTRASONIC;
    }
    return SRC_MOTION;
}

/* Higher value = more urgent. */
int scheduler_priority_value(SchedPolicy policy, const SchedEvent *ev, uint32_t now)
{
    int z;
    uint32_t wait;

    switch (policy) {
    case SCHED_FIFO:
        return 0;
    case SCHED_FIXED_PRIORITY:
        return 10 - (int)ev->fixed_priority;
    case SCHED_SAFETY_AWARE:
        z    = (int)ev->zone;
        wait = (now > ev->arrival_ms) ? (now - ev->arrival_ms) : 0u;
        if (z == (int)ZONE_SAFE && wait >= STARVATION_LIMIT_MS) {
            z = (int)ZONE_WARNING;      /* aging: never promoted to CRITICAL */
        }
        return z * 1000 + (int)ev->risk;
    default:
        return 0;
    }
}

int scheduler_deadline_met(const SchedEvent *ev)
{
    return (ev->finish_ms - ev->arrival_ms) <= ev->deadline_ms;
}

static int pick_next(SchedPolicy policy, const SchedEvent *w, const uint8_t *done,
                     int n, uint32_t now)
{
    int best = -1;
    int best_val = -100000;
    int i;

    for (i = 0; i < n; i++) {
        int v;
        if (done[i] || w[i].arrival_ms > now) {
            continue;
        }
        v = scheduler_priority_value(policy, &w[i], now);
        if (best < 0 ||
            v > best_val ||
            (v == best_val && w[i].arrival_ms < w[best].arrival_ms) ||
            (v == best_val && w[i].arrival_ms == w[best].arrival_ms &&
             w[i].event_id < w[best].event_id)) {
            best = i;
            best_val = v;
        }
    }
    return best;
}

void scheduler_run(SchedPolicy policy, const SchedEvent *in, int n,
                   SchedEvent *out_served, SchedStats *st)
{
    static SchedEvent work[MAX_EVENTS];
    uint8_t  done[MAX_EVENTS];
    uint32_t sum[3] = { 0u, 0u, 0u };
    uint32_t sum_all = 0u, sum_wait = 0u;
    uint32_t now = 0u;
    int completed = 0;
    int i;

    if (n > MAX_EVENTS) n = MAX_EVENTS;
    if (n < 0) n = 0;

    memset(st, 0, sizeof(*st));
    memset(done, 0, sizeof(done));
    for (i = 0; i < n; i++) {
        work[i] = in[i];
    }

    while (completed < n) {
        int idx = pick_next(policy, work, done, n, now);
        if (idx < 0) {
            uint32_t next_arrival = 0xFFFFFFFFu;
            for (i = 0; i < n; i++) {
                if (!done[i] && work[i].arrival_ms < next_arrival) {
                    next_arrival = work[i].arrival_ms;
                }
            }
            now = next_arrival;
            continue;
        }
        work[idx].start_ms  = now;
        now                += work[idx].service_ms;
        work[idx].finish_ms = now;
        done[idx] = 1u;
        out_served[completed++] = work[idx];
    }

    for (i = 0; i < n; i++) {
        const SchedEvent *e = &out_served[i];
        uint32_t lat = e->finish_ms - e->arrival_ms;
        int z = (int)e->zone;

        st->count[z]++;
        sum[z] += lat;
        sum_all += lat;
        sum_wait += e->start_ms - e->arrival_ms;
        if (lat > st->max_latency[z]) {
            st->max_latency[z] = lat;
        }
        if (lat > e->deadline_ms) {
            st->misses[z]++;
            st->total_misses++;
        }
        if (e->finish_ms > st->makespan_ms) {
            st->makespan_ms = e->finish_ms;
        }
    }

    st->total_events = (uint32_t)n;
    for (i = 0; i < 3; i++) {
        st->avg_latency[i] = st->count[i] ? (double)sum[i] / (double)st->count[i] : 0.0;
    }
    st->avg_latency_all = n ? (double)sum_all / (double)n : 0.0;
    st->avg_wait_all    = n ? (double)sum_wait / (double)n : 0.0;
}

const char *scheduler_policy_name(SchedPolicy policy)
{
    switch (policy) {
    case SCHED_FIFO:           return "FIFO";
    case SCHED_FIXED_PRIORITY: return "FIXED-PRIORITY";
    case SCHED_SAFETY_AWARE:   return "SAFETY-AWARE";
    default:                   return "UNKNOWN";
    }
}

const char *scheduler_source_name(SourceTask src)
{
    switch (src) {
    case SRC_PROXIMITY:  return "PROX";
    case SRC_ULTRASONIC: return "ULTRA";
    case SRC_MOTION:     return "MOTION";
    case SRC_ROUTINE:    return "ROUTINE";
    default:             return "?";
    }
}
