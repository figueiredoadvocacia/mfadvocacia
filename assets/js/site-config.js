(function () {
  const host = (window.location && window.location.hostname) || "";
  const isLocalEnvironment =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "0.0.0.0" ||
    host.endsWith(".local");

  const environment = isLocalEnvironment ? "local" : "production";

  const defaultsByEnvironment = {
    local: {
      n8nBaseUrl: "http://localhost:5678",
    },
    production: {
      n8nBaseUrl: "https://n8n.mfadvocacia.api.br",
    },
  };

  const defaultConfig = {
    environment,
    brand: "MF Advocacia",
    assistantName: "SENNE",
    integration: {
      n8nBaseUrl: defaultsByEnvironment[environment].n8nBaseUrl,
      leadWebhookPath: "/webhook/site-lead",
      chatWebhookPath: "/webhook/senne-site",
      senneEntradaPath: "/webhook/senne-entrada",
    },
    ollama: {
      internalUrl: "http://ollama:11434",
      textModel: "qwen2.5:7b",
      visionModel: "moondream:latest",
    },
    channels: {
      whatsapp: "https://wa.me/5592993972750",
      instagram: "https://www.instagram.com/mayanafigueiredoadv/",
    },
  };

  const existingConfig = window.MF_SITE_CONFIG || {};
  const overrideConfig = window.MF_SITE_CONFIG_OVERRIDES || {};

  window.MF_SITE_CONFIG = {
    ...defaultConfig,
    ...existingConfig,
    ...overrideConfig,
    integration: {
      ...defaultConfig.integration,
      ...(existingConfig.integration || {}),
      ...(overrideConfig.integration || {}),
    },
    ollama: {
      ...defaultConfig.ollama,
      ...(existingConfig.ollama || {}),
      ...(overrideConfig.ollama || {}),
    },
    channels: {
      ...defaultConfig.channels,
      ...(existingConfig.channels || {}),
      ...(overrideConfig.channels || {}),
    },
  };
})();
