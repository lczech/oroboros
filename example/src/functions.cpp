#include "cosmos/functions.hpp"

#include <utility>

namespace cosmos::functions {

std::string greet_pilgrim(std::string_view name)
{
    return "Welcome to the temples, " + std::string(name) + ".";
}

int combine_offerings(int grain, int nectar)
{
    return grain + nectar;
}

types::RelicInfo describe_relic(std::string_view name, types::Realm realm, int power)
{
    return types::RelicInfo {
        .name = std::string(name),
        .realm = realm,
        .power = power,
        .consecrated = power > 50,
    };
}

namespace omens {

types::OmenKind classify_comet(int brightness)
{
    if (brightness < 10) {
        return types::omen_blessing;
    }
    if (brightness < 25) {
        return types::omen_warning;
    }
    return types::omen_catastrophe;
}

std::string_view omen_name(types::OmenKind omen)
{
    switch (omen) {
        case types::omen_blessing:
            return "blessing";
        case types::omen_warning:
            return "warning";
        case types::omen_catastrophe:
            return "catastrophe";
    }
    return "unknown";
}

std::string realm_name(types::Realm realm)
{
    switch (realm) {
        case types::Realm::olympus:
            return "Olympus";
        case types::Realm::earth:
            return "Earth";
        case types::Realm::underworld:
            return "Underworld";
    }
    return "Unknown";
}

}  // namespace omens

}  // namespace cosmos::functions
