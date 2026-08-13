#pragma once

#include "core/types.hpp"

namespace boss {

class MonitorEngine {
 public:
  Snapshot snapshot();

 private:
  double sample_cpu();
  void fill_memory(Snapshot& snap);
  void fill_disk(Snapshot& snap);
  void fill_processes(Snapshot& snap);
  void fill_services(Snapshot& snap);
  void derive_issues(Snapshot& snap);

  unsigned long long prev_busy_ = 0;
  unsigned long long prev_total_ = 0;
  bool have_cpu_ = false;
};

}  // namespace boss
