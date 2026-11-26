#include "sensor_fusion.h"

static uint8_t clamp_u8(int v)
{
    if (v < 0)   return 0;
    if (v > 100) return 100;
    return (uint8_t)v;
}

void fusion_process_weighted(const SensorFrame *f, FusionResult *r,
                             int w_us, int w_pr, int w_mo)
{
    int us    = (int)f->ultrasonic_cm;
    int pr    = (int)f->proximity_cm;
    int mo    = (int)f->motion_level;
    int us_valid  = (us != US_INVALID);
    int us_echo   = us_valid && (us <= FUSION_US_DETECT_CM);
    int prox_echo = (pr < PROX_MAX_RANGE_CM);
    int us_s = 0, pr_s = 0, mo_s = 0;
    int w_sum = w_us + w_pr + w_mo;
    int conf;
    int dist;
    int both_close;

    if (us_echo) {
        us_s = 50 + ((FUSION_US_DETECT_CM - us) * 50) / (FUSION_US_DETECT_CM - 5);
    }
    if (prox_echo) {
        pr_s = 60 + ((PROX_MAX_RANGE_CM - pr) * 40) / (PROX_MAX_RANGE_CM - 3);
    }
    if (mo > FUSION_MOTION_FLOOR) {
        mo_s = ((mo - FUSION_MOTION_FLOOR) * 100) / (100 - FUSION_MOTION_FLOOR);
    }

    us_s = clamp_u8(us_s);
    pr_s = clamp_u8(pr_s);
    mo_s = clamp_u8(mo_s);

    /* Weighted fusion (default: ultrasonic 35%, proximity 25%, motion 40%) */
    if (w_sum <= 0) w_sum = 100;
    conf = (us_s * w_us + pr_s * w_pr + mo_s * w_mo) / w_sum;

    /* Cross-validation penalties for inconsistent sensors */
    if (us_echo && us < 100 && !prox_echo) {
        conf -= 20;
    }
    if (prox_echo && us_valid && !us_echo) {
        conf -= 10;
    }

    /* Distance estimate */
    if (us_echo && prox_echo) {
        dist = (us * 40 + pr * 60) / 100;
    } else if (prox_echo) {
        dist = pr;
    } else if (us_echo) {
        dist = us;
    } else {
        dist = US_MAX_RANGE_CM;
    }

    /* Confirm stationary/crouching child when both short-range sensors agree closely */
    both_close = us_echo && prox_echo && (dist <= FUSION_BOTH_CLOSE_CM);

    r->us_score        = (uint8_t)us_s;
    r->prox_score      = (uint8_t)pr_s;
    r->motion_score    = (uint8_t)mo_s;
    r->confidence      = clamp_u8(conf);
    r->est_distance_cm = (uint16_t)dist;
    r->child_present   = (uint8_t)((r->confidence >= FUSION_PRESENT_CONF) &&
                                   (mo_s >= FUSION_MIN_MOTION_SCORE || both_close));
}

void fusion_process(const SensorFrame *f, FusionResult *r)
{
    fusion_process_weighted(f, r, FUSION_WEIGHT_US, FUSION_WEIGHT_PR, FUSION_WEIGHT_MO);
}
