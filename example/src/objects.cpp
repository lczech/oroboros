#include "cosmos/objects.hpp"

#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <utility>

// ================================================================================================
//   cosmos::objects
// ================================================================================================

namespace cosmos::objects {

// -----------------------------------------------------------------------------
//   classe inheritance
// -----------------------------------------------------------------------------

NamedEntity::NamedEntity()
    : name_("unnamed")
{
    std::cout << "NamedEntity::NamedEntity()" << "\n";
}

NamedEntity::NamedEntity(std::string name)
    : name_(std::move(name))
{
    std::cout << "NamedEntity::NamedEntity(std::string)" << "\n";
}

NamedEntity::~NamedEntity()
{
    std::cout << "NamedEntity::~NamedEntity()" << "\n";
}

const std::string& NamedEntity::name() const
{
    std::cout << "NamedEntity::name()" << "\n";
    return name_;
}

void NamedEntity::rename(std::string name)
{
    std::cout << "NamedEntity::rename(std::string)" << "\n";
    name_ = std::move(name);
}

Device::Device()
    : NamedEntity("device")
{
    std::cout << "Device::Device()" << "\n";
}

Device::Device(std::string name)
    : NamedEntity(std::move(name))
{
    std::cout << "Device::Device(std::string)" << "\n";
}

Device::~Device()
{
    std::cout << "Device::~Device()" << "\n";
}

std::string Device::kind() const
{
    std::cout << "Device::kind()" << "\n";
    return "Device";
}

void Device::reset()
{
    std::cout << "Device::reset()" << "\n";
    state_ = State::idle;
}

Device::State Device::state() const
{
    std::cout << "Device::state()" << "\n";
    return state_;
}

void Device::set_state(State state)
{
    std::cout << "Device::set_state(State)" << "\n";
    state_ = state;
}

Device Device::make_default()
{
    std::cout << "Device::make_default()" << "\n";
    return Device("default-device");
}

Sensor::Sensor()
    : Device("sensor")
{
    std::cout << "Sensor::Sensor()" << "\n";
}

Sensor::Sensor(std::string name, double reading)
    : Device(std::move(name))
    , reading_(reading)
{
    std::cout << "Sensor::Sensor(std::string, double)" << "\n";
}

Sensor::~Sensor()
{
    std::cout << "Sensor::~Sensor()" << "\n";
}

std::string Sensor::kind() const
{
    std::cout << "Sensor::kind()" << "\n";
    return "Sensor";
}

void Sensor::reset()
{
    std::cout << "Sensor::reset()" << "\n";
    set_state(State::idle);
    reading_ = 0.0;
}

double Sensor::reading() const
{
    std::cout << "Sensor::reading()" << "\n";
    return reading_;
}

void Sensor::set_reading(double reading)
{
    std::cout << "Sensor::set_reading(double)" << "\n";
    reading_ = reading;
}

void Registry::add(std::shared_ptr<NamedEntity> entity)
{
    std::cout << "Registry::add(std::shared_ptr<NamedEntity>)" << "\n";
    entities_.push_back(std::move(entity));
}

std::size_t Registry::size() const
{
    std::cout << "Registry::size()" << "\n";
    return entities_.size();
}

std::shared_ptr<NamedEntity> Registry::at(std::size_t index) const
{
    std::cout << "Registry::at(std::size_t)" << "\n";
    if (index >= entities_.size()) {
        throw std::out_of_range("Registry index out of range");
    }
    return entities_[index];
}

types::NameList Registry::names() const
{
    std::cout << "Registry::names()" << "\n";

    types::NameList names;
    names.reserve(entities_.size());
    for (const auto& entity : entities_) {
        names.push_back(entity->name());
    }
    return names;
}

std::shared_ptr<NamedEntity> make_sensor(std::string name, double reading)
{
    std::cout << "make_sensor(std::string, double)" << "\n";
    return std::make_shared<Sensor>(std::move(name), reading);
}

// -----------------------------------------------------------------------------
//   operators
// -----------------------------------------------------------------------------

Vector2::Vector2()
{
    std::cout << "Vector2::Vector2()" << "\n";
}

Vector2::Vector2(double x, double y)
    : x_(x)
    , y_(y)
{
    std::cout << "Vector2::Vector2(double, double)" << "\n";
}

double Vector2::x() const
{
    std::cout << "Vector2::x()" << "\n";
    return x_;
}

double Vector2::y() const
{
    std::cout << "Vector2::y()" << "\n";
    return y_;
}

void Vector2::translate(double dx, double dy)
{
    std::cout << "Vector2::translate(double, double)" << "\n";
    x_ += dx;
    y_ += dy;
}

double Vector2::length() const
{
    std::cout << "Vector2::length()" << "\n";
    return std::sqrt((x_ * x_) + (y_ * y_));
}

Vector2 Vector2::operator+(const Vector2& other) const
{
    std::cout << "Vector2::operator+(const Vector2&)" << "\n";
    return Vector2(x_ + other.x_, y_ + other.y_);
}

bool Vector2::operator==(const Vector2& other) const
{
    std::cout << "Vector2::operator==(const Vector2&)" << "\n";
    return x_ == other.x_ && y_ == other.y_;
}

}  // namespace cosmos::objects
