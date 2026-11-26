#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sensor_input.h"
#include "sensor_fusion.h"
#include "danger_detection.h"
#include "priority_scheduler.h"
#include "warning_system.h"

#if defined(__riscv)
    #define TARGET_ARCH_STR "RISC-V"
#elif defined(__x86_64__) || defined(_M_X64)
    #define TARGET_ARCH_STR "x86-64"
#elif defined(__i386__) || defined(_M_IX86)
    #define TARGET_ARCH_STR "x86-32"
#elif defined(__aarch64__)
    #define TARGET_ARCH_STR "ARM64"
#else
    #define TARGET_ARCH_STR "Host-Native"
#endif

static SensorFrame    frames[MAX_EVENTS];
static FusionResult   fres[MAX_EVENTS];
static DangerResult   dres[MAX_EVENTS];
static WarningMessage wmsg[MAX_EVENTS];
static SchedEvent     events[MAX_EVENTS];
static SchedEvent     served[MAX_EVENTS];
static SchedStats     stats[SCHED_POLICY_COUNT];

static void print_banner(int n, unsigned seed, int verbose)
{
    printf("==============================================================\n");
    printf(" Smart School Bus Safety and Priority Management SoC (%s)\n", TARGET_ARCH_STR);
    printf("==============================================================\n");
    printf(" events=%d  seed=%u  verbose=%d\n\n", n, seed, verbose);
}

static void stage_detection(int n, int verbose)
{
    int i;
    unsigned tp = 0, fp = 0, fn = 0, tn = 0;
    unsigned zone_cnt[3] = { 0, 0, 0 };

    printf("---- STAGE 1: SENSOR INPUT, FUSION AND DANGER-ZONE DETECTION ----\n");
    if (verbose) {
        printf(" ID   T(ms) |  US  PR  MO | SCENE    | CONF DET TRU  DIST | ZONE     RISK | SRC\n");
    }

    for (i = 0; i < n; i++) {
        SourceTask src;

        fusion_process(&frames[i], &fres[i]);
        danger_classify(&frames[i], &fres[i], &dres[i]);
        src = scheduler_source_from_scores(fres[i].us_score, fres[i].prox_score,
                                           fres[i].motion_score);
        scheduler_build_event(&events[i], frames[i].event_id, frames[i].timestamp_ms,
                              dres[i].zone, dres[i].risk_score, fres[i].confidence,
                              fres[i].est_distance_cm, src);
        warning_generate(frames[i].event_id, dres[i].zone, dres[i].risk_score,
                         fres[i].confidence, fres[i].est_distance_cm, &wmsg[i]);

        zone_cnt[(int)dres[i].zone]++;
        if (fres[i].child_present && frames[i].child_truth)        tp++;
        else if (fres[i].child_present && !frames[i].child_truth)  fp++;
        else if (!fres[i].child_present && frames[i].child_truth)  fn++;
        else                                                       tn++;

        if (verbose) {
            printf("%3u %7u | %3u %3u %3u | %-8s | %3u  %-3s %-3s %4u | %-8s %4u | %s\n",
                   (unsigned)frames[i].event_id, (unsigned)frames[i].timestamp_ms,
                   (unsigned)frames[i].ultrasonic_cm, (unsigned)frames[i].proximity_cm,
                   (unsigned)frames[i].motion_level,
                   sensor_scene_name(frames[i].scene),
                   (unsigned)fres[i].confidence,
                   fres[i].child_present ? "YES" : "no",
                   frames[i].child_truth ? "YES" : "no",
                   (unsigned)fres[i].est_distance_cm,
                   danger_zone_name(dres[i].zone), (unsigned)dres[i].risk_score,
                   scheduler_source_name(src));
        }
    }

    printf("\nDetection summary: TP=%u FP=%u FN=%u TN=%u\n", tp, fp, fn, tn);
    printf("Zone summary     : SAFE=%u WARNING=%u CRITICAL=%u\n\n",
           zone_cnt[0], zone_cnt[1], zone_cnt[2]);
}

