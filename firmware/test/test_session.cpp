#include "bench.hpp"
#include "check.hpp"
#include "elm327.hpp"
#include "fakes.hpp"

using namespace elm327;

namespace {

// Sessão pronta para as consultas: sem eco, para comparar só a resposta.
struct Rig {
    BenchEcu ecu;
    Session s;
    explicit Rig(Options o = {}) : s(ecu, o) { s.handle("ATE0"); }
};

}  // namespace

TEST(mode_04_answers_no_data_and_never_reaches_the_bus) {
    Rig r;
    CHECK_STR(r.s.handle("04"), "NO DATA\r\r>");
    CHECK(r.ecu.requests_seen() == 0);
}

TEST(mode_04_can_be_enabled_explicitly) {
    Options o;
    o.allow_clear = true;
    Rig r(o);
    CHECK_STR(r.s.handle("04"), "44\r\r>");
    CHECK(r.ecu.requests_seen() == 1);
}

TEST(only_modes_01_02_03_09_reach_the_bus) {
    Rig r;
    for (const char* c : {"04", "05", "06", "07", "08", "0A", "0600", "0701", "FF", "2201"}) {
        CHECK_STR(r.s.handle(c), "NO DATA\r\r>");
    }
    CHECK(r.ecu.requests_seen() == 0);
    r.s.handle("0100");
    r.s.handle("0200");
    r.s.handle("03");
    r.s.handle("0902");
    CHECK(r.ecu.requests_seen() == 4);
}

TEST(freeze_frame_mode_02) {
    Rig r;
    CHECK_STR(r.s.handle("020C00"), "42 0C 00 30 DE\r\r>");
}

TEST(dtcs_in_mode_03) {
    Rig r;
    r.ecu.set_dtcs({{0x03, 0x00}});
    CHECK_STR(r.s.handle("03"), "43 01 03 00\r\r>");
}

TEST(invalid_requests_answer_question_mark) {
    Rig r;
    for (const char* c : {"XYZ", "010", "0102030405060708", "ATXX", "AT", "ATSP", "ATSP7"}) {
        CHECK_STR(r.s.handle(c), "?\r\r>");
    }
    CHECK(r.ecu.requests_seen() == 0);
}

TEST(case_and_spaces_are_ignored_and_blank_lines_are_silent) {
    Rig r;
    CHECK_STR(r.s.handle("01 0c"), "41 0C 30 DE\r\r>");
    CHECK_STR(r.s.handle(""), "");
    CHECK_STR(r.s.handle("   "), "");
}

TEST(voltage_comes_from_pid_42_or_falls_back) {
    Rig r;
    CHECK_STR(r.s.handle("ATRV"), "14.0V\r\r>");
    ScriptedBus silent;
    Session s(silent);
    s.handle("ATE0");
    CHECK_STR(s.handle("ATRV"), "12.6V\r\r>");
    CHECK_STR(s.handle("010C"), "NO DATA\r\r>");
}

TEST(multiframe_failure_reports_can_error) {
    ScriptedBus bus;
    bus.after_request.push_back(segment(kResponseId, Bytes(30, 1))[0]);  // FF e mais nada
    Session s(bus);
    s.handle("ATE0");
    CHECK_STR(s.handle("0902"), "CAN ERROR\r\r>");
}

TEST(negative_response_becomes_no_data) {
    ScriptedBus bus;
    bus.after_request.push_back(segment(kResponseId, {0x7F, 0x01, 0x12})[0]);
    Session s(bus);
    s.handle("ATE0");
    CHECK_STR(s.handle("0101"), "NO DATA\r\r>");
}

TEST(atz_resets_state_and_searching_returns) {
    Rig r;
    CHECK_STR(r.s.handle("0100"), "SEARCHING...\r41 00 9C 3A 80 01\r\r>");
    CHECK_STR(r.s.handle("0100"), "41 00 9C 3A 80 01\r\r>");
    r.s.handle("ATS0");
    CHECK_STR(r.s.handle("ATZ"), "ELM327 v1.5\r\r>");
    // depois do ATZ o eco volta e o SEARCHING... também
    CHECK_STR(r.s.handle("0100"), "0100\rSEARCHING...\r41 00 9C 3A 80 01\r\r>");
}

TEST(line_buffer_splits_on_cr_and_lf) {
    LineBuffer b;
    auto a = b.feed("ATZ\r01", 6);
    CHECK(a.size() == 1 && a[0] == "ATZ");
    auto c = b.feed("0C\r\n", 4);
    CHECK(c.size() == 2 && c[0] == "010C" && c[1].empty());
}
