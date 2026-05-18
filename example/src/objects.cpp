#include "cosmos/objects.hpp"

#include <utility>

namespace cosmos::beings {

Mortal::Mortal() = default;

Mortal::Mortal(std::string name, int year_of_birth)
    : name_(std::move(name))
    , year_of_birth_(year_of_birth)
{
}

const std::string& Mortal::name() const
{
    return name_;
}

int Mortal::year_of_birth() const
{
    return year_of_birth_;
}

Mortal::Vocation Mortal::vocation() const
{
    return vocation_;
}

void Mortal::set_vocation(Vocation vocation)
{
    vocation_ = vocation;
}

std::string_view vocation_name(Mortal::Vocation vocation)
{
    switch (vocation) {
        case Mortal::Vocation::farmer:
            return "farmer";
        case Mortal::Vocation::philosopher:
            return "philosopher";
        case Mortal::Vocation::poet:
            return "poet";
        case Mortal::Vocation::hero:
            return "hero";
    }
    return "unknown";
}

Deity::Deity() = default;

Deity::Deity(std::string title, types::Realm realm)
    : title_(std::move(title))
    , realm_(realm)
{
}

const std::string& Deity::title() const
{
    return title_;
}

types::Realm Deity::realm() const
{
    return realm_;
}

Deity::Domain Deity::domain() const
{
    return domain_;
}

void Deity::set_domain(Domain domain)
{
    domain_ = domain;
}

std::string_view domain_name(Deity::Domain domain)
{
    switch (domain) {
        case Deity::Domain::sky:
            return "sky";
        case Deity::Domain::earth:
            return "earth";
        case Deity::Domain::sea:
            return "sea";
        case Deity::Domain::underworld:
            return "underworld";
    }
    return "unknown";
}

std::string Deity::bless(std::string request) const
{
    return title_ + " blesses " + request;
}

Demigod::Demigod()
    : Mortal("young hero", 0)
    , Deity("minor patron", types::Realm::earth)
{
}

Demigod::Demigod(std::string mortal_name, std::string divine_title, int year_of_birth)
    : Mortal(std::move(mortal_name), year_of_birth)
    , Deity(std::move(divine_title), types::Realm::earth)
{
}

int Demigod::quest_count() const
{
    return quest_count_;
}

void Demigod::complete_quest()
{
    ++quest_count_;
}

Oracle::Oracle() = default;

Oracle::Oracle(std::string sanctuary)
    : sanctuary_(std::move(sanctuary))
{
}

const std::string& Oracle::sanctuary() const
{
    return sanctuary_;
}

void Oracle::set_sanctuary(std::string sanctuary)
{
    sanctuary_ = std::move(sanctuary);
}

types::OmenKind Oracle::last_omen() const
{
    return last_omen_;
}

void Oracle::set_last_omen(types::OmenKind omen)
{
    last_omen_ = omen;
}

}  // namespace cosmos::beings
