/*
  Copy this file to assets/js/site-config.override.js in production when you need
  to override runtime values without changing site-config.js.

  Then include the copied file BEFORE assets/js/site-config.js in pages where needed.
*/
window.MF_SITE_CONFIG_OVERRIDES = {
  environment: "production",
  integration: {
    n8nBaseUrl: "https://n8n.mfadvocacia.api.br",
    leadWebhookPath: "/webhook/site-lead",
    chatWebhookPath: "/webhook/senne-site",
    senneEntradaPath: "/webhook/senne-entrada",
  },
};
