// Dublê de barramento: devolve quadros roteirizados e registra o que foi enviado.
#pragma once

#include <deque>
#include <vector>

#include "can.hpp"

struct ScriptedBus : elm327::ICanBus {
    std::deque<elm327::CanFrame> after_request;  // liberados no primeiro envio
    std::deque<elm327::CanFrame> after_flow;     // liberados quando chega o quadro de fluxo
    std::deque<elm327::CanFrame> rx;
    std::vector<elm327::CanFrame> sent;
    bool refuse_send = false;

    bool send(const elm327::CanFrame& f) override {
        if (refuse_send) return false;
        sent.push_back(f);
        auto& from = (f.data[0] >> 4) == 3 ? after_flow : after_request;
        for (const auto& x : from) rx.push_back(x);
        from.clear();
        return true;
    }
    bool receive(elm327::CanFrame& f, uint32_t) override {
        if (rx.empty()) return false;
        f = rx.front();
        rx.pop_front();
        return true;
    }
};
