#include "bench.hpp"

namespace elm327 {

namespace {

const Bytes kVin = {'9', 'B', 'W', 'Z', 'Z', 'Z', '3', '7', '7', 'V', 'T', '0', '0', '4', '2', '5', '1'};

// PID -> dados (modo 01); o modo 02 devolve os mesmos valores como quadro congelado.
const std::map<uint8_t, Bytes> kPids = {
    {0x00, {0x9C, 0x3A, 0x80, 0x01}}, {0x01, {0x00, 0x00, 0x00, 0x00}},
    {0x04, {0x40}},                   {0x05, {0x80}},
    {0x06, {0x80}},                   {0x0B, {0x23}},
    {0x0C, {0x30, 0xDE}},             {0x0D, {0x4D}},
    {0x0F, {0x5A}},                   {0x11, {0x2F}},
    {0x20, {0x00, 0x02, 0x00, 0x01}}, {0x40, {0x40, 0x00, 0x00, 0x00}},
    {0x42, {0x36, 0xB0}},  // 14,000 V
};

}  // namespace

BenchEcu::BenchEcu() {
    for (const auto& [pid, data] : kPids) {
        Bytes r = {0x41, pid};
        r.insert(r.end(), data.begin(), data.end());
        table_[{0x01, pid}] = r;
        if (pid != 0x00 && pid != 0x20 && pid != 0x40) {
            Bytes f = {0x42, pid, 0x00};
            f.insert(f.end(), data.begin(), data.end());
            table_[{0x02, pid, 0x00}] = f;
        }
    }
    table_[{0x09, 0x00}] = {0x49, 0x00, 0x40, 0x00, 0x00, 0x00};
    Bytes vin = {0x49, 0x02, 0x01};
    vin.insert(vin.end(), kVin.begin(), kVin.end());
    table_[{0x09, 0x02}] = vin;
}

void BenchEcu::set_response(const Bytes& request, const Bytes& response) {
    table_[request] = response;
}

Bytes BenchEcu::respond(const Bytes& req) const {
    if (req.size() == 1 && req[0] == 0x03) {
        Bytes r = {0x43, static_cast<uint8_t>(dtcs_.size())};
        for (const Bytes& d : dtcs_) r.insert(r.end(), d.begin(), d.end());
        return r;
    }
    if (req.size() == 1 && req[0] == 0x04) return {0x44};
    auto it = table_.find(req);
    return it == table_.end() ? Bytes{} : it->second;  // sem suporte: sem resposta
}

bool BenchEcu::send(const CanFrame& f) {
    if (f.len == 0) return true;
    const uint8_t pci = f.data[0];
    if (f.id == kRequestId && (pci >> 4) == 3) {  // quadro de fluxo
        if ((pci & 0x0F) == 0) {                   // continuar
            for (const CanFrame& c : pending_) rx_.push_back(c);
            pending_.clear();
        } else if ((pci & 0x0F) == 2) {  // estouro: descarta
            pending_.clear();
        }
        return true;
    }
    if ((f.id != kFunctionalId && f.id != kRequestId) || (pci >> 4) != 0) return true;
    const std::size_t n = pci & 0x0F;
    if (n == 0 || n > 7 || n + 1 > f.len) return true;
    Bytes req(f.data.begin() + 1, f.data.begin() + 1 + n);
    ++requests_;
    log_.push_back(req);
    const Bytes resp = respond(req);
    std::vector<CanFrame> frames = segment(kResponseId, resp);
    rx_.clear();  // como o TWAI: respostas atrasadas de antes são descartadas
    pending_.clear();
    for (std::size_t i = 0; i < frames.size(); ++i) {
        (i == 0 ? rx_ : pending_).push_back(frames[i]);
    }
    return true;
}

bool BenchEcu::receive(CanFrame& frame, uint32_t) {
    if (rx_.empty()) return false;  // sem espera real: vazio equivale a estouro de tempo
    frame = rx_.front();
    rx_.pop_front();
    return true;
}

}  // namespace elm327
