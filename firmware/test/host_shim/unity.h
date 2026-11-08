// Minimal Unity-compatible shim so the core tests can be built with a plain host
// compiler when PlatformIO is not available: see firmware/test/run_host_tests.sh.
// Only the macros used by test_core are provided.
#pragma once
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int unity_failures = 0;
static int unity_tests = 0;
static int unity_cur_failed = 0;

#define UNITY_FAIL_(msg)                                                    \
  do {                                                                      \
    printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, msg);                  \
    unity_cur_failed = 1;                                                   \
    return;                                                                 \
  } while (0)

#define TEST_ASSERT_TRUE(c) \
  do { if (!(c)) UNITY_FAIL_("expected TRUE: " #c); } while (0)
#define TEST_ASSERT_FALSE(c) \
  do { if (c) UNITY_FAIL_("expected FALSE: " #c); } while (0)
#define UNITY_EQ_(e, a)                                                     \
  do {                                                                      \
    long long e_ = (long long)(e), a_ = (long long)(a);                     \
    if (e_ != a_) {                                                         \
      char b_[160];                                                         \
      snprintf(b_, sizeof b_, "expected %lld got %lld (%s)", e_, a_, #a);   \
      UNITY_FAIL_(b_);                                                      \
    }                                                                       \
  } while (0)
#define TEST_ASSERT_EQUAL_UINT8(e, a) UNITY_EQ_((uint8_t)(e), (uint8_t)(a))
#define TEST_ASSERT_EQUAL_UINT16(e, a) UNITY_EQ_((uint16_t)(e), (uint16_t)(a))
#define TEST_ASSERT_EQUAL_INT16(e, a) UNITY_EQ_((int16_t)(e), (int16_t)(a))
#define TEST_ASSERT_EQUAL_UINT32(e, a) UNITY_EQ_((uint32_t)(e), (uint32_t)(a))
#define TEST_ASSERT_UINT32_WITHIN(d, e, a)                                  \
  do {                                                                      \
    long long df_ = (long long)(a) - (long long)(e);                        \
    if (llabs(df_) > (long long)(d)) UNITY_FAIL_("not within delta: " #a);  \
  } while (0)
#define TEST_ASSERT_FLOAT_WITHIN(d, e, a)                                   \
  do {                                                                      \
    double a_ = (double)(a), e_ = (double)(e);                              \
    if (!(fabs(a_ - e_) <= (double)(d))) {                                  \
      char b_[160];                                                         \
      snprintf(b_, sizeof b_, "expected %f got %f (%s)", e_, a_, #a);       \
      UNITY_FAIL_(b_);                                                      \
    }                                                                       \
  } while (0)
#define TEST_ASSERT_EQUAL_STRING(e, a)                                      \
  do { if (strcmp((e), (a)) != 0) UNITY_FAIL_(a); } while (0)

void setUp();
void tearDown();

#define UNITY_BEGIN() (unity_failures = 0, unity_tests = 0)
#define RUN_TEST(fn)                                                        \
  do {                                                                      \
    unity_cur_failed = 0;                                                   \
    ++unity_tests;                                                          \
    setUp();                                                                \
    fn();                                                                   \
    tearDown();                                                             \
    printf("%s %s\n", unity_cur_failed ? "FAIL" : "PASS", #fn);             \
    unity_failures += unity_cur_failed;                                     \
  } while (0)
#define UNITY_END()                                                         \
  (printf("%d tests, %d failures\n", unity_tests, unity_failures), unity_failures)
