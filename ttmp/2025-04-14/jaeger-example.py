import logging
import time
import requests
from typing import Dict, Any, Optional

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.semconv.trace import SpanAttributes


def init_tracer(service_name: str) -> None:
    """Initialize the OpenTelemetry tracer with OTLP exporter for Jaeger"""

    # Create a resource with service name
    resource = Resource.create({"service.name": service_name})

    # Set up the trace provider with the resource
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Create OTLP exporter pointing to Jaeger
    # Jaeger accepts OTLP on port 4317 (gRPC)
    otlp_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)

    # Create a BatchSpanProcessor and add the exporter to it
    span_processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(span_processor)

    return trace.get_tracer(__name__)


def say_hello(tracer: trace.Tracer) -> str:
    with tracer.start_as_current_span("say_hello") as span:
        # Set span attributes (equivalent to tags in OpenTracing)
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, "https://www.jaegertracing.io/")
        span.set_attribute("span.kind", "client")

        # Create headers for context propagation
        headers: Dict[str, str] = {}
        TraceContextTextMapPropagator().inject(headers)

        try:
            response = requests.get("https://www.jaegertracing.io/", headers=headers)
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status_code)
            return response.text
        except Exception as e:
            # Record error information
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise


def main() -> None:
    tracer = init_tracer("jaeger-example")

    with tracer.start_as_current_span("main_process") as span:
        # Log events to the span
        span.add_event("Starting application")

        time.sleep(0.1)

        try:
            result = say_hello(tracer)
            span.add_event("Request successful", {"value": result[:100] + "..."})
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))

        time.sleep(0.1)
        span.add_event("Finished application")


if __name__ == "__main__":
    logging.getLogger("").handlers = []
    logging.basicConfig(level=logging.INFO)
    main()
