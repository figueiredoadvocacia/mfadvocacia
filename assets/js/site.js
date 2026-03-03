(function () {
  const LEAD_WEBHOOK_URL = "https://n8n.mfadvocacia.api.br/webhook/site-lead";
  const CHAT_WEBHOOK_URL = "https://n8n.mfadvocacia.api.br/webhook/senne-site";

  window.setArea = function setArea(area) {
    const el = document.getElementById("area_interesse");
    if (el) el.value = area || "";
  };

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
          throw new Error("Falha no envio");
        }

        networkForm.reset();
        setArea("");
        setFeedback("Mensagem enviada com sucesso", true);
      } catch (error) {
        setFeedback("Não foi possível enviar agora. Verifique sua conexão e tente novamente.", false);
      }
    });
  }

  const btn = document.getElementById("senne-btn");
  const box = document.getElementById("senne-box");
  const closeBtn = document.getElementById("senne-close");
  const log = document.getElementById("senne-log");
  const form = document.getElementById("senne-form");
  const input = document.getElementById("senne-input");

  if (!btn || !box || !closeBtn || !log || !form || !input) return;

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
        typingBubble.textContent = "Ops! O atendimento está indisponível no momento.";
        return;
      }

      const data = await response.json().catch(function () { return {}; });
      const reply = data.reply || data.resposta || data.output || data.message || "Recebi sua mensagem e vou te responder em instantes.";
      typingBubble.textContent = reply;
    } catch (error) {
      clearTimeout(timeout);
      typingBubble.textContent = error.name === "AbortError"
        ? "A resposta demorou demais. Tente novamente em instantes."
        : "Falha de conexão com o atendimento. Tente novamente.";
    }
  });
})();
