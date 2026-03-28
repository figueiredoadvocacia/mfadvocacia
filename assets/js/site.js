(function () {
  const config = window.MF_SITE_CONFIG || {};
  const integration = config.integration || {};

  function buildWebhookUrl(path, fallback) {
    if (!path) return fallback;
    if (/^https?:\/\//i.test(path)) return path;

    const base = (integration.n8nBaseUrl || "").replace(/\/$/, "");
    if (!base) return fallback;

    return base + (path.startsWith("/") ? path : "/" + path);
  }

  const LEAD_WEBHOOK_URL = buildWebhookUrl(
    integration.leadWebhookPath,
    "https://n8n.mfadvocacia.api.br/webhook/site-lead"
  );
  const CHAT_WEBHOOK_URL = buildWebhookUrl(
    integration.chatWebhookPath,
    "https://n8n.mfadvocacia.api.br/webhook/senne-entrada"
  );
  const SENNE_ENTRADA_URL = buildWebhookUrl(
    integration.senneEntradaPath,
    "https://n8n.mfadvocacia.api.br/webhook/senne-entrada"
  );
  const AGENDAMENTO_WEBHOOK_URL = "https://n8n.mfadvocacia.api.br/webhook/site-agendamento";

  document.documentElement.setAttribute("data-webhook-lead", LEAD_WEBHOOK_URL);
  document.documentElement.setAttribute("data-webhook-chat", CHAT_WEBHOOK_URL);
  document.documentElement.setAttribute("data-webhook-atendimento", SENNE_ENTRADA_URL);

  function buildErrorMessage(defaultMessage, response) {
    const status = response && response.status ? " (HTTP " + response.status + ")" : "";
    return defaultMessage + status;
  }

  function extractSenneReply(data) {
    if (typeof data === "string") return data.trim();

    if (Array.isArray(data)) {
      for (const item of data) {
        const reply = extractSenneReply(item);
        if (reply) return reply;
      }
      return "";
    }

    if (!data || typeof data !== "object") return "";

    const candidateKeys = [
      "reply",
      "resposta",
      "response",
      "output",
      "message",
      "text",
      "content",
      "answer",
    ];

    for (const key of candidateKeys) {
      const value = data[key];
      if (typeof value === "string" && value.trim()) return value.trim();
      if (Array.isArray(value) || (value && typeof value === "object")) {
        const nestedReply = extractSenneReply(value);
        if (nestedReply) return nestedReply;
      }
    }

    if (data.json) {
      const jsonReply = extractSenneReply(data.json);
      if (jsonReply) return jsonReply;
    }

    if (Array.isArray(data.data)) {
      const dataReply = extractSenneReply(data.data);
      if (dataReply) return dataReply;
    }

    return "";
  }

  window.setArea = function setArea(area) {
    const el = document.getElementById("area_interesse");
    if (el) el.value = area || "";
  };

  const leadForm = document.getElementById("leadForm");
  const leadStatus = document.getElementById("status");

  if (leadForm) {
    leadForm.addEventListener("submit", async function (event) {
      event.preventDefault();

      const nome = (leadForm.querySelector("#nome") && leadForm.querySelector("#nome").value.trim()) || "";
      const telefone =
        (leadForm.querySelector("#telefone") && leadForm.querySelector("#telefone").value.trim()) ||
        (leadForm.querySelector("#whatsapp") && leadForm.querySelector("#whatsapp").value.trim()) ||
        "";
      const instagram = (leadForm.querySelector("#instagram") && leadForm.querySelector("#instagram").value.trim()) || "";
      const areaInteresse =
        (leadForm.querySelector("#area") && leadForm.querySelector("#area").value.trim()) ||
        (leadForm.querySelector("#assunto") && leadForm.querySelector("#assunto").value.trim()) ||
        "";
      const mensagem = (leadForm.querySelector("#mensagem") && leadForm.querySelector("#mensagem").value.trim()) || "";
      const usuario_id = telefone.replace(/\D/g, "") || instagram.trim() || "site-" + Date.now();
      const submitButton = leadForm.querySelector('button[type="submit"]');

      if (!nome || !telefone || !areaInteresse || !mensagem) {
        if (leadStatus) {
          leadStatus.innerText = "Preencha todos os campos obrigatórios antes de enviar.";
        }
        return;
      }

      const payload = {
        nome: nome,
        telefone: telefone,
        instagram: instagram,
        usuario_id: usuario_id,
        area_interesse: areaInteresse,
        mensagem: mensagem,
        origem: "site",
        page_url: window.location.href,
      };

      if (leadStatus) leadStatus.innerText = "Enviando seu agendamento...";
      if (submitButton) submitButton.disabled = true;

      try {
        const response = await fetch(AGENDAMENTO_WEBHOOK_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const sendError = new Error("HTTP " + response.status);
          sendError.response = response;
          throw sendError;
        }

        leadForm.reset();
        if (leadStatus) {
          leadStatus.innerText = "Agendamento enviado com sucesso. Em breve entraremos em contato.";
        }
      } catch (error) {
        if (leadStatus) {
          leadStatus.innerText = buildErrorMessage("Falha ao enviar. Tente novamente em alguns minutos.", error && error.response);
        }
      } finally {
        if (submitButton) submitButton.disabled = false;
      }
    });
  }

  const networkForm = document.getElementById("network-form");
  const networkFeedback = document.getElementById("network-feedback");

  function setFeedback(message, isSuccess) {
    if (!networkFeedback) return;
    networkFeedback.style.display = "block";
    networkFeedback.textContent = message;
    networkFeedback.style.color = isSuccess ? "#2e7d32" : "#c62828";
  }

  function clearInvalidState(form) {
    [form.nome, form.email].forEach((field) => {
      if (!field) return;
      field.style.borderColor = "";
    });
  }

  if (networkForm) {
    networkForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      clearInvalidState(networkForm);
      if (networkFeedback) networkFeedback.style.display = "none";

      const nome = networkForm.nome.value.trim();
      const email = networkForm.email.value.trim();
      const mensagem = networkForm.mensagem.value.trim();
      const areaInteresse = (networkForm.area_interesse && networkForm.area_interesse.value.trim()) || "";

      let hasError = false;

      if (!nome) {
        networkForm.nome.style.borderColor = "#c62828";
        hasError = true;
      }

      if (!email) {
        networkForm.email.style.borderColor = "#c62828";
        hasError = true;
      }

      if (hasError) {
        setFeedback("Preencha os campos obrigatórios: nome e e-mail.", false);
        return;
      }

      const payload = {
        nome,
        email,
        mensagem,
        area_interesse: areaInteresse || null,
        origem: "site",
        pagina: window.location.pathname,
        dataHora: new Date().toISOString(),
      };

      setFeedback("Enviando mensagem...", true);

      try {
        const response = await fetch(LEAD_WEBHOOK_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const sendError = new Error("Falha no envio");
          sendError.response = response;
          throw sendError;
        }

        networkForm.reset();
        setArea("");
        setFeedback("Mensagem enviada com sucesso.", true);
      } catch (error) {
        setFeedback(buildErrorMessage("Não foi possível enviar agora. Verifique sua conexão e tente novamente.", error && error.response), false);
      }
    });
  }

  const qs = (s) => document.querySelector(s);
  const byId = (id) => document.getElementById(id);

  const btn = qs("[data-senne-btn]") || byId("senne-btn");
  const box = qs("[data-senne-chat]") || qs("[data-senne-box]") || byId("senne-box");
  const closeBtn = qs("[data-senne-close]") || byId("senne-close");
  const log = qs("[data-senne-output]") || qs("[data-senne-log]") || byId("senne-log");
  const form = qs("[data-senne-form]") || byId("senne-form");
  const input = qs("[data-senne-input]") || byId("senne-input");
  const send = qs("[data-senne-send]") || byId("senne-send");

  if (!(btn && box && closeBtn && log && form && input)) return;

  function addMsg(text, who) {
    const row = document.createElement("div");
    row.className = "senne-msg " + (who === "me" ? "me" : "bot");
    const bubble = document.createElement("div");
    bubble.className = "senne-bubble";
    bubble.textContent = text;
    row.appendChild(bubble);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }

  function toggle(open) {
    box.style.display = open ? "block" : "none";
    if (open && log.childElementCount === 0) {
      addMsg("Oi! Eu sou o SENNE. Me diga rapidamente o que você precisa 😊", "bot");
    }
    if (open) setTimeout(function () { input.focus(); }, 50);
  }

  btn.addEventListener("click", function () { toggle(true); });
  closeBtn.addEventListener("click", function () { toggle(false); });

  if (send && !send.hasAttribute("type")) {
    send.setAttribute("type", "submit");
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    addMsg(text, "me");
    input.value = "";

    const typingBubble = addMsg("digitando...", "bot");

    const payload = {
      mensagem: text,
      origem: "site",
      pagina: window.location.pathname,
      dataHora: new Date().toISOString(),
    };

    const controller = new AbortController();
    const timeout = setTimeout(function () {
      controller.abort();
    }, 12000);

    try {
      const response = await fetch(CHAT_WEBHOOK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        typingBubble.textContent = buildErrorMessage("Ops! O atendimento está indisponível no momento.", response);
        return;
      }

      const data = await response.json().catch(function () { return {}; });
      const reply = extractSenneReply(data) || "Recebi sua mensagem e vou te responder em instantes.";
      typingBubble.textContent = reply;
    } catch (error) {
      clearTimeout(timeout);
      typingBubble.textContent = error.name === "AbortError"
        ? "A resposta demorou demais. Tente novamente em instantes."
        : "Falha de conexão com o atendimento. Tente novamente.";
    }
  });

  const consentKey = "mf_cookie_consent_v1";
  if (!localStorage.getItem(consentKey)) {
    const banner = document.createElement("div");
    banner.className = "consent-banner";
    banner.innerHTML = '<p>Este site utiliza apenas recursos essenciais. Ao continuar, você concorda com a nossa <a href="privacidade.html">Política de Privacidade</a>.</p><ul class="actions"><li><button type="button" class="button small primary" data-consent-accept>Aceitar</button></li><li><button type="button" class="button small" data-consent-close>Fechar</button></li></ul>';
    document.body.appendChild(banner);

    const hideBanner = function (value) {
      localStorage.setItem(consentKey, value);
      banner.remove();
    };

    banner.querySelector("[data-consent-accept]").addEventListener("click", function () {
      hideBanner("accepted");
    });

    banner.querySelector("[data-consent-close]").addEventListener("click", function () {
      hideBanner("closed");
    });
  }
})();
