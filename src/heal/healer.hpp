#pragma once

#include <string>
#include <vector>

#include "core/types.hpp"

namespace boss {

class Healer {
 public:
  ActionResult run(const std::string& action);
  std::vector<ActionResult> run_issue_heals(const std::vector<Issue>& issues);
};

}  // namespace boss
