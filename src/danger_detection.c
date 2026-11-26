#include "danger_detection.h"

static int clamp_int(int v, int lo, int hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

void danger_classify(const SensorFrame *f, const FusionResult *r, DangerResult *d)
{
    int dist = (int)r->est_distance_cm;
    int risk;
    int speed;
    int v_cms;
    int d_stop_cm;
    int crit_cm;

    if (!r->child_present) {
        d->zone       = ZONE_SAFE;
        d->risk_score = (uint8_t)clamp_int((int)r->confidence / 4, 0, 34);
        return;
    }

    risk = ((US_MAX_RANGE_CM - dist) * 60) / US_MAX_RANGE_CM;
    if (risk < 0) risk = 0;
    risk += (int)r->confidence / 5;
    if (f->door_open) {
        risk += 10;
    }
    speed = (f->bus_speed_kmh > 20) ? 20 : (int)f->bus_speed_kmh;
    risk += speed / 2;

    /* Stopping-distance critical bound: tau = 0.4 s reaction + a = 5.0 m/s^2 braking */
    v_cms     = ((int)f->bus_speed_kmh * 1000) / 36;
    d_stop_cm = (v_cms * 4) / 10 + (v_cms * v_cms) / 100000;
    crit_cm   = CRITICAL_BASE_CM;
    if (f->door_open || f->bus_speed_kmh > 0) {
        crit_cm = CRITICAL_BASE_CM + d_stop_cm;
        if (crit_cm < CRITICAL_DOOR_CM) crit_cm = CRITICAL_DOOR_CM;
        if (crit_cm > CRITICAL_MAX_CM)  crit_cm = CRITICAL_MAX_CM;
    }

    if (dist <= crit_cm) {
        d->zone       = ZONE_CRITICAL;
        d->risk_score = (uint8_t)clamp_int(risk, 70, 100);
    } else if (dist <= WARNING_ZONE_CM) {
        d->zone       = ZONE_WARNING;
        d->risk_score = (uint8_t)clamp_int(risk, 35, 69);
    } else {
        d->zone       = ZONE_SAFE;
        d->risk_score = (uint8_t)clamp_int(risk, 0, 34);
    }
}

const char *danger_zone_name(ZoneLevel zone)
{
    switch (zone) {
    case ZONE_SAFE:     return "SAFE";
    case ZONE_WARNING:  return "WARNING";
    case ZONE_CRITICAL: return "CRITICAL";
    default:            return "UNKNOWN";
    }
}