static void stage_scheduling(int n, int verbose)
{
    int p, i;

    printf("---- STAGE 2: SCHEDULING, PRIORITY DECISIONS AND WARNINGS ----\n");

    for (p = 0; p < (int)SCHED_POLICY_COUNT; p++) {
        SchedPolicy pol = (SchedPolicy)p;

        scheduler_run(pol, events, n, served, &stats[p]);
        warning_log_reset();

        printf("\n>>> Policy: %s\n", scheduler_policy_name(pol));
        if (verbose) {
            printf(" POS  ID  ZONE     SRC     PRIO  ARR START   FIN   LAT  DEADLINE\n");
        }
        for (i = 0; i < n; i++) {
            const SchedEvent *e = &served[i];
            int prio = scheduler_priority_value(pol, e, e->start_ms);

            warning_log_record(pol, e, &wmsg[e->event_id]);
            if (verbose) {
                if (pol == SCHED_FIFO) {
                    printf(" %3d %3u  %-8s %-7s    -  %5u %5u %5u %5u  %s\n",
                           i, (unsigned)e->event_id, danger_zone_name(e->zone),
                           scheduler_source_name(e->source),
                           (unsigned)e->arrival_ms, (unsigned)e->start_ms,
                           (unsigned)e->finish_ms, (unsigned)(e->finish_ms - e->arrival_ms),
                           scheduler_deadline_met(e) ? "MET" : "MISSED");
                } else {
                    printf(" %3d %3u  %-8s %-7s %4d  %5u %5u %5u %5u  %s\n",
                           i, (unsigned)e->event_id, danger_zone_name(e->zone),
                           scheduler_source_name(e->source), prio,
                           (unsigned)e->arrival_ms, (unsigned)e->start_ms,
                           (unsigned)e->finish_ms, (unsigned)(e->finish_ms - e->arrival_ms),
                           scheduler_deadline_met(e) ? "MET" : "MISSED");
                }
            }
        }

        if (verbose && pol == SCHED_SAFETY_AWARE) {
            printf("\n  Warnings dispatched (safety-aware order, non-safe events):\n");
            for (i = 0; i < n; i++) {
                const SchedEvent *e = &served[i];
                if (e->zone != ZONE_SAFE) {
                    warning_print(&wmsg[e->event_id], e->finish_ms);
                }
            }
            printf("\n");
        }
        warning_log_print_summary(pol);
    }
    printf("\n");
}

static void stage_comparison(int n)
{
    int p;
    double base = stats[SCHED_FIFO].avg_latency[ZONE_CRITICAL];

    printf("---- STAGE 3: SCHEDULER COMPARISON (%d events) ----\n", n);
    printf("%-15s %9s %9s %9s %8s %8s %8s %9s %9s\n",
           "Policy", "AvgAll", "AvgCrit", "AvgWarn", "MaxCrit", "MissCrit",
           "MissAll", "Makespan", "AvgWait");
    for (p = 0; p < (int)SCHED_POLICY_COUNT; p++) {
        const SchedStats *s = &stats[p];
        printf("%-15s %9.2f %9.2f %9.2f %8u %8u %8u %9u %9.2f\n",
               scheduler_policy_name((SchedPolicy)p),
               s->avg_latency_all, s->avg_latency[ZONE_CRITICAL],
               s->avg_latency[ZONE_WARNING],
               (unsigned)s->max_latency[ZONE_CRITICAL],
               (unsigned)s->misses[ZONE_CRITICAL],
               (unsigned)s->total_misses, (unsigned)s->makespan_ms,
               s->avg_wait_all);
    }
    printf("(latencies in ms of simulated time)\n");

    if (base > 0.0) {
        for (p = 1; p < (int)SCHED_POLICY_COUNT; p++) {
            double cur = stats[p].avg_latency[ZONE_CRITICAL];
            printf("Critical-event latency vs FIFO, %-14s: %+.1f%%\n",
                   scheduler_policy_name((SchedPolicy)p), ((cur - base) / base) * 100.0);
        }
    }

    printf("\n");
    for (p = 0; p < (int)SCHED_POLICY_COUNT; p++) {
        const SchedStats *s = &stats[p];
        printf("RESULT,%s,%d,%.2f,%.2f,%u,%u,%u,%u\n",
               scheduler_policy_name((SchedPolicy)p), n,
               s->avg_latency_all, s->avg_latency[ZONE_CRITICAL],
               (unsigned)s->max_latency[ZONE_CRITICAL],
               (unsigned)s->misses[ZONE_CRITICAL],
               (unsigned)s->total_misses, (unsigned)s->makespan_ms);
    }
}

int main(int argc, char **argv)
{
    int n = 40;
    unsigned seed = 2024u;
    int verbose = 1;
    unsigned load = 100;

    if (argc > 1) n = atoi(argv[1]);
    if (argc > 2) seed = (unsigned)strtoul(argv[2], NULL, 10);
    if (argc > 3) verbose = atoi(argv[3]);
    if (argc > 4) load = (unsigned)strtoul(argv[4], NULL, 10);
    if (n < 1) n = 1;
    if (n > MAX_EVENTS) n = MAX_EVENTS;
    if (load < 5) load = 5;

    print_banner(n, seed, verbose);

    sensor_init((uint32_t)seed);
    n = sensor_generate_frames(frames, n);

    stage_detection(n, verbose);

    if (load != 100) {
        printf("---- STRESS TEST: LOAD = %u%% (arrivals %.1fx faster) ----\n\n", load, load / 100.0);
        for (int k = 0; k < n; k++) {
            events[k].arrival_ms = (uint32_t)(((uint64_t)events[k].arrival_ms * 100u) / load);
        }
    }

    stage_scheduling(n, verbose);
    stage_comparison(n);

    printf("\nSimulation complete.\n");
    return 0;
}
