#include "hardware_driver.h"

#include <cstring>

namespace emitter {

namespace {

constexpr size_t kMaxDrivers = 4;
std::unique_ptr<HardwareDriver> g_drivers[kMaxDrivers];
size_t g_count = 0;

}  // namespace

bool registerDriver(std::unique_ptr<HardwareDriver> d) {
  if (!d) {
    return false;
  }
  const char* id = d->id();
  if (!id || id[0] == '\0') {
    return false;
  }
  if (g_count >= kMaxDrivers) {
    return false;
  }
  for (size_t i = 0; i < g_count; ++i) {
    if (strcmp(g_drivers[i]->id(), id) == 0) {
      return false;
    }
  }
  g_drivers[g_count++] = std::move(d);
  return true;
}

HardwareDriver* getDriver(const char* id) {
  if (!id) {
    return nullptr;
  }
  for (size_t i = 0; i < g_count; ++i) {
    if (strcmp(g_drivers[i]->id(), id) == 0) {
      return g_drivers[i].get();
    }
  }
  return nullptr;
}

}  // namespace emitter
