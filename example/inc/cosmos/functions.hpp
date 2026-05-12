#pragma once

#include "cosmos/types.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

// ================================================================================================
//   cosmos::functions
// ================================================================================================

namespace cosmos::functions {

/** Return a greeting string. */
std::string greet(std::string_view name);

/** Add two integers. */
int add(int lhs, int rhs);

/** Add two doubles. */
double add(double lhs, double rhs);

/** Build a small status object. */
types::Status make_status(
    std::string_view message,
    types::StatusCode code = types::status_ok,
    types::LogLevel level = types::LogLevel::info
);

/** Create a list of names with a numbered suffix. */
types::NameList make_name_list(std::string_view prefix, int count);

/** Return one name when the requested index exists. */
std::optional<std::string> maybe_pick_name(const types::NameList& names, std::size_t index);

// ================================================================================================
//   cosmos::functions::math
// ================================================================================================

namespace math {

/** Compute a vector magnitude. */
double magnitude(double x, double y);

/** Normalize a pair of values into a unit vector when possible. */
std::vector<double> normalize_pair(double x, double y);

/** Header-only template algorithm for explicit template binding tests. */
template <typename T>
T square(T value)
{
    std::cout << "math::square(T)" << '\n';
    return value * value;
}

}  // namespace math

}  // namespace cosmos::functions
