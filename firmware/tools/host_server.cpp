// Servidor TCP do PC com a biblioteca do firmware e a ECU de bancada, para rodar a suíte de
// conformidade contra o mesmo código do ESP32:
//   make -C firmware host_server && firmware/build/host_server 35100
//   python -m tests.conformance --host 127.0.0.1 --port 35100
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <thread>

#include "bench.hpp"
#include "elm327.hpp"

namespace {

void serve(int fd) {
    elm327::BenchEcu ecu;  // uma ECU falsa por conexão
    elm327::Session session(ecu);
    elm327::LineBuffer lines;
    char buf[256];
    for (ssize_t n; (n = recv(fd, buf, sizeof buf, 0)) > 0;) {
        for (const std::string& line : lines.feed(buf, static_cast<std::size_t>(n))) {
            const std::string out = session.handle(line);
            if (!out.empty() && send(fd, out.data(), out.size(), MSG_NOSIGNAL) < 0) {
                close(fd);
                return;
            }
        }
    }
    close(fd);
}

}  // namespace

int main(int argc, char** argv) {
    const int port = argc > 1 ? std::atoi(argv[1]) : 35100;
    const int srv = socket(AF_INET, SOCK_STREAM, 0);
    const int one = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(static_cast<uint16_t>(port));
    if (bind(srv, reinterpret_cast<sockaddr*>(&addr), sizeof addr) < 0 || listen(srv, 8) < 0) {
        std::perror("host_server");
        return 1;
    }
    std::printf("host_server ouvindo em 127.0.0.1:%d\n", port);
    std::fflush(stdout);
    for (;;) {
        const int fd = accept(srv, nullptr, nullptr);
        if (fd >= 0) std::thread(serve, fd).detach();
    }
}
