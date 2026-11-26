#ifndef SENSOR_FUSION_H
#define SENSOR_FUSION_H

#include <stdint.h>
#include "sensor_input.h"

#define FUSION_US_DETECT_CM     350
#define FUSION_MOTION_FLOOR     20
#define FUSION_PRESENT_CONF     40
#define FUSION_MIN_MOTION_SCORE 20
#define FUSION_BOTH_CLOSE_CM    200

#ifndef FUSION_WEIGHT_US
#define FUSION_WEIGHT_US        35
#endif
#ifndef FUSION_WEIGHT_PR
#define FUSION_WEIGHT_PR        25
#endif
#ifndef FUSION_WEIGHT_MO
#define FUSION_WEIGHT_MO        40
#endif

typedef struct {
    uint8_t  us_score;         /* 0..100 */
    uint8_t  prox_score;       /* 0..100 */
    uint8_t  motion_score;     /* 0..100 */
    uint8_t  confidence;       /* 0..100 */
    uint8_t  child_present;
    uint16_t est_distance_cm;
} FusionResult;

void fusion_process(const SensorFrame *frame, FusionResult *result);
void fusion_process_weighted(const SensorFrame *frame, FusionResult *result,
                             int w_us, int w_pr, int w_mo);

#endif /* SENSOR_FUSION_H */
