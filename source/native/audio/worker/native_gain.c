/* Local native experiment, GPL-3.0-or-later. */
#include "native_gain.h"

void native_gain_table(signed char table[256], unsigned short gain) {
 unsigned int i, magnitude, limit;
 int sample;
 unsigned long amplified;
 if (gain < 1 || gain > 8) gain = 4;
 for (i = 0; i < 256; ++i) {
  sample = (int)i - 128;
  magnitude = sample < 0 ? (unsigned int)-sample : (unsigned int)sample;
  limit = sample < 0 ? 128 : 127;
  /* Smooth limiting increases quiet speech without flat-topping its peaks. */
  amplified = (unsigned long)magnitude * gain * limit /
              (limit + (unsigned long)(gain - 1) * magnitude);
  table[i] = (signed char)(sample < 0 ? -(int)amplified : (int)amplified);
 }
}
