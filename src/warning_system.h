#ifndef WARNING_SYSTEM_H
#define WARNING_SYSTEM_H

#include <stdint.h>
#include "danger_detection.h"
#include "priority_scheduler.h"

#define WARN_MSG_LEN 128

typedef struct {
    uint32_t  event_id;
    ZoneLevel zone;
    uint8_t   alert_level;      /* 0 = info, 1 = caution, 2 = danger */
    uint8_t   v2v_broadcast;
    char      driver_msg[WARN_MSG_LEN];
    char      vehicle_msg[WARN_MSG_LEN];
} WarningMessage;

typedef struct {
    uint32_t    event_id;
    SchedPolicy policy;
    ZoneLevel   zone;
    uint32_t    arrival_ms;
    uint32_t    start_ms;
    uint32_t    finish_ms;
    uint32_t    latency_ms;
    uint8_t     deadline_met;
    uint8_t     alert_level;
} ProcessingRecord;

void warning_generate(uint32_t event_id, ZoneLevel zone, uint8_t risk,
                      uint8_t confidence, uint16_t distance_cm, WarningMessage *out);
void warning_print(const WarningMessage *msg, uint32_t dispatch_time_ms);
void warning_log_reset(void);
void warning_log_record(SchedPolicy policy, const SchedEvent *ev, const WarningMessage *msg);
int  warning_log_count(void);
void warning_log_print_summary(SchedPolicy policy);

#endif /* WARNING_SYSTEM_H */
