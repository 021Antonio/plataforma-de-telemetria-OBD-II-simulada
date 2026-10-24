#include <algorithm>

#include "bench.hpp"
#include "check.hpp"
#include "fakes.hpp"
#include "isotp.hpp"

using namespace elm327;

namespace {

Bytes pattern(std::size_t n) {
    Bytes b(n);
    for (std::size_t i = 0; i < n; ++i) b[i] = static_cast<uint8_t>(i * 7 + 3);
    return b;
}

}  // namespace

TEST(reassembles_every_length_from_1_to_4095) {
    for (std::size_t n = 1; n <= kMaxPayload; ++n) {
        const Bytes want = pattern(n);
        Reassembler rx;
        const auto frames = segment(kResponseId, want);
        Reassembler::Event last = Reassembler::Event::NeedMore;
        for (const auto& f : frames) last = rx.feed(f);
        if (last != Reassembler::Event::Complete || rx.data() != want) {
            CHECK(false);
            std::printf("  comprimento %zu\n", n);
            return;
        }
    }
}

TEST(first_frame_asks_for_flow_control) {
    Reassembler rx;
    const auto frames = segment(kResponseId, pattern(20));
    CHECK(rx.feed(frames[0]) == Reassembler::Event::SendFlowControl);
    CHECK(rx.feed(frames[1]) == Reassembler::Event::NeedMore);
    CHECK(rx.feed(frames[2]) == Reassembler::Event::Complete);
}

TEST(out_of_order_frames_are_rejected) {
    const auto frames = segment(kResponseId, pattern(40));  // FF + 5 CFs
    Reassembler rx;
    rx.feed(frames[0]);
    rx.feed(frames[1]);
    CHECK(rx.feed(frames[3]) == Reassembler::Event::SequenceError);  // pulou o 2
    rx.reset();
    rx.feed(frames[0]);
    CHECK(rx.feed(frames[2]) == Reassembler::Event::SequenceError);  // 2 antes do 1
    CHECK(rx.feed(frames[1]) == Reassembler::Event::BadFrame);       // sem FF em andamento
}

TEST(duplicate_consecutive_frame_is_rejected) {
    const auto frames = segment(kResponseId, pattern(40));
    Reassembler rx;
    rx.feed(frames[0]);
    rx.feed(frames[1]);
    CHECK(rx.feed(frames[1]) == Reassembler::Event::SequenceError);
}

TEST(sequence_number_wraps_after_f) {
    const auto frames = segment(kResponseId, pattern(200));
    CHECK((frames[15].data[0] & 0x0F) == 15);
    CHECK((frames[16].data[0] & 0x0F) == 0);
}

TEST(malformed_frames_are_bad) {
    Reassembler rx;
    CanFrame ff;
    ff.len = 8;
    ff.data = {0x10, 0x05, 1, 2, 3, 4, 5, 6};  // FF com comprimento < 8
    CHECK(rx.feed(ff) == Reassembler::Event::BadFrame);
    CanFrame fc;
    fc.len = 8;
    fc.data = {0x30, 0, 0, kPad, kPad, kPad, kPad, kPad};
    CHECK(rx.feed(fc) == Reassembler::Event::BadFrame);
    CHECK(rx.feed(CanFrame{}) == Reassembler::Event::BadFrame);
}

TEST(request_end_to_end_for_every_length_with_flow_control) {
    for (std::size_t n = 1; n <= kMaxPayload; ++n) {
        BenchEcu ecu;
        ecu.set_response({0x09, 0x02}, pattern(n));
        const Exchange ex = request(ecu, {0x09, 0x02});
        if (ex.status != Status::Ok || ex.payload != pattern(n)) {
            CHECK(false);
            std::printf("  comprimento %zu\n", n);
            return;
        }
    }
}

TEST(request_sends_functional_frame_and_flow_control) {
    ScriptedBus bus;
    const auto frames = segment(kResponseId, pattern(20));
    bus.after_request.push_back(frames[0]);
    bus.after_flow.push_back(frames[1]);
    bus.after_flow.push_back(frames[2]);
    const Exchange ex = request(bus, {0x09, 0x02});
    CHECK(ex.status == Status::Ok);
    CHECK(ex.payload == pattern(20));
    CHECK(bus.sent.size() == 2);
    CHECK(bus.sent[0].id == 0x7DF);
    CHECK((bus.sent[0].data == std::array<uint8_t, 8>{2, 9, 2, kPad, kPad, kPad, kPad, kPad}));
    CHECK(bus.sent[1].id == 0x7E0);
    CHECK((bus.sent[1].data == std::array<uint8_t, 8>{0x30, 0, 0, kPad, kPad, kPad, kPad, kPad}));
    CHECK(ex.frames.size() == 3);
}

TEST(ecu_holds_consecutive_frames_until_flow_control) {
    BenchEcu ecu;
    ecu.set_response({0x09, 0x02}, pattern(20));
    CanFrame req;
    req.id = kFunctionalId;
    req.len = 8;
    req.data = {2, 9, 2, kPad, kPad, kPad, kPad, kPad};
    ecu.send(req);
    CanFrame f;
    CHECK(ecu.receive(f, 0));  // FF
    CHECK(!ecu.receive(f, 0));  // CFs só depois do FC
    ecu.send(flow_control());
    CHECK(ecu.receive(f, 0));
    CHECK(ecu.receive(f, 0));
}

TEST(consecutive_frame_timeout) {
    ScriptedBus bus;
    const auto frames = segment(kResponseId, pattern(30));
    bus.after_request.push_back(frames[0]);
    bus.after_flow.push_back(frames[1]);  // o resto nunca chega
    const Exchange ex = request(bus, {0x09, 0x02});
    CHECK(ex.status == Status::ConsecutiveTimeout);
}

TEST(no_response_is_a_timeout) {
    ScriptedBus bus;
    CHECK(request(bus, {0x01, 0x0C}).status == Status::NoResponse);
}

TEST(out_of_order_on_the_wire) {
    ScriptedBus bus;
    const auto frames = segment(kResponseId, pattern(30));
    bus.after_request.push_back(frames[0]);
    bus.after_flow.push_back(frames[2]);
    bus.after_flow.push_back(frames[1]);
    CHECK(request(bus, {0x09, 0x02}).status == Status::SequenceError);
}

TEST(foreign_ids_are_ignored) {
    ScriptedBus bus;
    CanFrame noise;
    noise.id = 0x123;
    noise.len = 8;
    CanFrame ok = segment(kResponseId, {0x41, 0x0D, 0x4D})[0];
    bus.after_request = {noise, noise, ok};
    const Exchange ex = request(bus, {0x01, 0x0D});
    CHECK(ex.status == Status::Ok);
    CHECK((ex.payload == Bytes{0x41, 0x0D, 0x4D}));
}

TEST(bus_errors_and_bad_requests) {
    ScriptedBus bus;
    bus.refuse_send = true;
    CHECK(request(bus, {0x01, 0x0C}).status == Status::BusError);
    CHECK(request(bus, {}).status == Status::BadRequest);
    CHECK(request(bus, Bytes(8, 1)).status == Status::BadRequest);
    CHECK(segment(kResponseId, {}).empty());
    CHECK(segment(kResponseId, Bytes(4096, 1)).empty());
}
