#include "elm327.hpp"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <vector>

namespace elm327 {

namespace {

const char* const kVersion = "ELM327 v1.5";
const char* const kProtocol = "ISO 15765-4 (CAN 11/500)";
const char* const kDescription = "OBD-II simulator (software-in-the-loop)";
constexpr std::size_t kMaxRequest = 7;  // um quadro único ISO-TP
constexpr uint8_t kVoltagePid = 0x42;

// Aceitos com `OK` e sem efeito.
const char* const kAccepted[] = {"AT", "ST", "SH", "CAF", "CRA", "AL", "D",  "M",  "R",
                                 "PC", "JHF", "JS", "FE",  "SW",  "WM", "CF", "CM", "CS",
                                 "V",  "KW",  "IB", "BI",  "SS",  "CV"};

bool starts_with(const std::string& s, const std::string& prefix) {
    return s.compare(0, prefix.size(), prefix) == 0;
}

bool is_hex(const std::string& s) {
    return !s.empty() && std::all_of(s.begin(), s.end(), [](unsigned char c) {
               return std::isdigit(c) || (c >= 'A' && c <= 'F');
           });
}

Bytes from_hex(const std::string& s) {
    Bytes out;
    for (std::size_t i = 0; i < s.size(); i += 2) {
        out.push_back(static_cast<uint8_t>(std::stoi(s.substr(i, 2), nullptr, 16)));
    }
    return out;
}

// Bytes úteis de cada quadro recebido: SF 1+N, FF 8, CF 1+restante (sem o preenchimento).
std::size_t used_length(const CanFrame& f, std::size_t total, std::size_t index) {
    switch (f.data[0] >> 4) {
        case 0: return 1 + (f.data[0] & 0x0F);
        case 1: return 8;
        default: return 1 + std::min<std::size_t>(7, total - 6 - 7 * (index - 1));
    }
}

// `0` ou `6`, com `A` na frente (automático) ou não.
bool is_protocol(const std::string& s) {
    const auto n = s.find_first_not_of('A');
    return n != std::string::npos && (s.substr(n) == "0" || s.substr(n) == "6");
}

}  // namespace

std::string Session::hex(const Bytes& data, bool spaces) const {
    std::string out;
    char b[3];
    for (std::size_t i = 0; i < data.size(); ++i) {
        std::snprintf(b, sizeof b, "%02X", data[i]);
        if (spaces && i) out += ' ';
        out += b;
    }
    return out;
}

void Session::reset() {
    echo_ = true;
    linefeed_ = false;
    spaces_ = true;
    headers_ = false;
    searched_ = false;
    auto_ = true;
}

void Session::line(std::string& lines, const std::string& text) const {
    lines += text;
    lines += eol_;
}

std::string Session::handle(const std::string& raw) {
    const auto b = raw.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    const std::string typed = raw.substr(b, raw.find_last_not_of(" \t\r\n") - b + 1);
    std::string cmd;
    for (char c : raw) {
        if (c != ' ') cmd += static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    }

    // O fim de linha vale o de antes do comando: `ATL1` ainda responde com `\r`.
    eol_ = linefeed_ ? "\r\n" : "\r";
    const bool echoed = echo_ && cmd != "ATZ";  // ATZ reinicia e não ecoa
    std::string lines;
    if (starts_with(cmd, "AT")) {
        at(cmd.substr(2), lines);
    } else {
        obd(cmd, lines);
    }
    std::string out;
    if (echoed) line(out, typed);
    out += lines + eol_ + ">";
    return out;
}

void Session::at(const std::string& arg, std::string& lines) {
    auto ok = [&] { line(lines, "OK"); };
    if (arg == "Z") {
        reset();
        line(lines, kVersion);
    } else if (arg == "I" || arg == "WS") {
        line(lines, kVersion);
    } else if (arg == "IGN") {
        line(lines, "ON");
    } else if (arg == "DP") {
        line(lines, auto_ ? std::string("AUTO, ") + kProtocol : kProtocol);
    } else if (arg == "DPN") {
        line(lines, auto_ ? "A6" : "6");
    } else if (arg == "RV") {
        line(lines, voltage());
    } else if (arg == "@1") {
        line(lines, kDescription);
    } else if (arg.size() == 2 && std::string("ELSH").find(arg[0]) != std::string::npos &&
               (arg[1] == '0' || arg[1] == '1')) {
        const bool on = arg[1] == '1';
        switch (arg[0]) {
            case 'E': echo_ = on; break;
            case 'L': linefeed_ = on; break;
            case 'S': spaces_ = on; break;
            default: headers_ = on; break;
        }
        ok();
    } else if ((starts_with(arg, "SP") || starts_with(arg, "TP")) && is_protocol(arg.substr(2))) {
        auto_ = arg[2] == '0' || arg[2] == 'A';
        ok();
    } else if (std::any_of(std::begin(kAccepted), std::end(kAccepted),
                           [&](const char* p) { return starts_with(arg, p); })) {
        ok();
    } else {
        line(lines, "?");
    }
}

std::string Session::voltage() {
    const Exchange ex = request(bus_, {0x01, kVoltagePid}, options_.timing);
    if (ex.status != Status::Ok || ex.payload.size() < 4) return "12.6V";
    const unsigned mv = ex.payload[2] * 256u + ex.payload[3];
    char buf[16];
    std::snprintf(buf, sizeof buf, "%u.%uV", (mv + 50) / 1000, ((mv + 50) % 1000) / 100);
    return buf;
}

void Session::obd(const std::string& cmd, std::string& lines) {
    if (!is_hex(cmd) || cmd.size() % 2 || cmd.size() / 2 > kMaxRequest) {
        line(lines, "?");
        return;
    }
    const Bytes req = from_hex(cmd);
    const bool first_search = cmd == "0100" && !searched_;
    searched_ = true;
    if (first_search) line(lines, "SEARCHING...");

    const uint8_t mode = req[0];
    const bool query = mode == 0x01 || mode == 0x02 || mode == 0x03 || mode == 0x09;
    if (!query && !(mode == 0x04 && options_.allow_clear)) {
        line(lines, "NO DATA");  // nada de escrita no carro: não chega ao barramento
        return;
    }
    const Exchange ex = request(bus_, req, options_.timing);
    switch (ex.status) {
        case Status::Ok:
            break;
        case Status::NoResponse:
            line(lines, "NO DATA");
            return;
        default:
            line(lines, "CAN ERROR");
            return;
    }
    const Bytes& r = ex.payload;
    if (r.empty() || r[0] == 0x7F || r == Bytes{0x43, 0x00}) {
        line(lines, "NO DATA");  // o chip real não repete a negativa da ECU
        return;
    }
    if (!headers_) {
        line(lines, hex(r, spaces_));
        return;
    }
    for (std::size_t i = 0; i < ex.frames.size(); ++i) {
        const CanFrame& f = ex.frames[i];
        const Bytes used(f.data.begin(), f.data.begin() + used_length(f, r.size(), i));
        line(lines, spaces_ ? "7E8 " + hex(used, true) : "7E8" + hex(used, false));
    }
}

std::vector<std::string> LineBuffer::feed(const char* data, std::size_t n) {
    std::vector<std::string> out;
    for (std::size_t i = 0; i < n; ++i) {
        if (data[i] == '\r' || data[i] == '\n') {
            out.push_back(buf_);
            buf_.clear();
        } else {
            buf_ += data[i];
        }
    }
    return out;
}

}  // namespace elm327
