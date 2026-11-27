/* profile_stages.c - Per-stage gem5 cycle/instruction profiler (zero printf inside measured regions).
 * Measures each controller stage using both RISC-V rdcycle/rdinstret CSRs and gem5 m5ops.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#ifdef GEM5_M5OPS
#include <gem5/m5ops.h>
#else
static inline void m5_reset_stats(uint64_t ns_delay, uint64_t ns_period) {
    (void)ns_delay; (void)ns_period;
}
static inline void m5_dump_stats(uint64_t ns_delay, uint64_t ns_period) {
    (void)ns_delay; (void)ns_period;
}
#endif

#include "sensor_input.h"
#include "sensor_fusion.h"
#include "danger_detection.h"
#include "priority_scheduler.h"
#include "warning_system.h"

static inline uint64_t read_cycles(void)
{
#if defined(__riscv)
    uint64_t c;
    __asm__ volatile ("rdcycle %0" : "=r"(c));
    return c;
#else
    return 0;
#endif
}

static inline uint64_t read_instret(void)
{
#if defined(__riscv)
    uint64_t inst;
    __asm__ volatile ("rdinstret %0" : "=r"(inst));
    return inst;
#else
    return 0;
#endif
}

static SensorFrame    frames[MAX_EVENTS];
static FusionResult   fres[MAX_EVENTS];
static DangerResult   dres[MAX_EVENTS];
static WarningMessage wmsg[MAX_EVENTS];
static SchedEvent     events[MAX_EVENTS];
static SchedEvent     served[MAX_EVENTS];
static SchedStats     stats[SCHED_POLICY_COUNT];

typedef struct {
    const char *name;
    uint64_t    cycles;
    uint64_t    insts;
} StageProf;

int main(int argc, char **argv)
{
    int n = 40;
    unsigned seed = 2024u;
    int i, p;
    StageProf prof[7];
    uint64_t c0, c1, i0, i1;
    uint64_t total_cyc = 0, total_ins = 0;

    if (argc > 1) n = atoi(argv[1]);
    if (argc > 2) seed = (unsigned)strtoul(argv[2], NULL, 10);
    if (n < 1) n = 1;
    if (n > MAX_EVENTS) n = MAX_EVENTS;

    /* Warm up code/data paths without printing */
    sensor_init((uint32_t)seed);
    n = sensor_generate_frames(frames, n);
    for (i = 0; i < n; i++) {
        fusion_process(&frames[i], &fres[i]);
        danger_classify(&frames[i], &fres[i], &dres[i]);
    }

    /* Reset RNG for deterministic measured pass */
    sensor_init((uint32_t)seed);

    /* 0: Sensor input generation */
    m5_reset_stats(0, 0);
    c0 = read_cycles(); i0 = read_instret();
    n = sensor_generate_frames(frames, n);
    c1 = read_cycles(); i1 = read_instret();
    m5_dump_stats(0, 0);
    prof[0] = (StageProf){ "SensorInput", c1 - c0, i1 - i0 };

    /* 1: Multi-sensor fusion */
    m5_reset_stats(0, 0);
    c0 = read_cycles(); i0 = read_instret();
    for (i = 0; i < n; i++) {
        fusion_process(&frames[i], &fres[i]);
    }
    c1 = read_cycles(); i1 = read_instret();
    m5_dump_stats(0, 0);
    prof[1] = (StageProf){ "SensorFusion", c1 - c0, i1 - i0 };

    /* 2: Danger-zone classification */
    m5_reset_stats(0, 0);
    c0 = read_cycles(); i0 = read_instret();
    for (i = 0; i < n; i++) {
        SourceTask src;
        danger_classify(&frames[i], &fres[i], &dres[i]);
        src = scheduler_source_from_scores(fres[i].us_score, fres[i].prox_score,
                                           fres[i].motion_score);
        scheduler_build_event(&events[i], frames[i].event_id, frames[i].timestamp_ms,
                              dres[i].zone, dres[i].risk_score, fres[i].confidence,
                              fres[i].est_distance_cm, src);
    }
    c1 = read_cycles(); i1 = read_instret();
    m5_dump_stats(0, 0);
    prof[2] = (StageProf){ "DangerDetect", c1 - c0, i1 - i0 };

    /* 3..5: Schedulers (FIFO, FIXED, SAFETY-AWARE) */
    for (p = 0; p < (int)SCHED_POLICY_COUNT; p++) {
        m5_reset_stats(0, 0);
        c0 = read_cycles(); i0 = read_instret();
        scheduler_run((SchedPolicy)p, events, n, served, &stats[p]);
        c1 = read_cycles(); i1 = read_instret();
        m5_dump_stats(0, 0);
        prof[3 + p] = (StageProf){ scheduler_policy_name((SchedPolicy)p), c1 - c0, i1 - i0 };
    }

    /* 6: Warning & V2V message generation */
    m5_reset_stats(0, 0);
    c0 = read_cycles(); i0 = read_instret();
    for (i = 0; i < n; i++) {
        warning_generate(frames[i].event_id, dres[i].zone, dres[i].risk_score,
                         fres[i].confidence, fres[i].est_distance_cm, &wmsg[i]);
    }
    c1 = read_cycles(); i1 = read_instret();
    m5_dump_stats(0, 0);
    prof[6] = (StageProf){ "WarningGen", c1 - c0, i1 - i0 };

    /* Print results only AFTER all measured sections complete */
    printf("======================================================================\n");
    printf(" gem5 Per-Stage Compute Profile (n=%d, seed=%u, 1 GHz ref clock)\n", n, seed);
    printf("======================================================================\n");
    printf("%-16s %10s %10s %10s %10s %8s\n",
           "Stage", "Cycles", "Insts", "Cyc/Evt", "Time(us)", "IPC");
    for (i = 0; i < 7; i++) {
        double ipc = prof[i].cycles ? (double)prof[i].insts / (double)prof[i].cycles : 0.0;
        double us  = (double)prof[i].cycles / 1000.0;
        double cpe = (double)prof[i].cycles / (double)n;
        printf("%-16s %10llu %10llu %10.1f %10.3f %8.3f\n",
               prof[i].name,
               (unsigned long long)prof[i].cycles,
               (unsigned long long)prof[i].insts,
               cpe, us, ipc);
        total_cyc += prof[i].cycles;
        total_ins += prof[i].insts;
    }
    printf("----------------------------------------------------------------------\n");
    printf("%-16s %10llu %10llu %10.1f %10.3f %8.3f\n",
           "TOTAL_COMPUTE",
           (unsigned long long)total_cyc,
           (unsigned long long)total_ins,
           (double)total_cyc / (double)n,
           (double)total_cyc / 1000.0,
           total_cyc ? (double)total_ins / (double)total_cyc : 0.0);
    {
        uint64_t core_c = prof[0].cycles + prof[1].cycles + prof[2].cycles + prof[6].cycles;
        uint64_t core_i = prof[0].insts  + prof[1].insts  + prof[2].insts  + prof[6].insts;
        for (p = 0; p < (int)SCHED_POLICY_COUNT; p++) {
            uint64_t sc = core_c + prof[3 + p].cycles;
            uint64_t si = core_i + prof[3 + p].insts;
            char sname[32];
            snprintf(sname, sizeof(sname), "SINGLE_%s", prof[3 + p].name);
            printf("%-22s %10llu %10llu %10.1f %10.3f %8.3f\n",
                   sname,
                   (unsigned long long)sc,
                   (unsigned long long)si,
                   (double)sc / (double)n,
                   (double)sc / 1000.0,
                   sc ? (double)si / (double)sc : 0.0);
        }
    }
    return 0;
}
