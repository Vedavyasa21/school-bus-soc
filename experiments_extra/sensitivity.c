/* sensitivity.c - Fusion weight (+/-20%) and standing-child rule ablation over 100 seeds. */
#include <stdio.h>
#include "sensor_input.h"
#include "sensor_fusion.h"

typedef struct {
    const char *label;
    int w_us, w_pr, w_mo;
    int allow_stationary;
} Config;

static SensorFrame fr[MAX_EVENTS];

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
    int ci, i;
    unsigned s;

    printf("config,w_us,w_pr,w_mo,both_close,tp,fp,fn,tn,precision,recall,accuracy,f1,standing_tp,standing_fn\n");
    for (ci = 0; ci < ncfg; ci++) {
        const Config *c = &cfgs[ci];
        unsigned tp = 0, fp = 0, fn = 0, tn = 0;
        unsigned st_tp = 0, st_fn = 0;

        for (s = 1; s <= 100u; s++) {
            int n;
            sensor_init(s);
            n = sensor_generate_frames(fr, 40);
            for (i = 0; i < n; i++) {
                FusionResult r;
                uint8_t pred;
                fusion_process_weighted(&fr[i], &r, c->w_us, c->w_pr, c->w_mo);
                if (c->allow_stationary) {
                    pred = r.child_present;
                } else {
                    pred = (uint8_t)((r.confidence >= FUSION_PRESENT_CONF) &&
                                     (r.motion_score >= FUSION_MIN_MOTION_SCORE));
                }
                if (pred && fr[i].child_truth)        tp++;
                else if (pred && !fr[i].child_truth)  fp++;
                else if (!pred && fr[i].child_truth)  fn++;
                else                                  tn++;

                if (fr[i].scene == SCENE_CHILD_STANDING) {
                    if (pred) st_tp++; else st_fn++;
                }
            }
        }
        {
            double prec = (tp + fp) ? (double)tp / (double)(tp + fp) : 0.0;
            double rec  = (tp + fn) ? (double)tp / (double)(tp + fn) : 0.0;
            double acc  = (double)(tp + tn) / (double)(tp + fp + fn + tn);
            double f1   = (prec + rec > 0.0) ? (2.0 * prec * rec) / (prec + rec) : 0.0;
            printf("\"%s\",%d,%d,%d,%d,%u,%u,%u,%u,%.4f,%.4f,%.4f,%.4f,%u,%u\n",
                   c->label, c->w_us, c->w_pr, c->w_mo, c->allow_stationary,
                   tp, fp, fn, tn, prec, rec, acc, f1, st_tp, st_fn);
        }
    }
    return 0;
}
