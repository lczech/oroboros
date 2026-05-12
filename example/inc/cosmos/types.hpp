#pragma once

#include <cstdint>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

// ================================================================================================
//   cosmos::types
// ================================================================================================

namespace cosmos::types {

/** Severity for the example trace output. */
enum class LogLevel : std::uint8_t {
    quiet = 0,
    info = 1,
    debug = 2,
};

/** Unscoped enum to exercise both enum styles. */
enum StatusCode {
    status_ok = 0,
    status_warning = 1,
    status_error = 2,
};

/** Small struct with public fields for direct field binding tests. */
struct Status {
    StatusCode code {status_ok};
    std::string message {"ready"};
    LogLevel level {LogLevel::info};
};

/** Alias used by a few APIs that return containers. */
using NameList = std::vector<std::string>;

/** Header-only template type that would need explicit binding instantiation. */
template <typename T>
struct Box {
    T value {};

    Box()
    {
        std::cout << "Box::Box()" << '\n';
    }

    explicit Box(T initial)
        : value(std::move(initial))
    {
        std::cout << "Box::Box(T)" << '\n';
    }

    const T& get() const
    {
        std::cout << "Box::get()" << '\n';
        return value;
    }

    void set(T replacement)
    {
        std::cout << "Box::set()" << '\n';
        value = std::move(replacement);
    }
};

/** Header-only template function for template binding experiments. */
template <typename T>
T echo_value(T value)
{
    std::cout << "echo_value(T)" << '\n';
    return value;
}

}  // namespace cosmos::types
