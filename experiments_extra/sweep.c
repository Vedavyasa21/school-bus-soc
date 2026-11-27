/* sweep.c - Multi-seed, multi-load scheduler experiment driver covering:
 *   - 9 policies (including 2x2 factorial ablation: risk-only & aging-only)
 *   - RAW_40, COAL_40 (25 ms track coalescing), LONG_RAW (N=1000), LONG_COAL (N=1000)
 *   - CPU50_1000 (50 MHz MinorCPU + 1.5x RTOS overhead = 109 us/event pure-CPU model)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sensor_input.h"
#include "sensor_fusion.h"
#include "danger_detection.h"
#include "priority_scheduler.h"

#define NPOL 9
static const char *POL_NAME[NPOL] = {
    "FIFO", "FIXED-SENSOR", "SAFETY-AWARE", "SA-RISK-ONLY", "SA-AGING-ONLY",
    "ZONE-FIFO", "EDF", "P-ZONE-FIFO", "P-EDF"
};

static SensorFrame  frames[MAX_EVENTS];
static FusionResult fres[MAX_EVENTS];
static DangerResult dres[MAX_EVENTS];
static SchedEvent   base_ev[MAX_EVENTS], coal_ev[MAX_EVENTS], events[MAX_EVENTS];
static uint32_t     coal_end_base[MAX_EVENTS], raw_end_base[MAX_EVENTS];

static int is_preempt(int pol) { return (pol == 7 || pol == 8); }

static int pick_compare(const SchedEvent *e, int i, int j, int pol, uint32_t now)
{
    long ki, kj;
    if (j < 0) return 1;
    if (pol == 0) {
        ki = (long)e[i].arrival_ms;
        kj = (long)e[j].arrival_ms;
    } else if (pol == 1) {
        int pi = 10 - (int)e[i].fixed_priority;
        int pj = 10 - (int)e[j].fixed_priority;
        if (pi != pj) return pi > pj;
        ki = (long)e[i].arrival_ms;
        kj = (long)e[j].arrival_ms;
    } else if (pol == 2 || pol == 3 || pol == 4 || pol == 5 || pol == 7) {
        int zi = (int)e[i].zone;
        int zj = (int)e[j].zone;
        if (pol == 2 || pol == 4) {
            uint32_t wi = (now > e[i].arrival_ms) ? (now - e[i].arrival_ms) : 0u;
            uint32_t wj = (now > e[j].arrival_ms) ? (now - e[j].arrival_ms) : 0u;
            if (zi == (int)ZONE_SAFE && wi >= STARVATION_LIMIT_MS) zi = (int)ZONE_WARNING;
            if (zj == (int)ZONE_SAFE && wj >= STARVATION_LIMIT_MS) zj = (int)ZONE_WARNING;
        }
        if (zi != zj) return zi > zj;
        if (pol == 2 || pol == 3) {
            if (e[i].risk != e[j].risk) return e[i].risk > e[j].risk;
        }
        ki = (long)e[i].arrival_ms;
        kj = (long)e[j].arrival_ms;
    } else {
        /* EDF / P-EDF */
        ki = (long)e[i].arrival_ms + (long)e[i].deadline_ms;
        kj = (long)e[j].arrival_ms + (long)e[j].deadline_ms;
    }
    if (ki != kj) return ki < kj;
    return e[i].event_id < e[j].event_id;
}

static void fast_sim(const SchedEvent *e, int n, int pol, uint32_t *fin)
{
    static uint32_t rem[MAX_EVENTS];
    int done = 0, cur = -1, i;
    int next_unarrived = 0;
    uint32_t t = 0;
    int preempt = is_preempt(pol);

    for (i = 0; i < n; i++) rem[i] = e[i].service_ms;

    while (done < n) {
        while (next_unarrived < n && e[next_unarrived].arrival_ms <= t) {
            next_unarrived++;
        }
        if (preempt || cur < 0) {
            int best = -1;
            for (i = 0; i < next_unarrived; i++) {
                if (rem[i] > 0 && pick_compare(e, i, best, pol, t)) {
                    best = i;
                }
            }
            cur = best;
        }
        if (cur < 0) {
            if (next_unarrived < n) {
                t = e[next_unarrived].arrival_ms;
                continue;
            }
            break;
        }
        {
            uint32_t step = rem[cur];
            if (preempt && next_unarrived < n) {
                uint32_t dt_arr = e[next_unarrived].arrival_ms - t;
                if (dt_arr < step) step = dt_arr;
            }
            t += step;
            rem[cur] -= step;
            if (rem[cur] == 0) {
                fin[cur] = t;
                done++;
                cur = -1;
            }
        }
    }
}

