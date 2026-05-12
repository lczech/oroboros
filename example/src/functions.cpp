#include "cosmos/functions.hpp"

#include <cmath>
#include <iostream>

// ================================================================================================
//   cosmos::functions
// ================================================================================================

namespace cosmos::functions {

std::string greet(std::string_view name)
{
    std::cout << "greet()" << "\n";
    return std::string("Hello, ") + std::string(name) + "!";
}

int add(int lhs, int rhs)
{
    std::cout << "add(int, int)" << "\n";
    return lhs + rhs;
}

double add(double lhs, double rhs)
{
    std::cout << "add(double, double)" << "\n";
    return lhs + rhs;
}

types::Status make_status(std::string_view message, types::StatusCode code, types::LogLevel level)
{
    std::cout << "make_status()" << "\n";
    return types::Status {
        .code = code,
        .message = std::string(message),
        .level = level,
    };
}

types::NameList make_name_list(std::string_view prefix, int count)
{
    std::cout << "make_name_list()" << "\n";

    types::NameList names;
    for (int index = 0; index < count; ++index) {
        names.push_back(std::string(prefix) + "_" + std::to_string(index));
    }
    return names;
}

std::optional<std::string> maybe_pick_name(const types::NameList& names, std::size_t index)
{
    std::cout << "maybe_pick_name()" << "\n";
    if (index >= names.size()) {
        return std::nullopt;
    }
    return names[index];
}

// ================================================================================================
//   cosmos::functions::math
// ================================================================================================

namespace math {

double magnitude(double x, double y)
{
    std::cout << "math::magnitude()" << "\n";
    return std::sqrt((x * x) + (y * y));
}

std::vector<double> normalize_pair(double x, double y)
{
    std::cout << "math::normalize_pair()" << "\n";

    const double size = magnitude(x, y);
    if (size == 0.0) {
        return {0.0, 0.0};
    }
    return {x / size, y / size};
}

}  // namespace math

}  // namespace cosmos::functions
