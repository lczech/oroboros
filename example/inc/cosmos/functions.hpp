#pragma once

#include "cosmos/types.hpp"

#include <string>
#include <string_view>

// ================================================================================================
//   cosmos::functions
// ================================================================================================

namespace cosmos::functions {

/** Return a greeting for a mortal visitor. */
std::string greet_pilgrim(std::string_view name);

/** Combine two ritual offering counts. */
int combine_offerings(int grain, int nectar);

/** Build one small relic description from plain inputs. */
types::RelicInfo describe_relic(
    std::string_view name,
    types::Realm realm,
    int power
);

/** Echo one typed value through a small function template. */
template <class T>
T echo_prophecy(T value) {
    return value;
}

/** Wrap one relic in a template-based reliquary. */
types::Reliquary<types::RelicInfo> bless_reliquary(types::RelicInfo relic);

// ================================================================================================
//   cosmos::functions::omens
// ================================================================================================

namespace omens {

/** Classify the severity of one celestial event. */
types::OmenKind classify_comet(int brightness);

/** Return a display name for one omen enum value. */
std::string_view omen_name(types::OmenKind omen);

/** Return a display name for one realm enum value. */
std::string realm_name(types::Realm realm);

}  // namespace omens

}  // namespace cosmos::functions
