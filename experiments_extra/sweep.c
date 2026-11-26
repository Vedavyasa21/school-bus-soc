/* sweep.c - multi-seed, multi-load experiment driver (7 policies + finer load sweep).
 * Build: gcc -O2 -Wall -Wextra -I ../src -o ../build/sweep sweep.c ../src/sensor_input.c ../src/sensor_fusion.c ../src/danger_detection.c ../src/priority_scheduler.c
 * Run  : ../build/sweep 40 100 > results/sweep.csv 2> results/det.csv
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sensor_input.h"
#include "sensor_fusion.h"
#include "danger_detection.h"
#include "priority_scheduler.h"

typedef enum { K_FIFO = 0, K_ZONE_ARR = 1, K_EDF = 2 } Key;
#define NPOL 7
static const char *POL_NAME[NPOL] = {
    "FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "ZONE-FIFO", "EDF", "P-ZONE-FIFO", "P-EDF"
};

static SensorFrame  frames[MAX_EVENTS];
static FusionResult fres[MAX_EVENTS];
static DangerResult dres[MAX_EVENTS];
static SchedEvent   base_ev[MAX_EVENTS], events[MAX_EVENTS], served[MAX_EVENTS];

/* Returns 1 if job i should run before job j under key k */
static int better(const SchedEvent *e, int i, int j, Key k)
{
    long ki, kj;
    if (j < 0) return 1;
    if (k == K_FIFO) {
        ki = e[i].arrival_ms;
        kj = e[j].arrival_ms;
    } else if (k == K_EDF) {
        ki = (long)e[i].arrival_ms + (long)e[i].deadline_ms;
        kj = (long)e[j].arrival_ms + (long)e[j].deadline_ms;
    } else {
        if (e[i].zone != e[j].zone) return e[i].zone > e[j].zone;
        ki = e[i].arrival_ms;
        kj = e[j].arrival_ms;
    }
    if (ki != kj) return ki < kj;
    return e[i].event_id < e[j].event_id;
}

/* 1-ms discrete tick simulator: preempt=0 keeps the running job until completion */
static void tick_sim(const SchedEvent *e, int n, Key k, int preempt, uint32_t *fin)
{
    int rem[MAX_EVENTS];
    int done = 0, cur = -1, i;
    uint32_t t = 0;

    for (i = 0; i < n; i++) rem[i] = (int)e[i].service_ms;
    while (done < n) {
        if (preempt || cur < 0) {
            int best = -1;
            for (i = 0; i < n; i++) {
                if (rem[i] > 0 && e[i].arrival_ms <= t && better(e, i, best, k)) {
                    best = i;
                }
            }
            cur = best;
        }
        if (cur < 0) {
            uint32_t na = 0xFFFFFFFFu;
            for (i = 0; i < n; i++) {
                if (rem[i] > 0 && e[i].arrival_ms < na) na = e[i].arrival_ms;
            }
            t = na;
            continue;
        }
        rem[cur]--;
        t++;
        if (rem[cur] == 0) {
            fin[cur] = t;
            done++;
            cur = -1;
        }
    }
}

typedef struct {
    int  cnt[3], miss[3];
    long sum[3];
    int  mx[3];
    long sum_all;
    int  makespan;
} Met;

static void metrics(const SchedEvent *e, const uint32_t *fin, int n, Met *m)
{
    int i;
    memset(m, 0, sizeof(*m));
    for (i = 0; i < n; i++) {
        int z   = (int)e[i].zone;
        int lat = (int)(fin[i] - e[i].arrival_ms);
        m->cnt[z]++;
        m->sum[z] += lat;
        m->sum_all += lat;
        if (lat > m->mx[z]) m->mx[z] = lat;
        if ((uint32_t)lat > e[i].deadline_ms) m->miss[z]++;
        if ((int)fin[i] > m->makespan) m->makespan = (int)fin[i];
    }
}

