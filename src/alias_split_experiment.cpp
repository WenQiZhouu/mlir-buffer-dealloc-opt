// Standalone algorithmic experiment, NOT the MLIR compiler pass.
// Based on llvm/llvm-project issue #219740; includes independent alias scenarios.
// Build: g++ -std=c++17 -O2 -Wall -Wextra src/alias_split_experiment.cpp -o build/alias_split
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

struct Operand {
  int64_t allocRoot; // -1 = unknown, may alias any allocation
};

struct SplitResult {
  std::vector<uint8_t> split;
  uint64_t checks = 0;
};

static bool mayAlias(const Operand &a, const Operand &b) {
  return a.allocRoot < 0 || b.allocRoot < 0 || a.allocRoot == b.allocRoot;
}

// Model the original O(N^2) check: copy the other operands for each candidate.
__attribute__((noinline)) static SplitResult baseline(const std::vector<Operand> &operands) {
  SplitResult out;
  out.split.assign(operands.size(), 0);
  for (size_t i = 0; i < operands.size(); ++i) {
    std::vector<Operand> others(operands);
    others.erase(others.begin() + i);
    bool potentiallyAliases = false;
    for (const auto &other : others) {
      ++out.checks;
      if (mayAlias(other, operands[i])) {
        potentiallyAliases = true;
        break;
      }
    }
    out.split[i] = !potentiallyAliases;
  }
  return out;
}

// Fast path: all operand origins are proven local allocations or known views.
// Unknown origins fall back to the baseline (conservative; no invalid splitting).
__attribute__((noinline)) static SplitResult optimized(const std::vector<Operand> &operands) {
  SplitResult out;
  out.split.assign(operands.size(), 0);
  std::map<int64_t, size_t> rootCounts;
  for (const auto &op : operands) {
    if (op.allocRoot < 0)
      return baseline(operands);
    ++rootCounts[op.allocRoot];
  }
  for (size_t i = 0; i < operands.size(); ++i) {
    ++out.checks; // one root-frequency lookup instead of a pairwise alias check
    out.split[i] = rootCounts.at(operands[i].allocRoot) == 1;
  }
  return out;
}

static std::vector<Operand> generate(const std::string &kind, size_t n) {
  std::vector<Operand> operands;
  operands.reserve(n);
  for (size_t i = 0; i < n; ++i) {
    if (kind == "distinct")
      operands.push_back({static_cast<int64_t>(i)});
    else if (kind == "pairs")
      operands.push_back({static_cast<int64_t>(i / 2)});
    else if (kind == "sparse-shared")
      operands.push_back({static_cast<int64_t>((i % 13 == 0 && i > 0) ? i - 1 : i)});
    else if (kind == "unknown")
      operands.push_back({i % 7 == 0 ? -1 : static_cast<int64_t>(i)});
    else
      throw std::invalid_argument("unknown case: " + kind);
  }
  return operands;
}

template <class Fn> static double measureMicros(Fn &&fn, int repeats, uint64_t &sink) {
  std::vector<double> samples;
  samples.reserve(repeats);
  for (int r = 0; r < repeats; ++r) {
    auto start = std::chrono::steady_clock::now();
    SplitResult result = fn();
    auto end = std::chrono::steady_clock::now();
    sink += result.checks + std::accumulate(result.split.begin(), result.split.end(), uint64_t(0));
    samples.push_back(std::chrono::duration<double, std::micro>(end - start).count());
  }
  std::sort(samples.begin(), samples.end());
  return samples[samples.size() / 2];
}

int main(int argc, char **argv) {
  size_t n = argc >= 2 ? std::stoull(argv[1]) : 2048;
  int repeats = argc >= 3 ? std::stoi(argv[2]) : 7;
  if (n < 2 || n > 100000 || repeats < 1 || repeats > 100)
    return 2;
  uint64_t sink = 0;
  for (const std::string kind : {"distinct", "pairs", "sparse-shared", "unknown"}) {
    auto operands = generate(kind, n);
    auto a = baseline(operands);
    auto b = optimized(operands);
    if (a.split != b.split) {
      std::cerr << "ERROR: mismatched split decisions in " << kind << "\n";
      return 1;
    }
    const auto tb = measureMicros([&]() { return baseline(operands); }, repeats, sink);
    const auto to = measureMicros([&]() { return optimized(operands); }, repeats, sink);
    const auto count = std::accumulate(a.split.begin(), a.split.end(), uint64_t(0));
    std::cout << kind << "," << n << "," << std::fixed << std::setprecision(2)
              << tb << "," << to << "," << tb / to << ","
              << a.checks << "," << b.checks << "," << count << "\n";
  }
  if (sink == 0) return 3;
  return 0;
}
