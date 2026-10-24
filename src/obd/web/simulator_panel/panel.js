// Painel de controle do simulador: envia comandos pela API HTTP e mostra o WS /sim/stream.
"use strict";

const VARIAVEIS = {
  rpm: { rotulo: "Rotação (rpm)", min: 0, max: 7000, passo: 10 },
  speed: { rotulo: "Velocidade (km/h)", min: 0, max: 200, passo: 1 },
  coolant: { rotulo: "Arrefecimento (°C)", min: -40, max: 120, passo: 1 },
  throttle: { rotulo: "Borboleta (%)", min: 0, max: 100, passo: 0.5 },
  fuel: { rotulo: "Combustível (%)", min: 0, max: 100, passo: 0.5 },
  voltage: { rotulo: "Tensão (V)", min: 9, max: 16, passo: 0.05 },
};
const DTC_LINHAS_MAX = 200;
const MONITOR_LINHAS_MAX = 200;

const $ = (id) => document.getElementById(id);

function mostrarErro(msg) {
  $("erro").textContent = msg || "";
}

async function api(metodo, caminho, corpo) {
  const resp = await fetch(caminho, {
    method: metodo,
    headers: corpo ? { "Content-Type": "application/json" } : {},
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    const detalhe = Array.isArray(dados.detail)
      ? dados.detail.map((d) => d.msg).join("; ")
      : dados.detail;
    mostrarErro(`${resp.status}: ${detalhe || resp.statusText}`);
    return null;
  }
  mostrarErro("");
  return resp.json();
}

function criarVariaveis() {
  const pai = $("variaveis");
  for (const [nome, cfg] of Object.entries(VARIAVEIS)) {
    const linha = document.createElement("div");
    linha.className = "variavel";
    linha.dataset.nome = nome;
    linha.innerHTML = `
      <span class="rotulo">${cfg.rotulo}</span>
      <input type="range" min="${cfg.min}" max="${cfg.max}" step="${cfg.passo}">
      <output></output>
      <button type="button" class="auto">Automático</button>`;
    const faixa = linha.querySelector("input");
    faixa.addEventListener("input", () => {
      linha.querySelector("output").textContent = faixa.value;
    });
    faixa.addEventListener("change", () =>
      api("PUT", `/sim/override/${nome}`, { value: Number(faixa.value) })
    );
    linha.querySelector(".auto").addEventListener("click", () =>
      api("DELETE", `/sim/override/${nome}`)
    );
    pai.appendChild(linha);
  }
}

function atualizarVariaveis(estado) {
  for (const linha of document.querySelectorAll(".variavel")) {
    const nome = linha.dataset.nome;
    const faixa = linha.querySelector("input");
    const ativo = nome in estado.overrides;
    linha.classList.toggle("sobreposta", ativo);
    if (document.activeElement !== faixa) {
      faixa.value = estado.variaveis[nome];
    }
    linha.querySelector("output").textContent = Number(estado.variaveis[nome]).toFixed(2);
  }
}

// Não sobrescreve um controle que o usuário está arrastando (o estado chega a cada 100 ms).
function definirSeLivre(id, valor) {
  const campo = $(id);
  if (document.activeElement !== campo) {
    campo.value = valor;
    $(`${id}-v`).textContent = campo.value;
  }
}

function atualizarControles(estado) {
  const perfil = $("perfil");
  if (perfil.options.length !== estado.perfis.length) {
    perfil.replaceChildren(...estado.perfis.map((p) => new Option(p, p)));
  }
  perfil.value = estado.perfil;
  $("sem-resposta").checked = estado.sem_resposta;
  definirSeLivre("lat-min", estado.latencia.min);
  definirSeLivre("lat-max", estado.latencia.max);
  definirSeLivre("rede-drop", estado.rede.drop);
  definirSeLivre("rede-corrupt", estado.rede.corrupt);
  const lista = $("dtc-lista");
  const itens = [
    ...estado.dtcs.armazenados.map((c) => `${c} (armazenado)`),
    ...estado.dtcs.pendentes.map((c) => `${c} (pendente)`),
  ];
  lista.replaceChildren(...itens.slice(0, DTC_LINHAS_MAX).map((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    return li;
  }));
}

function mostrarQuadros(quadros) {
  const monitor = $("quadros");
  const linhas = quadros.map((q) => `${q.sentido} ${q.id.padEnd(4)} ${q.dados}`);
  const atual = monitor.textContent ? monitor.textContent.split("\n") : [];
  const todas = [...atual, ...linhas].slice(-MONITOR_LINHAS_MAX);
  monitor.textContent = todas.join("\n");
  monitor.scrollTop = monitor.scrollHeight;
}

function conectarStream() {
  const protocolo = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocolo}://${location.host}/sim/stream`);
  ws.onopen = () => {
    $("status").textContent = "conectado";
  };
  ws.onmessage = (evento) => {
    const msg = JSON.parse(evento.data);
    atualizarVariaveis(msg.estado);
    atualizarControles(msg.estado);
    mostrarQuadros(msg.quadros);
  };
  ws.onclose = () => {
    $("status").textContent = "desconectado, tentando de novo…";
    setTimeout(conectarStream, 1000);
  };
}

function ligarControles() {
  $("perfil").addEventListener("change", (e) =>
    api("POST", "/sim/profile", { name: e.target.value })
  );
  $("sem-resposta").addEventListener("change", (e) =>
    api("POST", "/sim/unresponsive", { on: e.target.checked })
  );
  $("reiniciar").addEventListener("click", () =>
    api("POST", "/sim/seed", {
      model: Number($("semente-modelo").value),
      ecu: Number($("semente-ecu").value),
    })
  );
  for (const id of ["lat-min", "lat-max"]) {
    $(id).addEventListener("input", () => ($(`${id}-v`).textContent = $(id).value));
  }
  $("lat-min").addEventListener("change", enviarLatencia);
  $("lat-max").addEventListener("change", enviarLatencia);
  for (const id of ["rede-drop", "rede-corrupt"]) {
    $(id).addEventListener("input", () => ($(`${id}-v`).textContent = $(id).value));
    $(id).addEventListener("change", enviarRede);
  }
  $("dtc-injetar").addEventListener("click", () =>
    api("POST", "/sim/dtc", {
      code: $("dtc-codigo").value.toUpperCase(),
      pending: $("dtc-pendente").checked,
    })
  );
  $("dtc-limpar").addEventListener("click", () => api("DELETE", "/sim/dtc"));
}

function enviarLatencia() {
  const min = Number($("lat-min").value);
  const max = Number($("lat-max").value);
  api("PUT", "/sim/latency", { min, max: Math.max(min, max) });
}

function enviarRede() {
  api("PUT", "/sim/network", {
    drop: Number($("rede-drop").value),
    corrupt: Number($("rede-corrupt").value),
  });
}

criarVariaveis();
ligarControles();
conectarStream();
