/* sensitivity.c - Fusion baseline comparisons, threshold ROC sweep, stationary ablation,
 * and 200-draw simultaneous random (+/-20%) weight sensitivity over 100 seeds (4,000 frames).
 */
#include <stdio.h>
#include <math.h>
#include <stdint.h>
#include "sensor_input.h"
#include "sensor_fusion.h"

typedef struct {
    const char *label;
    int w_us, w_pr, w_mo;
    int allow_stationary;
} Config;

static SensorFrame fr[MAX_EVENTS];

static uint32_t mc_rng = 987654321u;
static uint32_t mc_rand(void)
{
    uint32_t x = mc_rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    mc_rng = x;
    return x;
}

static void eval_rule(int mode, int thresh, int w_us, int w_pr, int w_mo, int allow_stat,
                      unsigned *out_tp, unsigned *out_fp, unsigned *out_fp_int,
                      unsigned *out_fn, unsigned *out_tn,
                      unsigned *out_st_tp, unsigned *out_st_fn)
{
    unsigned tp = 0, fp = 0, fp_int = 0, fn = 0, tn = 0, st_tp = 0, st_fn = 0;
    unsigned s;
    int i;

    for (s = 1; s <= 100u; s++) {
        int n;
        sensor_init(s);
        n = sensor_generate_frames(fr, 40);
        for (i = 0; i < n; i++) {
            FusionResult r;
            uint8_t pred = 0;
            fusion_process_weighted(&fr[i], &r, w_us, w_pr, w_mo);
            if (mode == 0) {
                /* Weighted fusion + gating */
                uint8_t both_close = (uint8_t)(fr[i].ultrasonic_cm != US_INVALID &&
                                               fr[i].ultrasonic_cm < US_MAX_RANGE_CM &&
                                               fr[i].proximity_cm < PROX_MAX_RANGE_CM &&
                                               r.est_distance_cm <= FUSION_BOTH_CLOSE_CM);
                pred = (uint8_t)(r.confidence >= (uint8_t)thresh &&
                                 (r.motion_score >= FUSION_MIN_MOTION_SCORE ||
                                  (allow_stat && both_close)));
            } else if (mode == 1) {
                /* Max-of-sensors */
                uint8_t mx = r.us_score;
                if (r.prox_score > mx) mx = r.prox_score;
                if (r.motion_score > mx) mx = r.motion_score;
                pred = (uint8_t)(mx >= (uint8_t)thresh);
            } else if (mode == 2) {
                /* 2-of-3 voting */
                int votes = (r.us_score >= (uint8_t)thresh) +
                            (r.prox_score >= (uint8_t)thresh) +
                            (r.motion_score >= (uint8_t)thresh);
                pred = (uint8_t)(votes >= 2);
            } else if (mode == 3) {
                /* AND-fusion (all 3 >= thresh) */
                pred = (uint8_t)(r.us_score >= (uint8_t)thresh &&
                                 r.prox_score >= (uint8_t)thresh &&
                                 r.motion_score >= (uint8_t)thresh);
            }

            if (pred && fr[i].child_truth) {
                tp++;
            } else if (pred && !fr[i].child_truth) {
                fp++;
                if (fr[i].scene != SCENE_CHILD_APPROACH) {
                    fp_int++;
                }
            } else if (!pred && fr[i].child_truth) {
                fn++;
            } else {
                tn++;
            }

            if (fr[i].scene == SCENE_CHILD_STANDING) {
                if (pred) st_tp++; else st_fn++;
            }
        }
    }
    *out_tp = tp; *out_fp = fp; *out_fp_int = fp_int; *out_fn = fn; *out_tn = tn;
    *out_st_tp = st_tp; *out_st_fn = st_fn;
}

