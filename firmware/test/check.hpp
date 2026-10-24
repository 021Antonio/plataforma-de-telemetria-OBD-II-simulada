// Asserções mínimas: só as falhas são impressas.
#pragma once

#include <cstdio>
#include <functional>
#include <string>
#include <vector>

namespace check {

struct Case {
    const char* name;
    std::function<void()> fn;
};

inline std::vector<Case>& cases() {
    static std::vector<Case> c;
    return c;
}
inline int& failures() {
    static int n = 0;
    return n;
}
struct Register {
    Register(const char* name, std::function<void()> fn) { cases().push_back({name, std::move(fn)}); }
};

inline std::string show(const std::string& s) {
    std::string o = "\"";
    for (unsigned char c : s) {
        if (c == '\r') o += "\\r";
        else if (c == '\n') o += "\\n";
        else if (c < 32 || c > 126) { char b[8]; std::snprintf(b, sizeof b, "\\x%02X", c); o += b; }
        else o += static_cast<char>(c);
    }
    return o + "\"";
}

}  // namespace check

#define TEST(name)                                                       \
    static void name();                                                  \
    static check::Register reg_##name(#name, name);                      \
    static void name()

#define CHECK(cond)                                                                  \
    do {                                                                             \
        if (!(cond)) {                                                               \
            ++check::failures();                                                     \
            std::printf("FALHA %s:%d: %s\n", __FILE__, __LINE__, #cond);             \
        }                                                                            \
    } while (0)

#define CHECK_STR(got, want)                                                         \
    do {                                                                             \
        const std::string g_ = (got), w_ = (want);                                   \
        if (g_ != w_) {                                                              \
            ++check::failures();                                                     \
            std::printf("FALHA %s:%d: obtido %s esperado %s\n", __FILE__, __LINE__,  \
                        check::show(g_).c_str(), check::show(w_).c_str());           \
        }                                                                            \
    } while (0)
