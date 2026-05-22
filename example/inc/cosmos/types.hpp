#pragma once

#include <array>
#include <cstdint>
#include <string>

// ================================================================================================
//   cosmos::types
// ================================================================================================

namespace cosmos::types {

/** Broad mythological realms used across the example library. */
enum class Realm : std::uint8_t {
    olympus = 0,
    earth = 1,
    underworld = 2,
};

/** Unscoped omen categories for parser-side enum coverage. */
enum OmenKind {
    omen_blessing = 0,
    omen_warning = 1,
    omen_catastrophe = 2,
};

/** Small public struct used for enum, member-variable, and parameter coverage. */
struct RelicInfo {
    std::string name {"unnamed"};
    Realm realm {Realm::earth};
    int power {0};
    bool consecrated {false};
};

/** Small generic wrapper used to exercise class template parsing in the example library. */
template <class T>
struct Reliquary {
    T value {};
};

/** Alias used to exercise nested template arguments with one non-type value. */
using RelicQuartet = std::array<RelicInfo, 4>;

/** Alias used to exercise a nested template alias target in parsed C++ types. */
using ReliquaryShelf = Reliquary<RelicQuartet>;

/** Alias used to exercise namespace-level alias declarations in the example library. */
using RealmCode = Realm;

}  // namespace cosmos::types
