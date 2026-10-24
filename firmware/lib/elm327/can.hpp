// Interface da camada CAN. A biblioteca não conhece Arduino nem ESP-IDF: o ESP32 implementa
// `ICanBus` com o TWAI, o PC com um dublê ou com a ECU de bancada (`BenchEcu`).
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace elm327 {

struct CanFrame {
    uint32_t id = 0;
    uint8_t len = 0;
    std::array<uint8_t, 8> data{};
};

class ICanBus {
public:
    virtual ~ICanBus() = default;
    // Envia um quadro; false se o barramento recusou (sem ACK, bus-off...).
    virtual bool send(const CanFrame& frame) = 0;
    // Próximo quadro recebido, esperando até `timeout_ms`; false se estourou o tempo.
    virtual bool receive(CanFrame& frame, uint32_t timeout_ms) = 0;
};

}  // namespace elm327
