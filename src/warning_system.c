#include <stdio.h>
#include <string.h>
#include "warning_system.h"

static ProcessingRecord log_buf[MAX_EVENTS];
static int      log_count = 0;
static uint32_t level_count[3];
static uint32_t v2v_count;
static uint32_t deadlines_met;
static uint32_t deadlines_missed;
static uint32_t latency_sum;

void warning_generate(uint32_t event_id, ZoneLevel zone, uint8_t risk,
                      uint8_t confidence, uint16_t distance_cm, WarningMessage *out)
{
    memset(out, 0, sizeof(*out));
    out->event_id = event_id;
    out->zone     = zone;

    switch (zone) {
    case ZONE_CRITICAL:
        out->alert_level   = 2;
        out->v2v_broadcast = 1;
        snprintf(out->driver_msg, WARN_MSG_LEN,
                 "[DANGER] STOP! Child in critical zone at %u cm (conf %u%%, risk %u). Do not move the bus!",
                 (unsigned)distance_cm, (unsigned)confidence, (unsigned)risk);
        snprintf(out->vehicle_msg, WARN_MSG_LEN,
                 "[V2V-EMERGENCY] School bus: CHILD ON ROADWAY. STOP IMMEDIATELY. Event %u.",
                 (unsigned)event_id);
        break;
    case ZONE_WARNING:
        out->alert_level   = 1;
        out->v2v_broadcast = 1;
        snprintf(out->driver_msg, WARN_MSG_LEN,
                 "[CAUTION] Child detected %u cm from bus (conf %u%%, risk %u). Reduce speed, prepare to stop.",
                 (unsigned)distance_cm, (unsigned)confidence, (unsigned)risk);
        snprintf(out->vehicle_msg, WARN_MSG_LEN,
                 "[V2V-WARNING] School bus ahead: children near roadway. Slow down, keep distance.");
        break;
    default:
        out->alert_level   = 0;
        out->v2v_broadcast = 0;
        snprintf(out->driver_msg, WARN_MSG_LEN,
                 "[INFO] Zone clear (risk %u). Monitoring continues.", (unsigned)risk);
        out->vehicle_msg[0] = '\0';
        break;
    }
}

void warning_print(const WarningMessage *msg, uint32_t dispatch_time_ms)
{
    printf("  t=%4u ms  EVT %-3u %s\n", (unsigned)dispatch_time_ms,
           (unsigned)msg->event_id, msg->driver_msg);
    if (msg->v2v_broadcast) {
        printf("             EVT %-3u %s\n", (unsigned)msg->event_id, msg->vehicle_msg);
    }
}

void warning_log_reset(void)
{
    memset(log_buf, 0, sizeof(log_buf));
    memset(level_count, 0, sizeof(level_count));
    log_count        = 0;
    v2v_count        = 0;
    deadlines_met    = 0;
    deadlines_missed = 0;
    latency_sum      = 0;
}

void warning_log_record(SchedPolicy policy, const SchedEvent *ev, const WarningMessage *msg)
{
    ProcessingRecord *rec;

    if (log_count >= MAX_EVENTS) {
        return;
    }
    rec = &log_buf[log_count++];
    rec->event_id     = ev->event_id;
    rec->policy       = policy;
    rec->zone         = ev->zone;
    rec->arrival_ms   = ev->arrival_ms;
    rec->start_ms     = ev->start_ms;
    rec->finish_ms    = ev->finish_ms;
    rec->latency_ms   = ev->finish_ms - ev->arrival_ms;
    rec->deadline_met = (uint8_t)scheduler_deadline_met(ev);
    rec->alert_level  = msg->alert_level;

    level_count[msg->alert_level > 2 ? 2 : msg->alert_level]++;
    if (msg->v2v_broadcast) {
        v2v_count++;
    }
    if (rec->deadline_met) {
        deadlines_met++;
    } else {
        deadlines_missed++;
    }
    latency_sum += rec->latency_ms;
}

int warning_log_count(void)
{
    return log_count;
}

void warning_log_print_summary(SchedPolicy policy)
{
    double avg = log_count ? (double)latency_sum / (double)log_count : 0.0;

    printf("[LOG %s] records=%d | driver alerts: info=%u caution=%u danger=%u | "
           "V2V broadcasts=%u | deadlines met=%u missed=%u | avg latency=%.2f ms\n",
           scheduler_policy_name(policy), log_count,
           (unsigned)level_count[0], (unsigned)level_count[1], (unsigned)level_count[2],
           (unsigned)v2v_count, (unsigned)deadlines_met, (unsigned)deadlines_missed, avg);
}
