// ECU falsa de bancada: responde em 0x7E8 com valores fixos (os do ensaio, iguais ao
// `dourado.json`), sem CAN. Serve ao modo de bancada do ESP32 e aos testes no PC.
#pragma once

#include <deque>
#include <map>
#include <vector>

#include "can.hpp"
#include "isotp.hpp"

namespace elm327 {

class BenchEcu : public ICanBus {
public:
    BenchEcu();

    bool send(const CanFrame& frame) override;
    bool receive(CanFrame& frame, uint32_t timeout_ms) override;

    // Substitui a resposta de uma requisição (para testar comprimentos arbitrários).
    void set_response(const Bytes& request, const Bytes& response);
    // DTCs armazenados (2 bytes cada), devolvidos no modo 03.
    void set_dtcs(const std::vector<Bytes>& dtcs) { dtcs_ = dtcs; }

    int requests_seen() const { return requests_; }
    const std::vector<Bytes>& request_log() const { return log_; }

private:
    Bytes respond(const Bytes& req) const;

    std::map<Bytes, Bytes> table_;
    std::vector<Bytes> dtcs_;
    std::deque<CanFrame> rx_;       // o que o testador vai receber
    std::deque<CanFrame> pending_;  // CFs à espera do quadro de fluxo
    int requests_ = 0;
    std::vector<Bytes> log_;
};

}  // namespace elm327