static void print_row(unsigned seed, unsigned load, const char *pol, const Met *m, double rho)
{
    printf("%u,%u,%s,%d,%d,%d,%d,%d,%d,%ld,%d,%ld,%d,%ld,%d,%ld,%d,%.3f\n",
           seed, load, pol,
           m->cnt[2], m->cnt[1], m->cnt[0],
           m->miss[2], m->miss[1], m->miss[0],
           m->sum[2], m->mx[2], m->sum[1], m->mx[1], m->sum[0], m->mx[0],
           m->sum_all, m->makespan, rho);
}

int main(int argc, char **argv)
{
    int n = 40, nseeds = 100;
    unsigned s, li, p;
    int i;
    static const unsigned loads[] = {
        50, 75, 100, 110, 120, 125, 130, 140, 150, 175, 200, 300, 400
    };

    if (argc > 1) n = atoi(argv[1]);
    if (argc > 2) nseeds = atoi(argv[2]);

    printf("seed,load,policy,crit_n,warn_n,safe_n,crit_miss,warn_miss,safe_miss,"
           "crit_sum,crit_max,warn_sum,warn_max,safe_sum,safe_max,all_sum,makespan,rho\n");

    for (s = 1; s <= (unsigned)nseeds + 1; s++) {
        unsigned seed = (s == (unsigned)nseeds + 1) ? 2024u : s;
        unsigned tp = 0, fp = 0, fn = 0, tn = 0;

        sensor_init(seed);
        n = sensor_generate_frames(frames, n);
        for (i = 0; i < n; i++) {
            SourceTask src;
            fusion_process(&frames[i], &fres[i]);
            danger_classify(&frames[i], &fres[i], &dres[i]);
            src = scheduler_source_from_scores(fres[i].us_score, fres[i].prox_score,
                                               fres[i].motion_score);
            scheduler_build_event(&base_ev[i], frames[i].event_id, frames[i].timestamp_ms,
                                  dres[i].zone, dres[i].risk_score, fres[i].confidence,
                                  fres[i].est_distance_cm, src);
            if (fres[i].child_present && frames[i].child_truth) tp++;
            else if (fres[i].child_present) fp++;
            else if (frames[i].child_truth) fn++;
            else tn++;
        }
        fprintf(stderr, "DET,%u,%u,%u,%u,%u\n", seed, tp, fp, fn, tn);

        for (li = 0; li < sizeof(loads) / sizeof(loads[0]); li++) {
            unsigned load = loads[li];
            long work = 0;
            double rho;
            uint32_t fin[MAX_EVENTS], fifo_fin[MAX_EVENTS];

            for (i = 0; i < n; i++) {
                events[i] = base_ev[i];
                events[i].arrival_ms = (uint32_t)(((uint64_t)base_ev[i].arrival_ms * 100u) / load);
                work += events[i].service_ms;
            }
            rho = (double)work / (double)events[n - 1].arrival_ms;

            for (p = 0; p < NPOL; p++) {
                Met m;
                if (p <= 2) {
                    SchedStats st;
                    scheduler_run((SchedPolicy)p, events, n, served, &st);
                    for (i = 0; i < n; i++) fin[served[i].event_id] = served[i].finish_ms;
                    if (p == 0) memcpy(fifo_fin, fin, sizeof(fin));
                } else if (p == 3) {
                    tick_sim(events, n, K_ZONE_ARR, 0, fin);
                } else if (p == 4) {
                    tick_sim(events, n, K_EDF, 0, fin);
                } else if (p == 5) {
                    tick_sim(events, n, K_ZONE_ARR, 1, fin);
                } else {
                    tick_sim(events, n, K_EDF, 1, fin);
                }
                metrics(events, fin, n, &m);
                print_row(seed, load, POL_NAME[p], &m, rho);
            }

            {
                uint32_t chk[MAX_EVENTS];
                tick_sim(events, n, K_FIFO, 0, chk);
                for (i = 0; i < n; i++) {
                    if (chk[i] != fifo_fin[i]) {
                        fprintf(stderr, "MISMATCH FIFO seed %u load %u\n", seed, load);
                        return 1;
                    }
                }
            }
        }
    }
    return 0;
}