int main(void)
{
    static const Config cfgs[] = {
        { "Baseline (35/25/40, both_close)", 35, 25, 40, 1 },
        { "Legacy motion-only (35/25/40)",   35, 25, 40, 0 },
        { "W_US -20% (28/25/40)",            28, 25, 40, 1 },
        { "W_US +20% (42/25/40)",            42, 25, 40, 1 },
        { "W_PR -20% (35/20/40)",            35, 20, 40, 1 },
        { "W_PR +20% (35/30/40)",            35, 30, 40, 1 },
        { "W_MO -20% (35/25/32)",            35, 25, 32, 1 },
        { "W_MO +20% (35/25/48)",            35, 25, 48, 1 },
    };
    int ncfg = (int)(sizeof(cfgs) / sizeof(cfgs[0]));
    int ci, k;
    FILE *f_roc, *f_mc;
    const char *rule_names[] = { "Weighted+both_close", "Max-of-sensors", "2-of-3 voting", "AND-fusion", "Weighted-motion-only" };
    int threshs[] = { 25, 30, 35, 40, 45, 50, 55, 60, 65 };

    /* 1. Single-parameter sensitivity & ablation -> stdout (results/sensitivity.csv) */
    printf("config,w_us,w_pr,w_mo,both_close,tp,fp,fp_interior,fn,tn,precision,recall,accuracy,f1,standing_tp,standing_fn\n");
    for (ci = 0; ci < ncfg; ci++) {
        const Config *c = &cfgs[ci];
        unsigned tp, fp, fpi, fn, tn, stp, sfn;
        double prec, rec, acc, f1;
        eval_rule(0, FUSION_PRESENT_CONF, c->w_us, c->w_pr, c->w_mo, c->allow_stationary,
                  &tp, &fp, &fpi, &fn, &tn, &stp, &sfn);
        prec = (double)tp / (double)(tp + fp);
        rec  = (double)tp / (double)(tp + fn);
        acc  = (double)(tp + tn) / (double)(tp + fp + fn + tn);
        f1   = (2.0 * prec * rec) / (prec + rec);
        printf("\"%s\",%d,%d,%d,%d,%u,%u,%u,%u,%u,%.4f,%.4f,%.4f,%.4f,%u,%u\n",
               c->label, c->w_us, c->w_pr, c->w_mo, c->allow_stationary,
               tp, fp, fpi, fn, tn, prec, rec, acc, f1, stp, sfn);
    }

    /* 2. Fusion rule baselines & ROC threshold sweep -> results/fusion_roc.csv */
    f_roc = fopen("results/fusion_roc.csv", "w");
    fprintf(f_roc, "rule,threshold,tp,fp,fp_interior,fn,tn,precision,recall,fpr,accuracy,f1,standing_recall\n");
    for (ci = 0; ci < 5; ci++) {
        int mode = (ci == 4) ? 0 : ci;
        int astat = (ci == 4) ? 0 : 1;
        for (k = 0; k < (int)(sizeof(threshs)/sizeof(threshs[0])); k++) {
            unsigned tp, fp, fpi, fn, tn, stp, sfn;
            double prec, rec, fpr, acc, f1, srec;
            eval_rule(mode, threshs[k], 35, 25, 40, astat, &tp, &fp, &fpi, &fn, &tn, &stp, &sfn);
            prec = (tp + fp) ? (double)tp / (double)(tp + fp) : 0.0;
            rec  = (tp + fn) ? (double)tp / (double)(tp + fn) : 0.0;
            fpr  = (fp + tn) ? (double)fp / (double)(fp + tn) : 0.0;
            acc  = (double)(tp + tn) / (double)(tp + fp + fn + tn);
            f1   = (prec + rec > 0.0) ? (2.0 * prec * rec) / (prec + rec) : 0.0;
            srec = (stp + sfn) ? (double)stp / (double)(stp + sfn) : 0.0;
            fprintf(f_roc, "\"%s\",%d,%u,%u,%u,%u,%u,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n",
                    rule_names[ci], threshs[k], tp, fp, fpi, fn, tn, prec, rec, fpr, acc, f1, srec);
        }
    }
    fclose(f_roc);

    /* 3. 200 simultaneous random (+/-20%) weight draws -> results/sensitivity_mc.csv */
    f_mc = fopen("results/sensitivity_mc.csv", "w");
    fprintf(f_mc, "draw,w_us,w_pr,w_mo,tp,fp,fn,tn,precision,recall,accuracy,f1,standing_tp,standing_fn\n");
    for (k = 1; k <= 200; k++) {
        int wu = 28 + (int)(mc_rand() % 15u); /* [28..42] = 35 +/- 20% */
        int wp = 20 + (int)(mc_rand() % 11u); /* [20..30] = 25 +/- 20% */
        int wm = 32 + (int)(mc_rand() % 17u); /* [32..48] = 40 +/- 20% */
        unsigned tp, fp, fpi, fn, tn, stp, sfn;
        double prec, rec, acc, f1;
        eval_rule(0, FUSION_PRESENT_CONF, wu, wp, wm, 1, &tp, &fp, &fpi, &fn, &tn, &stp, &sfn);
        prec = (double)tp / (double)(tp + fp);
        rec  = (double)tp / (double)(tp + fn);
        acc  = (double)(tp + tn) / (double)(tp + fp + fn + tn);
        f1   = (2.0 * prec * rec) / (prec + rec);
        fprintf(f_mc, "%d,%d,%d,%d,%u,%u,%u,%u,%.4f,%.4f,%.4f,%.4f,%u,%u\n",
                k, wu, wp, wm, tp, fp, fn, tn, prec, rec, acc, f1, stp, sfn);
    }
    fclose(f_mc);
    return 0;
}
