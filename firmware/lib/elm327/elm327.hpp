// Interpretador do dialeto ELM327 (docs/spec/09-elm327-dialeto.md): uma sessão por conexão.
// Puro: sem I/O e sem relógio; o barramento entra por `ICanBus`.
#pragma once

#include <string>
#include <vector>

#include "can.hpp"
#include "isotp.hpp"

namespace elm327 {

struct Options {
    // Só consultas (modos 01, 02, 03 e 09) vão ao barramento. O modo 04 (apagar falhas)
    // responde NO DATA, salvo se isto for ligado.
    bool allow_clear = false;
    Timing timing;
};

class Session {
public:
    Session(ICanBus& bus, Options options = {}) : bus_(bus), options_(options) { reset(); }

    // Trata uma linha (sem o terminador) e devolve os bytes a enviar: eco, linhas, linha
    // vazia e `>`. Linha em branco não gera resposta.
    std::string handle(const std::string& line);

private:
    void reset();
    void at(const std::string& arg, std::string& lines);
    void obd(const std::string& cmd, std::string& lines);
    void line(std::string& lines, const std::string& text) const;
    std::string voltage();
    std::string hex(const Bytes& data, bool spaces) const;

    ICanBus& bus_;
    Options options_;
    bool echo_ = true, linefeed_ = false, spaces_ = true, headers_ = false;
    bool searched_ = false, auto_ = true;
    const char* eol_ = "\r";
};

// Separa o fluxo TCP em linhas (terminadas em `\r` ou `\n`).
class LineBuffer {
public:
    // Acrescenta bytes e devolve as linhas completas (sem terminador, inclusive vazias).
    std::vector<std::string> feed(const char* data, std::size_t n);

private:
    std::string buf_;
};

}  // namespace elm327