/* Coalesce consecutive WARNING/CRITICAL frames separated by <= win_ms nominal */
static int coalesce_stream(const SchedEvent *in, int n, uint32_t win_ms,
                           SchedEvent *out, uint32_t *out_end_t)
{
    int m = 0, i;
    int open_idx[3] = { -1, -1, -1 };
    uint32_t last_t[3] = { 0, 0, 0 };

    for (i = 0; i < n; i++) {
        int z = (int)in[i].zone;
        if (z > (int)ZONE_SAFE && open_idx[z] >= 0 &&
            (in[i].arrival_ms - last_t[z]) <= win_ms) {
            int oi = open_idx[z];
            if (in[i].risk > out[oi].risk) out[oi].risk = in[i].risk;
            out_end_t[oi] = in[i].arrival_ms;
            last_t[z] = in[i].arrival_ms;
        } else {
            out[m] = in[i];
            out_end_t[m] = in[i].arrival_ms;
            if (z > (int)ZONE_SAFE) {
                open_idx[z] = m;
                last_t[z] = in[i].arrival_ms;
            }
            m++;
        }
    }
    return m;
}

typedef struct {
    int  cnt[3], miss[3];
    long long sum[3];
    long mx[3];
    long long sum_all;
    long makespan;
} Met;

static void metrics(const SchedEvent *e, const uint32_t *fin, int n, Met *m)
{
    int i;
    memset(m, 0, sizeof(*m));
    for (i = 0; i < n; i++) {
        int z = (int)e[i].zone;
        long lat = (long)(fin[i] - e[i].arrival_ms);
        m->cnt[z]++;
        m->sum[z] += lat;
        m->sum_all += lat;
        if (lat > m->mx[z]) m->mx[z] = lat;
        if ((uint32_t)lat > e[i].deadline_ms) m->miss[z]++;
        if ((long)fin[i] > m->makespan) m->makespan = (long)fin[i];
    }
}

static void run_mode(FILE *fp_main, FILE *fp_legacy, const char *mode_name,
                     unsigned seed, int n_frames, int coalesce, int cpu50_us,
                     const unsigned *loads, int nloads)
{
    int i, li, p;
    const SchedEvent *src_ev = base_ev;
    const uint32_t *src_end = raw_end_base;
    int m = n_frames;

    if (coalesce) {
        m = coalesce_stream(base_ev, n_frames, 25u, coal_ev, coal_end_base);
        src_ev = coal_ev;
        src_end = coal_end_base;
    }

    for (li = 0; li < nloads; li++) {
        unsigned load = loads[li];
        long long work = 0;
        double rho;
        uint32_t fin[MAX_EVENTS];

        for (i = 0; i < m; i++) {
            events[i] = src_ev[i];
            if (cpu50_us) {
                /* Microsecond scale: 110 us per event (MinorCPU 3,667.8 cyc @ 50 MHz * 1.5 RTOS) */
                events[i].arrival_ms  = (uint32_t)(((uint64_t)src_ev[i].arrival_ms * 100000ULL) / load);
                events[i].service_ms  = 110u;
                events[i].deadline_ms = src_ev[i].deadline_ms * 1000u;
            } else {
                uint32_t end_s = (uint32_t)(((uint64_t)src_end[i] * 100u) / load);
                events[i].arrival_ms  = (uint32_t)(((uint64_t)src_ev[i].arrival_ms * 100u) / load);
                events[i].deadline_ms = (end_s + src_ev[i].deadline_ms) - events[i].arrival_ms;
            }
            work += (long long)events[i].service_ms;
        }
        rho = events[m - 1].arrival_ms ? (double)work / (double)events[m - 1].arrival_ms : 0.0;

        for (p = 0; p < NPOL; p++) {
            Met met;
            fast_sim(events, m, p, fin);
            metrics(events, fin, m, &met);
            fprintf(fp_main, "%s,%u,%u,%s,%d,%d,%d,%d,%d,%d,%lld,%ld,%lld,%ld,%lld,%ld,%lld,%ld,%.4f\n",
                    mode_name, seed, load, POL_NAME[p],
                    met.cnt[2], met.cnt[1], met.cnt[0],
                    met.miss[2], met.miss[1], met.miss[0],
                    met.sum[2], met.mx[2], met.sum[1], met.mx[1], met.sum[0], met.mx[0],
                    met.sum_all, met.makespan, rho);
            if (fp_legacy) {
                fprintf(fp_legacy, "%u,%u,%s,%d,%d,%d,%d,%d,%d,%lld,%ld,%lld,%ld,%lld,%ld,%lld,%ld,%.3f\n",
                        seed, load, POL_NAME[p],
                        met.cnt[2], met.cnt[1], met.cnt[0],
                        met.miss[2], met.miss[1], met.miss[0],
                        met.sum[2], met.mx[2], met.sum[1], met.mx[1], met.sum[0], met.mx[0],
                        met.sum_all, met.makespan, rho);
            }
        }
    }
}

