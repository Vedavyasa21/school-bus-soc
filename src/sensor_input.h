#ifndef SENSOR_INPUT_H
#define SENSOR_INPUT_H

#include <stdint.h>

#define MAX_EVENTS          1024
#define US_MAX_RANGE_CM     400
#define US_INVALID          0
#define PROX_MAX_RANGE_CM   150

typedef enum {
    SCENE_IDLE = 0,
    SCENE_CHILD_APPROACH,
    SCENE_CHILD_CROSSING,
    SCENE_CHILD_STANDING,
    SCENE_OBSTACLE,
    SCENE_SENSOR_NOISE,
    SCENE_COUNT
} SceneType;

typedef struct {
    uint32_t  event_id;
    uint32_t  timestamp_ms;
    uint16_t  ultrasonic_cm;   /* 0 = invalid/dropout, 400 = no echo        */
    uint16_t  proximity_cm;    /* 150 = nothing inside short range          */
    uint8_t   motion_level;    /* 0..100                                    */
    uint8_t   bus_speed_kmh;
    uint8_t   door_open;
    uint8_t   child_truth;     /* ground truth injected by the simulator    */
    SceneType scene;
} SensorFrame;

void        sensor_init(uint32_t seed);
uint32_t    sensor_rand(void);
uint32_t    sensor_rand_range(uint32_t lo, uint32_t hi);
int         sensor_generate_frames(SensorFrame *frames, int count);
const char *sensor_scene_name(SceneType scene);

#endif /* SENSOR_INPUT_H */
