// Instrumentación OpenTelemetry (OTLP) -> OpenObserve
// Se activa solo si existe OTLP_ENDPOINT (en la EC2). En local y en CI queda desactivada.
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-proto');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-proto');
const { OTLPLogExporter } = require('@opentelemetry/exporter-logs-otlp-proto');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const { BatchLogRecordProcessor } = require('@opentelemetry/sdk-logs');
const { HttpInstrumentation } = require('@opentelemetry/instrumentation-http');
const { ExpressInstrumentation } = require('@opentelemetry/instrumentation-express');
const { trace, metrics, logs, SeverityNumber, SpanStatusCode } = require('@opentelemetry/api');

process.env.OTEL_SERVICE_NAME = process.env.OTEL_SERVICE_NAME || 'proyecto-api';

const endpoint = process.env.OTLP_ENDPOINT; // ej: http://host.docker.internal:5080/api/default
let sdk = null;

if (endpoint) {
  const auth = 'Basic ' + Buffer.from(`${process.env.OTLP_USER}:${process.env.OTLP_PASS}`).toString('base64');
  const headers = { Authorization: auth };

  sdk = new NodeSDK({
    traceExporter: new OTLPTraceExporter({ url: `${endpoint}/v1/traces`, headers }),
    metricReaders: [new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter({ url: `${endpoint}/v1/metrics`, headers }),
      exportIntervalMillis: Number(process.env.OTLP_METRIC_INTERVAL_MS || 10000),
    })],
    logRecordProcessors: [
      new BatchLogRecordProcessor({
        exporter: new OTLPLogExporter({ url: `${endpoint}/v1/logs`, headers: { ...headers, 'stream-name': 'app_logs' } }),
      }),
    ],
    instrumentations: [
      new HttpInstrumentation(),
      new ExpressInstrumentation({ ignoreLayersType: ['middleware'] }),
    ],
  });
  sdk.start();

  const stop = () => sdk.shutdown().finally(() => process.exit(0));
  process.on('SIGTERM', stop);
  process.on('SIGINT', stop);
}

// ---------------------------------------------------------------- Logs
function log(level, body, attributes = {}) {
  const sev = { INFO: SeverityNumber.INFO, WARN: SeverityNumber.WARN, ERROR: SeverityNumber.ERROR };
  logs.getLogger('app').emit({
    severityNumber: sev[level] || SeverityNumber.INFO,
    severityText: level,
    body,
    attributes,
  });
  console.log(JSON.stringify({ ts: new Date().toISOString(), level, message: body, ...attributes }));
}

function logError(err, req) {
  const span = trace.getActiveSpan();
  if (span) {
    span.recordException(err);
    span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
  }
  log('ERROR', err.message, {
    stack: err.stack,
    method: req && req.method,
    url: req && req.originalUrl,
  });
}

// ---------------------------------------------------------------- Métricas por endpoint
const meter = metrics.getMeter('proyecto-api');
const reqCounter = meter.createCounter('http_requests_total', {
  description: 'Peticiones HTTP por endpoint, método y status code',
});
const reqDuration = meter.createHistogram('http_request_duration_ms', {
  description: 'Latencia de las peticiones HTTP en milisegundos',
  unit: 'ms',
});

function requestObserver(req, res, next) {
  const start = process.hrtime.bigint();
  const ctx = trace.getActiveSpan() && trace.getActiveSpan().spanContext();
  res.on('finish', () => {
    const ms = Number(process.hrtime.bigint() - start) / 1e6;
    const route = req.route ? req.baseUrl + req.route.path : 'static_o_sin_ruta';
    const attrs = { method: req.method, route, status_code: res.statusCode };
    reqCounter.add(1, attrs);
    reqDuration.record(ms, attrs);
    const level = res.statusCode >= 500 ? 'ERROR' : res.statusCode >= 400 ? 'WARN' : 'INFO';
    log(level, `${req.method} ${route} ${res.statusCode}`, {
      ...attrs,
      duration_ms: Math.round(ms * 100) / 100,
      url: req.originalUrl,
      trace_id: ctx && ctx.traceId,
      span_id: ctx && ctx.spanId,
    });
  });
  next();
}

// ---------------------------------------------------------------- Trazas de consultas SQLite
function traceDb(db) {
  const tracer = trace.getTracer('sqlite');
  const wrapStmt = (stmt, sql) =>
    new Proxy(stmt, {
      get(t, p) {
        if (p === 'get' || p === 'all' || p === 'run') {
          return (...args) =>
            tracer.startActiveSpan(
              `sqlite ${String(p)}`,
              {
                attributes: {
                  'db.system': 'sqlite',
                  'db.statement': sql,
                  'db.operation': sql.trim().split(/\s+/)[0].toUpperCase(),
                },
              },
              (span) => {
                try {
                  return t[p](...args);
                } catch (e) {
                  span.recordException(e);
                  span.setStatus({ code: SpanStatusCode.ERROR, message: e.message });
                  throw e;
                } finally {
                  span.end();
                }
              }
            );
        }
        const v = t[p];
        return typeof v === 'function' ? v.bind(t) : v;
      },
    });
  return new Proxy(db, {
    get(t, p) {
      if (p === 'prepare') return (sql) => wrapStmt(t.prepare(sql), sql);
      const v = t[p];
      return typeof v === 'function' ? v.bind(t) : v;
    },
  });
}

module.exports = { log, logError, requestObserver, traceDb, enabled: !!sdk };
