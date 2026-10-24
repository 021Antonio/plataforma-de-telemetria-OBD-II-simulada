// `ICanBus` sobre o driver TWAI do ESP32 (CAN 500 kbit/s, 11 bits). Só compila no ESP32.
#pragma once

#include <driver/twai.h>

#include "can.hpp"
#include "config.h"

class TwaiBus : public elm327::ICanBus {
public:
    bool begin() {
        twai_general_config_t g =
            TWAI_GENERAL_CONFIG_DEFAULT((gpio_num_t)CAN_TX_PIN, (gpio_num_t)CAN_RX_PIN, TWAI_MODE_NORMAL);
        g.rx_queue_len = 32;
        twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
        // Só passam os IDs 0x7E8 a 0x7EF: o carro trafega muito mais do que isso.
        twai_filter_config_t f = {.acceptance_code = (uint32_t)0x7E8 << 21,
                                  .acceptance_mask = ~((uint32_t)0x7FF << 21) | ((uint32_t)0x7 << 21),
                                  .single_filter = true};
        return twai_driver_install(&g, &t, &f) == ESP_OK && twai_start() == ESP_OK;
    }

    bool send(const elm327::CanFrame& frame) override {
        if (frame.data[0] >> 4 != 3) twai_clear_receive_queue();  // descarta resposta atrasada
        twai_message_t m = {};
        m.identifier = frame.id;
        m.data_length_code = frame.len;
        for (int i = 0; i < frame.len; ++i) m.data[i] = frame.data[i];
        return twai_transmit(&m, pdMS_TO_TICKS(20)) == ESP_OK;
    }

    bool receive(elm327::CanFrame& frame, uint32_t timeout_ms) override {
        twai_message_t m;
        if (twai_receive(&m, pdMS_TO_TICKS(timeout_ms)) != ESP_OK) return false;
        frame.id = m.identifier;
        frame.len = m.data_length_code;
        for (int i = 0; i < 8; ++i) frame.data[i] = m.data[i];
        return true;
    }
};
