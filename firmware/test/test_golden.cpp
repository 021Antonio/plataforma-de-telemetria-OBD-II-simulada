// Cada comando do roteiro de conformidade deve formatar igual ao tests/conformance/dourado.json.
#include <fstream>
#include <sstream>

#include "bench.hpp"
#include "check.hpp"
#include "elm327.hpp"

#ifndef GOLDEN_PATH
#error "defina GOLDEN_PATH"
#endif

namespace {

struct Entry {
    std::string cmd, reply;
};

// Lê o array [{"comando": "...", "resposta": "..."}, ...] (só strings, com escapes JSON).
std::vector<Entry> load(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    std::stringstream ss;
    ss << in.rdbuf();
    const std::string t = ss.str();
    std::vector<std::string> strings;
    for (std::size_t i = 0; i < t.size(); ++i) {
        if (t[i] != '"') continue;
        std::string s;
        for (++i; t[i] != '"'; ++i) {
            if (t[i] != '\\') { s += t[i]; continue; }
            switch (t[++i]) {
                case 'n': s += '\n'; break;
                case 'r': s += '\r'; break;
                case 't': s += '\t'; break;
                case 'u': s += static_cast<char>(std::stoi(t.substr(i + 1, 4), nullptr, 16)); i += 4; break;
                default: s += t[i];
            }
        }
        strings.push_back(s);
    }
    std::vector<Entry> out;
    for (std::size_t i = 0; i + 3 < strings.size(); i += 4) {
        out.push_back({strings[i + 1], strings[i + 3]});  // "comando", X, "resposta", Y
    }
    return out;
}

}  // namespace

TEST(golden_file_is_readable) {
    const auto golden = load(GOLDEN_PATH);
    CHECK(golden.size() == 41);
}

TEST(every_command_matches_the_golden_file) {
    const auto golden = load(GOLDEN_PATH);
    elm327::BenchEcu ecu;
    elm327::Session session(ecu);
    for (const auto& e : golden) {
        const std::string got = session.handle(e.cmd);
        if (got != e.reply) {
            CHECK_STR(got, e.reply);
            std::printf("  comando %s\n", e.cmd.c_str());
        }
    }
}