int main(void)
{
    unsigned s;
    int i;
    static const unsigned loads[] = {
        50, 75, 100, 110, 120, 125, 130, 140, 150, 175, 200, 300, 400
    };
    int nloads = (int)(sizeof(loads) / sizeof(loads[0]));
    FILE *fp_all = fopen("results/sweep_all.csv", "w");
    FILE *fp_leg = fopen("results/sweep.csv", "w");
    FILE *fp_det = fopen("results/det.csv", "w");

    fprintf(fp_all, "mode,seed,load,policy,crit_n,warn_n,safe_n,crit_miss,warn_miss,safe_miss,"
                    "crit_sum,crit_max,warn_sum,warn_max,safe_sum,safe_max,all_sum,makespan,rho\n");
    fprintf(fp_leg, "seed,load,policy,crit_n,warn_n,safe_n,crit_miss,warn_miss,safe_miss,"
                    "crit_sum,crit_max,warn_sum,warn_max,safe_sum,safe_max,all_sum,makespan,rho\n");

    for (s = 1; s <= 101u; s++) {
        unsigned seed = (s == 101u) ? 2024u : s;
        unsigned tp = 0, fp = 0, fn = 0, tn = 0;
        int n;

        /* Part A: N = 40 runs (RAW_40 & COAL_40) */
        sensor_init(seed);
        n = sensor_generate_frames(frames, 40);
        for (i = 0; i < n; i++) {
            SourceTask src;
            fusion_process(&frames[i], &fres[i]);
            danger_classify(&frames[i], &fres[i], &dres[i]);
            src = scheduler_source_from_scores(fres[i].us_score, fres[i].prox_score, fres[i].motion_score);
            scheduler_build_event(&base_ev[i], frames[i].event_id, frames[i].timestamp_ms,
                                  dres[i].zone, dres[i].risk_score, fres[i].confidence,
                                  fres[i].est_distance_cm, src);
            raw_end_base[i] = frames[i].timestamp_ms;
            if (fres[i].child_present && frames[i].child_truth) tp++;
            else if (fres[i].child_present) fp++;
            else if (frames[i].child_truth) fn++;
            else tn++;
        }
        fprintf(fp_det, "DET,%u,%u,%u,%u,%u\n", seed, tp, fp, fn, tn);
        run_mode(fp_all, fp_leg, "RAW_40",  seed, n, 0, 0, loads, nloads);
        run_mode(fp_all, NULL,   "COAL_40", seed, n, 1, 0, loads, nloads);

        /* Part B: N = 1,000 steady-state runs (seeds 1..100) */
        if (seed != 2024u) {
            sensor_init(seed);
            n = sensor_generate_frames(frames, 1000);
            for (i = 0; i < n; i++) {
                SourceTask src;
                fusion_process(&frames[i], &fres[i]);
                danger_classify(&frames[i], &fres[i], &dres[i]);
                src = scheduler_source_from_scores(fres[i].us_score, fres[i].prox_score, fres[i].motion_score);
                scheduler_build_event(&base_ev[i], frames[i].event_id, frames[i].timestamp_ms,
                                      dres[i].zone, dres[i].risk_score, fres[i].confidence,
                                      fres[i].est_distance_cm, src);
                raw_end_base[i] = frames[i].timestamp_ms;
            }
            run_mode(fp_all, NULL, "LONG_RAW",   seed, n, 0, 0, loads, nloads);
            run_mode(fp_all, NULL, "LONG_COAL",  seed, n, 1, 0, loads, nloads);
            run_mode(fp_all, NULL, "CPU50_1000", seed, n, 0, 1, loads, nloads);
        }
    }

    fclose(fp_all);
    fclose(fp_leg);
    fclose(fp_det);
    return 0;
}
