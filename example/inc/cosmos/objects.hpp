#pragma once

#include "cosmos/types.hpp"

#include <string>
#include <string_view>

// ================================================================================================
//   cosmos::beings
// ================================================================================================

namespace cosmos::beings {

/** A mortal with a vocation and a year of birth. */
class Mortal {
public:
    /** The public set of mortal vocations used by the example parser. */
    enum class Vocation {
        farmer,
        philosopher,
        poet,
        hero,
    };

    Mortal();
    Mortal(std::string name, int year_of_birth);

    const std::string& name() const;
    int year_of_birth() const;
    Vocation vocation() const;
    void set_vocation(Vocation vocation);

private:
    std::string name_ {"unknown mortal"};
    int year_of_birth_ {0};
    Vocation vocation_ {Vocation::farmer};
};

/** Return a display name for one mortal vocation value. */
std::string_view vocation_name(Mortal::Vocation vocation);

/** A deity tied to one realm and one sphere of influence. */
class Deity {
public:
    enum class Domain {
        sky,
        earth,
        sea,
        underworld,
    };

    Deity();
    Deity(std::string title, types::Realm realm);

    const std::string& title() const;
    types::Realm realm() const;
    Domain domain() const;
    void set_domain(Domain domain);
    std::string bless(std::string request) const;

protected:
    std::string title_ {"nameless deity"};
    types::Realm realm_ {types::Realm::olympus};
    Domain domain_ {Domain::sky};
};

/** Return a display name for one deity domain value. */
std::string_view domain_name(Deity::Domain domain);

/** A half-god exercises multiple inheritance between mortals and deities. */
class Demigod : public Mortal, public Deity {
public:
    Demigod();
    Demigod(std::string mortal_name, std::string divine_title, int year_of_birth);

    int quest_count() const;
    void complete_quest();

private:
    int quest_count_ {0};
};

/** An oracle with a sanctuary and one remembered omen. */
class Oracle {
public:
    /** Alias used to exercise class-scoped alias declarations in the example library. */
    using SanctuaryName = std::string;

    Oracle();
    explicit Oracle(std::string sanctuary);

    /**
     * @brief Return the sanctuary name.
     *
     * Example usage:
     *
     *     oracle.sanctuary();
     */
    const std::string& sanctuary() const;
    void set_sanctuary(std::string sanctuary);
    types::OmenKind last_omen() const;
    void set_last_omen(types::OmenKind omen);

private:
    std::string sanctuary_ {"Delphi"};           ///< Remembered sanctuary name.
    types::OmenKind last_omen_ {types::omen_blessing};  ///< Most recent omen.
};

}  // namespace cosmos::beings
