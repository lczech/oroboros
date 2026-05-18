#include "cosmos/cosmos.hpp"

#include <iostream>

int main()
{
    using namespace cosmos::beings;
    using namespace cosmos::beings;
    using namespace cosmos::functions;
    using namespace cosmos::functions::omens;
    using namespace cosmos::types;

    std::cout << "A small tale from the cosmos example library\n";
    std::cout << "============================================\n";
    std::cout << "A pilgrim arrives at the temple.\n";
    std::cout << "  Greeting: " << greet_pilgrim("Ariadne") << '\n';
    std::cout << "  Offerings counted: 3 baskets of grain + 4 cups of nectar = "
              << combine_offerings(3, 4) << " total offerings\n";

    const auto relic = describe_relic("Aegis", Realm::olympus, 90);
    std::cout << "A relic is presented for inspection.\n";
    std::cout << "  Relic name: " << relic.name << '\n';
    std::cout << "  Realm of origin: " << realm_name(relic.realm) << '\n';
    std::cout << "  Power rating: " << relic.power << '\n';
    std::cout << "  Consecrated: " << (relic.consecrated ? "yes" : "no") << '\n';

    Mortal mortal("Odysseus", -1200);
    mortal.set_vocation(Mortal::Vocation::philosopher);
    std::cout << "A mortal introduces himself.\n";
    std::cout << "  Name: " << mortal.name() << '\n';
    std::cout << "  Year of birth: " << mortal.year_of_birth() << '\n';
    std::cout << "  Vocation: " << vocation_name(mortal.vocation()) << '\n';

    Deity deity("Athena", Realm::olympus);
    deity.set_domain(Deity::Domain::earth);
    std::cout << "A deity answers the prayer.\n";
    std::cout << "  Title: " << deity.title() << '\n';
    std::cout << "  Realm: " << realm_name(deity.realm()) << '\n';
    std::cout << "  Domain: " << domain_name(deity.domain()) << '\n';
    std::cout << "  Blessing: " << deity.bless("the voyage") << '\n';

    Demigod demigod("Heracles", "Zeus", -1250);
    demigod.complete_quest();
    demigod.complete_quest();
    std::cout << "A demigod steps forward.\n";
    std::cout << "  Mortal name: " << demigod.name() << '\n';
    std::cout << "  Divine title: " << demigod.title() << '\n';
    std::cout << "  Completed quests: " << demigod.quest_count() << '\n';

    Oracle oracle("Delphi");
    oracle.set_last_omen(classify_comet(30));
    std::cout << "At last, the oracle speaks.\n";
    std::cout << "  Sanctuary: " << oracle.sanctuary() << '\n';
    std::cout << "  Omen after observing a comet of brightness 30: "
              << omen_name(oracle.last_omen()) << '\n';

    return 0;
}
