#pragma once

#include <string>
#include <vector>

#include "core/types.hpp"

namespace boss {

struct OptimizeReport {
  std::vector<ActionResult> results;
  std::string summary_text() const;
};

class Optimizer {
 public:
  OptimizeReport run_all();
};

}  // namespace boss
