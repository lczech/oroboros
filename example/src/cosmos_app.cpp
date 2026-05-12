#include "cosmos/cosmos.hpp"

#include <iostream>
#include <memory>

// ================================================================================================
//   cosmos example app
// ================================================================================================

int main()
{
    using namespace cosmos::functions;
    using namespace cosmos::objects;
    using namespace cosmos::types;

    std::cout << greet("cosmos bindings example") << '\n';
    std::cout << add(2, 3) << '\n';
    std::cout << add(1.5, 2.5) << '\n';

    const auto status = make_status("running", status_warning, LogLevel::debug);
    std::cout << status.message << '\n';

    const auto names = make_name_list("node", 3);
    if (const auto chosen = maybe_pick_name(names, 1)) {
        std::cout << *chosen << '\n';
    }

    const auto normalized = math::normalize_pair(3.0, 4.0);
    std::cout << normalized[0] << ", " << normalized[1] << '\n';

    Box<int> box(7);
    box.set(echo_value(8));
    std::cout << box.get() << '\n';
    std::cout << math::square(6) << '\n';

    Device device = Device::make_default();
    device.set_state(Device::State::running);
    std::cout << device.kind() << '\n';

    auto sensor = std::dynamic_pointer_cast<Sensor>(make_sensor("temperature", 21.5));
    if (sensor) {
        sensor->set_reading(22.0);
        std::cout << sensor->kind() << '\n';
    }

    Vector2 a(1.0, 2.0);
    Vector2 b(3.0, 4.0);
    Vector2 c = a + b;
    c.translate(1.0, -1.0);
    std::cout << c.length() << '\n';

    Registry registry;
    registry.add(std::make_shared<Device>(device));
    registry.add(make_sensor("pressure", 2.0));
    std::cout << registry.size() << '\n';
    for (const auto& name : registry.names()) {
        std::cout << name << '\n';
    }

    return 0;
}
