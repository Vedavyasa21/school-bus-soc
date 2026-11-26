#include "sensor_input.h"

static uint32_t  rng_state       = 2463534242u;
static SceneType cur_scene       = SCENE_IDLE;
static int       scene_left      = 0;
static int       true_dist       = US_MAX_RANGE_CM;
static int       approach_step   = 0;
static int       obstacle_moving = 0;
static uint8_t   door_open       = 0;
static uint8_t   bus_speed       = 0;
static uint32_t  now_ms          = 0;
static uint32_t  next_id         = 0;

uint32_t sensor_rand(void)
{
    uint32_t x = rng_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    rng_state = x;
    return x;
}

uint32_t sensor_rand_range(uint32_t lo, uint32_t hi)
{
    if (hi <= lo) {
        return lo;
    }
    return lo + (sensor_rand() % (hi - lo + 1u));
}

static int rand_i(int lo, int hi)
{
    return (int)sensor_rand_range((uint32_t)lo, (uint32_t)hi);
}

static int clamp_int(int v, int lo, int hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

/* Triangular-ish noise in the range [-amp, +amp] */
static int noise(int amp)
{
    return (rand_i(0, 2 * amp) + rand_i(0, 2 * amp)) / 2 - amp;
}

void sensor_init(uint32_t seed)
{
    int i;
    rng_state = seed ? seed : 2463534242u;
    for (i = 0; i < 8; i++) {
        (void)sensor_rand();
    }
    cur_scene       = SCENE_IDLE;
    scene_left      = 0;
    true_dist       = US_MAX_RANGE_CM;
    approach_step   = 0;
    obstacle_moving = 0;
    door_open       = 0;
    bus_speed       = 0;
    now_ms          = 0;
    next_id         = 0;
}

static void start_new_scene(void)
{
    int r = rand_i(0, 99);

    obstacle_moving = 0;
    approach_step   = 0;

    if (r < 25) {
        cur_scene  = SCENE_IDLE;
        scene_left = rand_i(2, 5);
        true_dist  = US_MAX_RANGE_CM;
        door_open  = 0;
        bus_speed  = (uint8_t)rand_i(0, 35);
    } else if (r < 50) {
        cur_scene     = SCENE_CHILD_APPROACH;
        scene_left    = rand_i(6, 10);
        true_dist     = rand_i(300, 380);
        approach_step = rand_i(25, 50);
        door_open     = (uint8_t)(rand_i(0, 99) < 60);
        bus_speed     = (uint8_t)(door_open ? rand_i(0, 2) : rand_i(0, 8));
    } else if (r < 62) {
        cur_scene  = SCENE_CHILD_CROSSING;
        scene_left = rand_i(5, 8);
        true_dist  = rand_i(160, 260);
        door_open  = 0;
        bus_speed  = (uint8_t)rand_i(4, 15);
    } else if (r < 74) {
        cur_scene  = SCENE_CHILD_STANDING;
        scene_left = rand_i(4, 8);
        true_dist  = rand_i(50, 250);
        door_open  = (uint8_t)(rand_i(0, 99) < 40);
        bus_speed  = (uint8_t)rand_i(0, 3);
    } else if (r < 88) {
        cur_scene       = SCENE_OBSTACLE;
        scene_left      = rand_i(3, 6);
        true_dist       = rand_i(60, 320);
        obstacle_moving = (rand_i(0, 99) < 35);
        door_open       = 0;
        bus_speed       = (uint8_t)rand_i(0, 20);
    } else {
        cur_scene  = SCENE_SENSOR_NOISE;
        scene_left = rand_i(2, 4);
        true_dist  = US_MAX_RANGE_CM;
        door_open  = 0;
        bus_speed  = (uint8_t)rand_i(0, 25);
    }
}

static void generate_one(SensorFrame *f)
{
    int dist = US_MAX_RANGE_CM;
    int prox_dist;
    int motion = 0;
    int truth = 0;
    int us;
    int prox;

    if (scene_left <= 0) {
        start_new_scene();
    }

    switch (cur_scene) {
    case SCENE_IDLE:
        motion = rand_i(0, 12);
        break;
    case SCENE_CHILD_APPROACH:
        true_dist -= approach_step + noise(8);
        if (true_dist < 25) {
            true_dist = rand_i(25, 35);   /* child waits next to the bus */
        }
        dist   = true_dist;
        motion = clamp_int(40 + (US_MAX_RANGE_CM - dist) / 8 + rand_i(0, 15), 0, 100);
        truth  = (true_dist <= 300);
        break;
    case SCENE_CHILD_CROSSING:
        true_dist = clamp_int(true_dist + rand_i(0, 60) - 30, 50, 260);
        dist   = true_dist;
        motion = rand_i(55, 100);
        truth  = 1;
        break;
    case SCENE_CHILD_STANDING:
        dist   = true_dist;
        motion = rand_i(0, 15);                  /* standing or crouching child */
        truth  = 1;
        break;
    case SCENE_OBSTACLE:
        dist   = true_dist + noise(2);
        motion = obstacle_moving ? rand_i(30, 55) : rand_i(0, 10);
        truth  = 0;
        break;
    case SCENE_SENSOR_NOISE:
        motion = rand_i(50, 85);                 /* wind / vibration spike */
        if (rand_i(0, 99) < 35) {
            dist = rand_i(30, 70);               /* spurious ultrasonic echo */
        }
        break;
    default:
        break;
    }

    prox_dist = (cur_scene == SCENE_SENSOR_NOISE) ? US_MAX_RANGE_CM : dist;

    if (dist >= US_MAX_RANGE_CM) {
        us = US_MAX_RANGE_CM;
    } else {
        us = clamp_int(dist + noise(6), 5, US_MAX_RANGE_CM);
    }
    if (rand_i(0, 99) < 3) {
        us = US_INVALID;                          /* sensor dropout */
    }

    if (prox_dist <= PROX_MAX_RANGE_CM) {
        prox = clamp_int(prox_dist + noise(4), 3, PROX_MAX_RANGE_CM);
    } else {
        prox = PROX_MAX_RANGE_CM;
    }

    if (cur_scene == SCENE_CHILD_APPROACH ||
        cur_scene == SCENE_CHILD_CROSSING ||
        cur_scene == SCENE_CHILD_STANDING) {
        now_ms += (uint32_t)rand_i(4, 9);         /* adaptive faster sampling */
    } else {
        now_ms += (uint32_t)rand_i(6, 14);
    }

    f->event_id      = next_id++;
    f->timestamp_ms  = now_ms;
    f->ultrasonic_cm = (uint16_t)us;
    f->proximity_cm  = (uint16_t)prox;
    f->motion_level  = (uint8_t)clamp_int(motion, 0, 100);
    f->bus_speed_kmh = bus_speed;
    f->door_open     = door_open;
    f->child_truth   = (uint8_t)truth;
    f->scene         = cur_scene;

    scene_left--;
}

int sensor_generate_frames(SensorFrame *frames, int count)
{
    int i;
    if (count > MAX_EVENTS) count = MAX_EVENTS;
    if (count < 0) count = 0;
    for (i = 0; i < count; i++) {
        generate_one(&frames[i]);
    }
    return count;
}

const char *sensor_scene_name(SceneType scene)
{
    switch (scene) {
    case SCENE_IDLE:           return "IDLE";
    case SCENE_CHILD_APPROACH: return "APPROACH";
    case SCENE_CHILD_CROSSING: return "CROSSING";
    case SCENE_CHILD_STANDING: return "STANDING";
    case SCENE_OBSTACLE:       return "OBSTACLE";
    case SCENE_SENSOR_NOISE:   return "NOISE";
    default:                   return "UNKNOWN";
    }
}
