// ISO-TP (ISO 15765-2) sobre CAN de 11 bits, no papel de testador: envia a requisição,
// responde ao primeiro quadro com controle de fluxo e remonta a resposta (1 a 4095 bytes).
#pragma once

#include <cstdint>
#include <vector>

#include "can.hpp"

namespace elm327 {

using Bytes = std::vector<uint8_t>;

constexpr uint32_t kFunctionalId = 0x7DF;
constexpr uint32_t kRequestId = 0x7E0;   // também o ID do quadro de fluxo
constexpr uint32_t kResponseId = 0x7E8;  // ECU do motor
constexpr uint8_t kPad = 0x55;
constexpr std::size_t kMaxPayload = 4095;

// Quadros de `payload` (SF ou FF + CFs) com o ID dado e preenchimento 0x55. Vazio se o
// tamanho for 0 ou maior que 4095.
std::vector<CanFrame> segment(uint32_t id, const Bytes& payload);

// Quadro de fluxo "continuar", BS = 0, STmin = 0.
CanFrame flow_control();

class Reassembler {
public:
    enum class Event {
        NeedMore,         // faltam quadros
        SendFlowControl,  // chegou um FF: mandar o FC e esperar os CFs
        Complete,         // `data()` tem a mensagem inteira
        SequenceError,    // CF fora de ordem
        BadFrame,         // quadro inválido ou fora de contexto
    };

    Event feed(const CanFrame& frame);
    const Bytes& data() const { return data_; }
    void reset();

private:
    Bytes data_;
    std::size_t expected_ = 0;
    uint8_t next_seq_ = 1;
    bool receiving_ = false;
};

struct Timing {
    uint32_t first_ms = 200;         // espera pela primeira resposta (P2 com folga)
    uint32_t consecutive_ms = 1000;  // N_Cr entre quadros consecutivos
};

enum class Status {
    Ok,
    NoResponse,          // nenhuma ECU respondeu a tempo
    ConsecutiveTimeout,  // o multiquadro parou no meio (N_Cr)
    SequenceError,
    BadFrame,
    BusError,       // o barramento recusou um envio
    BadRequest,     // vazia ou com mais de 7 bytes
};

struct Exchange {
    Status status = Status::NoResponse;
    Bytes payload;                 // resposta remontada
    std::vector<CanFrame> frames;  // quadros recebidos, na ordem (para `ATH1`)
};

// Envia `request` (1 a 7 bytes) em 0x7DF e devolve a resposta de 0x7E8.
Exchange request(ICanBus& bus, const Bytes& request, const Timing& timing = {});

}  // namespace elm327
