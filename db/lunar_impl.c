/*
 * lunar_impl.c — Lunar eclipse implementation translation unit.
 *
 * Compile with solar_impl.c and test_saros_lib.c (or your own main).
 * Optionally define SAROS_USE_ALL to use the full Saros 1-180 dataset.
 * Optionally define ECLIPSE_USE_PROGMEM on AVR/ESP32.
 */

#define SAROS_IMPL_LUNAR
/* #define SAROS_USE_ALL */

#include "lunar/eclipse_times_modern.h"
#include "lunar/eclipse_info_modern.h"
#include "lunar/saros_modern.h"
#include "saros.h"
