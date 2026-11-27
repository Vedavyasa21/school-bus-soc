#ifndef DANGER_DETECTION_H
#define DANGER_DETECTION_H

#include <stdint.h>
#include "sensor_input.h"
#include "sensor_fusion.h"

#define CRITICAL_BASE_CM   100
#define CRITICAL_DOOR_CM   150
#define WARNING_ZONE_CM    300

typedef enum {
    ZONE_SAFE = 0,
    ZONE_WARNING = 1,
    ZONE_CRITICAL = 2
} ZoneLevel;

typedef struct {
    ZoneLevel zone;
    uint8_t   risk_score;   /* 0..100 */
} DangerResult;

void        danger_classify(const SensorFrame *frame, const FusionResult *fusion,
                            DangerResult *result);
const char *danger_zone_name(ZoneLevel zone);

#endif /* DANGER_DETECTION_H */
