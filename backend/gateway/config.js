/**
 * Gateway configuration settings.
 */
module.exports = {
  GATEWAY_PORT: Number(process.env.PORT || 5000),
  FASTAPI_URL: process.env.FASTAPI_URL || 'http://127.0.0.1:8000',
  ADMIN_TOKEN: process.env.ADMIN_TOKEN || '',
  ALLOWED_ORIGINS: (process.env.ALLOWED_ORIGINS || '').split(',').map((origin) => origin.trim()).filter(Boolean),
  HEARTBEAT_INTERVAL_MS: 5000,
  RATE_LIMIT_WINDOW_MS: Number(process.env.RATE_LIMIT_WINDOW_MS || 60_000),
  REGISTRATION_LIMIT: Number(process.env.REGISTRATION_LIMIT || 10),
  INGEST_LIMIT: Number(process.env.INGEST_LIMIT || 180),
  HEARTBEAT_LIMIT: Number(process.env.HEARTBEAT_LIMIT || 60)
};
