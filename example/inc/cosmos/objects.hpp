#pragma once

#include "cosmos/types.hpp"

#include <cstddef>
#include <memory>
#include <string>
#include <vector>

// ================================================================================================
//   cosmos::objects
// ================================================================================================

namespace cosmos::objects {

// -----------------------------------------------------------------------------
//   classe inheritance
// -----------------------------------------------------------------------------

/** Abstract base class used for polymorphic binding tests. */
class NamedEntity {
public:
    NamedEntity();
    explicit NamedEntity(std::string name);
    virtual ~NamedEntity();

    virtual std::string kind() const = 0;

    const std::string& name() const;
    void rename(std::string name);

protected:
    std::string name_;
};

/** Concrete class with a nested enum and a virtual method. */
class Device : public NamedEntity {
public:
    enum class State {
        idle,
        running,
        stopped,
    };

    Device();
    explicit Device(std::string name);
    ~Device() override;

    std::string kind() const override;
    virtual void reset();

    State state() const;
    void set_state(State state);

    static Device make_default();

private:
    State state_ {State::idle};
};

/** Derived class with extra state and overridden behavior. */
class Sensor : public Device {
public:
    Sensor();
    Sensor(std::string name, double reading);
    ~Sensor() override;

    std::string kind() const override;
    void reset() override;

    double reading() const;
    void set_reading(double reading);

private:
    double reading_ {0.0};
};

/** Container that stores polymorphic instances through shared pointers. */
class Registry {
public:
    void add(std::shared_ptr<NamedEntity> entity);
    std::size_t size() const;
    std::shared_ptr<NamedEntity> at(std::size_t index) const;
    types::NameList names() const;

private:
    std::vector<std::shared_ptr<NamedEntity>> entities_;
};

/** Factory returning a polymorphic shared pointer. */
std::shared_ptr<NamedEntity> make_sensor(std::string name, double reading);

// -----------------------------------------------------------------------------
//   operators
// -----------------------------------------------------------------------------

/** Lightweight value type with a few operators. */
class Vector2 {
public:
    Vector2();
    Vector2(double x, double y);

    double x() const;
    double y() const;

    void translate(double dx, double dy);
    double length() const;

    Vector2 operator+(const Vector2& other) const;
    bool operator==(const Vector2& other) const;

private:
    double x_ {0.0};
    double y_ {0.0};
};

}  // namespace cosmos::objects
