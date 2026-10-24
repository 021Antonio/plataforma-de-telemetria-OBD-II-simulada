#include "isotp.hpp"

#include <algorithm>

namespace elm327 {

namespace {

CanFrame padded(uint32_t id) {
    CanFrame f;
    f.id = id;
    f.len = 8;
    f.data.fill(kPad);
    return f;
}

// Quadros de outros IDs (tráfego do carro) são ignorados, até este limite por espera.
constexpr int kMaxForeign = 256;

}  // namespace

std::vector<CanFrame> segment(uint32_t id, const Bytes& payload) {
    std::vector<CanFrame> out;
    const std::size_t n = payload.size();
    if (n == 0 || n > kMaxPayload) return out;
    CanFrame f = padded(id);
    if (n <= 7) {
        f.data[0] = static_cast<uint8_t>(n);
        std::copy(payload.begin(), payload.end(), f.data.begin() + 1);
        out.push_back(f);
        return out;
    }
    f.data[0] = static_cast<uint8_t>(0x10 | (n >> 8));
    f.data[1] = static_cast<uint8_t>(n & 0xFF);
    std::copy(payload.begin(), payload.begin() + 6, f.data.begin() + 2);
    out.push_back(f);
    uint8_t seq = 1;
    for (std::size_t pos = 6; pos < n; pos += 7) {
        CanFrame c = padded(id);
        c.data[0] = static_cast<uint8_t>(0x20 | seq);
        seq = (seq + 1) & 0x0F;
        const std::size_t take = std::min<std::size_t>(7, n - pos);
        std::copy(payload.begin() + pos, payload.begin() + pos + take, c.data.begin() + 1);
        out.push_back(c);
    }
    return out;
}

CanFrame flow_control() {
    CanFrame f = padded(kRequestId);
    f.data[0] = 0x30;
    f.data[1] = 0x00;
    f.data[2] = 0x00;
    return f;
}

void Reassembler::reset() {
    data_.clear();
    expected_ = 0;
    next_seq_ = 1;
    receiving_ = false;
}

Reassembler::Event Reassembler::feed(const CanFrame& frame) {
    if (frame.len == 0) return Event::BadFrame;
    const uint8_t pci = frame.data[0];
    switch (pci >> 4) {
        case 0: {  // SF
            const std::size_t n = pci & 0x0F;
            if (n == 0 || n > 7 || n + 1 > frame.len) return Event::BadFrame;
            reset();
            data_.assign(frame.data.begin() + 1, frame.data.begin() + 1 + n);
            return Event::Complete;
        }
        case 1: {  // FF
            const std::size_t n = (static_cast<std::size_t>(pci & 0x0F) << 8) | frame.data[1];
            if (n < 8 || frame.len < 8) return Event::BadFrame;
            reset();
            expected_ = n;
            receiving_ = true;
            data_.assign(frame.data.begin() + 2, frame.data.begin() + 8);
            return Event::SendFlowControl;
        }
        case 2: {  // CF
            if (!receiving_) return Event::BadFrame;
            if ((pci & 0x0F) != next_seq_) {
                reset();
                return Event::SequenceError;
            }
            next_seq_ = (next_seq_ + 1) & 0x0F;
            const std::size_t avail = std::min<std::size_t>(frame.len - 1, 7);
            const std::size_t take = std::min(avail, expected_ - data_.size());
            data_.insert(data_.end(), frame.data.begin() + 1, frame.data.begin() + 1 + take);
            if (data_.size() < expected_) return Event::NeedMore;
            receiving_ = false;
            return Event::Complete;
        }
        default:  // FC e o resto não são respostas
            return Event::BadFrame;
    }
}

Exchange request(ICanBus& bus, const Bytes& req, const Timing& timing) {
    Exchange ex;
    if (req.empty() || req.size() > 7) {
        ex.status = Status::BadRequest;
        return ex;
    }
    for (const CanFrame& f : segment(kFunctionalId, req)) {
        if (!bus.send(f)) {
            ex.status = Status::BusError;
            return ex;
        }
    }
    Reassembler rx;
    bool multiframe = false;
    int foreign = 0;
    while (true) {
        CanFrame f;
        const uint32_t wait = multiframe ? timing.consecutive_ms : timing.first_ms;
        if (!bus.receive(f, wait)) {
            ex.status = multiframe ? Status::ConsecutiveTimeout : Status::NoResponse;
            return ex;
        }
        if (f.id != kResponseId) {
            if (++foreign > kMaxForeign) {
                ex.status = multiframe ? Status::ConsecutiveTimeout : Status::NoResponse;
                return ex;
            }
            continue;
        }
        ex.frames.push_back(f);
        switch (rx.feed(f)) {
            case Reassembler::Event::NeedMore:
                break;
            case Reassembler::Event::SendFlowControl:
                multiframe = true;
                if (!bus.send(flow_control())) {
                    ex.status = Status::BusError;
                    return ex;
                }
                break;
            case Reassembler::Event::Complete:
                ex.status = Status::Ok;
                ex.payload = rx.data();
                return ex;
            case Reassembler::Event::SequenceError:
                ex.status = Status::SequenceError;
                return ex;
            case Reassembler::Event::BadFrame:
                ex.status = Status::BadFrame;
                return ex;
        }
    }
}

}  // namespace elm327
