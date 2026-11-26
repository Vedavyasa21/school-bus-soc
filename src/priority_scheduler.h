#ifndef PRIORITY_SCHEDULER_H
#define PRIORITY_SCHEDULER_H

#include <stdint.h>
#include "danger_detection.h"

#define STARVATION_LIMIT_MS 250u

typedef enum {
    SCHED_FIFO = 0,
    SCHED_FIXED_PRIORITY = 1,
    SCHED_SAFETY_AWARE = 2,
    SCHED_POLICY_COUNT = 3
} SchedPolicy;

/* Fixed-priority classes (0 = highest priority) */
typedef enum {
    SRC_PROXIMITY  = 0,
    SRC_ULTRASONIC = 1,
    SRC_MOTION     = 2,
    SRC_ROUTINE    = 3
} SourceTask;

typedef struct {
    uint32_t   event_id;
    uint32_t   arrival_ms;
    uint32_t   start_ms;
    uint32_t   finish_ms;
    uint32_t   service_ms;
    uint32_t   deadline_ms;     /* relative to arrival */
    ZoneLevel  zone;
    uint8_t    risk;
    uint8_t    confidence;
    uint16_t   distance_cm;
    SourceTask source;
    uint8_t    fixed_priority;
} SchedEvent;

typedef struct {
    uint32_t total_events;
    uint32_t count[3];
    uint32_t max_latency[3];
    uint32_t misses[3];
    double   avg_latency[3];
    double   avg_latency_all;
    double   avg_wait_all;
    uint32_t total_misses;
    uint32_t makespan_ms;
} SchedStats;

void        scheduler_build_event(SchedEvent *ev, uint32_t id, uint32_t arrival_ms,
                                  ZoneLevel zone, uint8_t risk, uint8_t confidence,
                                  uint16_t distance_cm, SourceTask source);
SourceTask  scheduler_source_from_scores(uint8_t us, uint8_t prox, uint8_t motion);
int         scheduler_priority_value(SchedPolicy policy, const SchedEvent *ev, uint32_t now);
int         scheduler_deadline_met(const SchedEvent *ev);
void        scheduler_run(SchedPolicy policy, const SchedEvent *in, int n,
                          SchedEvent *out_served, SchedStats *stats);
const char *scheduler_policy_name(SchedPolicy policy);
const char *scheduler_source_name(SourceTask src);

#endif /* PRIORITY_SCHEDULER_H */
