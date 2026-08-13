#pragma once

#include "core/types.hpp"

#include <vector>

namespace boss {

class MonitorEngine {
 public:
  Snapshot snapshot();

 private:
  double sample_cpu(Snapshot& snap);
  void fill_memory(Snapshot& snap);
  void fill_disk(Snapshot& snap);
  void fill_processes(Snapshot& snap);
  void fill_services(Snapshot& snap);
  void derive_issues(Snapshot& snap);
  void fill_cpu_model(Snapshot& snap);

  unsigned long long prev_busy_ = 0;
  unsigned long long prev_total_ = 0;
  bool have_cpu_ = false;
  std::vector<unsigned long long> prev_cpu_busy_;
  std::vector<unsigned long long> prev_cpu_total_;
};

}  // namespace boss
