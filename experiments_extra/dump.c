/* dump.c - writes per-frame detection data (100 seeds) and per-event latencies for seed 2024. */
#include <stdio.h>
#include <stdlib.h>
#include "sensor_input.h"
#include "sensor_fusion.h"
#include "danger_detection.h"
#include "priority_scheduler.h"

static SensorFrame  fr[MAX_EVENTS];
static FusionResult fu[MAX_EVENTS];
static DangerResult da[MAX_EVENTS];
static SchedEvent   ev[MAX_EVENTS], sv[MAX_EVENTS];
static SchedStats   st;

int main(int argc, char **argv)
{
    FILE *f1, *f2;
    unsigned s;
    int i, p = 0, n = 40;
    static int lat[6][MAX_EVENTS];
    unsigned loads[2] = { 100, 400 };
    int li;

    if (argc < 3) return 1;
    f1 = fopen(argv[1], "w");
    f2 = fopen(argv[2], "w");
    fprintf(f1, "seed,id,scene,truth,present,conf,dist,us,pr,mo,zone,risk\n");
    fprintf(f2, "id,scene,us,pr,mo,conf,det,tru,dist,zone,risk,fifo100,fixed100,sa100,fifo400,fixed400,sa400\n");

    for (s = 1; s <= 101; s++) {
        unsigned seed = (s == 101) ? 2024u : s;
        sensor_init(seed);
        n = sensor_generate_frames(fr, 40);
        for (i = 0; i < n; i++) {
            SourceTask src;
            fusion_process(&fr[i], &fu[i]);
            danger_classify(&fr[i], &fu[i], &da[i]);
            src = scheduler_source_from_scores(fu[i].us_score, fu[i].prox_score, fu[i].motion_score);
            scheduler_build_event(&ev[i], fr[i].event_id, fr[i].timestamp_ms,
                                  da[i].zone, da[i].risk_score, fu[i].confidence,
                                  fu[i].est_distance_cm, src);
            if (seed != 2024u) {
                fprintf(f1, "%u,%d,%s,%d,%d,%d,%d,%d,%d,%d,%s,%d\n",
                        seed, i, sensor_scene_name(fr[i].scene),
                        fr[i].child_truth, fu[i].child_present, fu[i].confidence,
                        fu[i].est_distance_cm, fr[i].ultrasonic_cm, fr[i].proximity_cm,
                        fr[i].motion_level, danger_zone_name(da[i].zone), da[i].risk_score);
            }
        }
        if (seed == 2024u) {
            for (li = 0; li < 2; li++) {
                SchedEvent sc[MAX_EVENTS];
                for (i = 0; i < n; i++) {
                    sc[i] = ev[i];
                    sc[i].arrival_ms = (uint32_t)(((uint64_t)ev[i].arrival_ms * 100u) / loads[li]);
                }
                for (p = 0; p < 3; p++) {
                    scheduler_run((SchedPolicy)p, sc, n, sv, &st);
                    for (i = 0; i < n; i++) {
                        lat[li * 3 + p][sv[i].event_id] = (int)(sv[i].finish_ms - sv[i].arrival_ms);
                    }
                }
            }
            for (i = 0; i < n; i++) {
                fprintf(f2, "%d,%s,%d,%d,%d,%d,%s,%s,%d,%s,%d,%d,%d,%d,%d,%d,%d\n",
                        i, sensor_scene_name(fr[i].scene),
                        fr[i].ultrasonic_cm, fr[i].proximity_cm, fr[i].motion_level,
                        fu[i].confidence,
                        fu[i].child_present ? "YES" : "no",
                        fr[i].child_truth ? "YES" : "no",
                        fu[i].est_distance_cm, danger_zone_name(da[i].zone), da[i].risk_score,
                        lat[0][i], lat[1][i], lat[2][i], lat[3][i], lat[4][i], lat[5][i]);
            }
        }
    }
    fclose(f1);
    fclose(f2);
    (void)p;
    return 0;
}
