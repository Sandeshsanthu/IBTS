# API gateway credentials.
resource "kubernetes_secret" "api_gateway" {
  metadata {
    name      = "api-gateway-secrets"
    namespace = kubernetes_namespace.ibts_app.metadata[0].name
  }

  data = {
    JWT_SECRET = var.jwt_secret
    API_KEY    = var.api_key
  }

  type = "Opaque"
}

# Shared runtime configuration for IBTS application services.
resource "kubernetes_config_map" "ibts_shared" {
  metadata {
    name      = "ibts-shared-config"
    namespace = kubernetes_namespace.ibts_app.metadata[0].name
  }

  data = {
    # AWS resources
    AWS_DEFAULT_REGION                  = var.aws_region
    DYNAMODB_TABLE_NAME_IDEMPOTENCY     = aws_dynamodb_table.idempotency_records.name
    DYNAMODB_TABLE_NAME_TRANSACTIONS    = aws_dynamodb_table.ibts_transactions.name
    ROUTING_TABLE_NAME                  = aws_dynamodb_table.routing_table.name
    SQS_QUEUE_NAME                      = aws_sqs_queue.settlement_events.name

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT         = "http://otel-collector-opentelemetry-collector.${kubernetes_namespace.ibts_observability.metadata[0].name}.svc.cluster.local:4318"
    OTEL_EXPORTER_OTLP_PROTOCOL         = "http/protobuf"
    OTEL_TRACES_EXPORTER                = "otlp"
    OTEL_METRICS_EXPORTER               = "none"
    OTEL_LOGS_EXPORTER                  = "none"
    OTEL_PYTHON_LOG_CORRELATION         = "true"

    # Internal services
    IDEMPOTENCY_GUARD_URL                = "http://idempotency-guard.${kubernetes_namespace.ibts_app.metadata[0].name}.svc.cluster.local:8080"
    PAYMENT_ROUTER_URL                  = "http://payment-router.${kubernetes_namespace.ibts_app.metadata[0].name}.svc.cluster.local:8081"
    BANK_ADAPTER_URL                    = "http://bank-adapter.${kubernetes_namespace.ibts_app.metadata[0].name}.svc.cluster.local:8082"
    BANK_ADAPTER_SEND_URL               = "http://bank-adapter.${kubernetes_namespace.ibts_app.metadata[0].name}.svc.cluster.local:8082/api/v1/adapter/send"
    PAYMENT_SWITCH_URL                  = "http://payment-switch.${kubernetes_namespace.ibts_app.metadata[0].name}.svc.cluster.local:8083"
    REDIS_HOST                          = "ibts-redis.${kubernetes_namespace.ibts_app.metadata[0].name}.svc.cluster.local"
    REDIS_PORT                          = "6379"
    MOCK_BANK_URL                       = "http://mock-bank-server.${kubernetes_namespace.ibts_app.metadata[0].name}.svc.cluster.local:8080"
  }
}

