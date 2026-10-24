#include "check.hpp"

int main() {
    int ran = 0;
    for (const auto& c : check::cases()) {
        const int before = check::failures();
        c.fn();
        ++ran;
        if (check::failures() != before) std::printf("  em %s\n", c.name);
    }
    std::printf("%d teste(s), %d falha(s)\n", ran, check::failures());
    return check::failures() ? 1 : 0;
}
