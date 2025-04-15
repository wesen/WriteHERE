# Python Tracing with Jaeger and OpenTelemetry

This tutorial explains how to implement distributed tracing in Python applications using Jaeger and OpenTelemetry.

## Table of Contents

1. [Introduction](#introduction)
2. [Jaeger Tracing](#jaeger-tracing)
   - [Setting up Jaeger](#setting-up-jaeger)
   - [Using Jaeger Client in Python](#using-jaeger-client-in-python)
   - [Example Application](#example-application-jaeger)
3. [OpenTelemetry Tracing](#opentelemetry-tracing)
   - [Setting up OpenTelemetry](#setting-up-opentelemetry)
   - [Using OpenTelemetry in Python](#using-opentelemetry-in-python)
   - [Example Application](#example-application-opentelemetry)
4. [Dockerfiles](#dockerfiles)
   - [Jaeger Dockerfile](#jaeger-dockerfile)
   - [OpenTelemetry Dockerfile](#opentelemetry-dockerfile)
5. [Running the Examples](#running-the-examples)

## Introduction

Distributed tracing helps you understand how requests flow through your microservices architecture. Jaeger and OpenTelemetry are two popular frameworks for implementing distributed tracing:

- **Jaeger**: An open-source end-to-end distributed tracing system originally developed by Uber.
- **OpenTelemetry**: An observability framework for cloud-native software that provides vendor-agnostic APIs, libraries, and agents to collect distributed traces and metrics.

**Note**: Jaeger clients have been deprecated in favor of OpenTelemetry. The Jaeger client libraries are in maintenance mode, and for new applications, it's recommended to use OpenTelemetry SDKs.

## Jaeger Tracing

### Setting up Jaeger

You can run Jaeger using Docker:

```bash
docker run -d --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 5775:5775/udp \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 14250:14250 \
  -p 14268:14268 \
  -p 14269:14269 \
  -p 9411:9411 \
  jaegertracing/all-in-one:1.35
```

The Jaeger UI will be available at http://localhost:16686.

### Using Jaeger Client in Python

First, install the Jaeger client:

```bash
pip install jaeger-client
```

### Example Application (Jaeger)

Create a file named `jaeger_example.py`:

```python
import logging
import time
import requests
from jaeger_client import Config
from opentracing.ext import tags
from opentracing.propagation import Format

def init_tracer(service_name):
    config = Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
            'local_agent': {
                'reporting_host': 'localhost',
                'reporting_port': 6831,
            }
        },
        service_name=service_name,
        validate=True,
    )
    return config.initialize_tracer()

def make_request(tracer, url):
    with tracer.start_span('make_request') as span:
        span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
        span.set_tag(tags.HTTP_METHOD, 'GET')
        span.set_tag(tags.HTTP_URL, url)

        headers = {}
        tracer.inject(span.context, Format.HTTP_HEADERS, headers)

        try:
            response = requests.get(url, headers=headers)
            span.set_tag(tags.HTTP_STATUS_CODE, response.status_code)
            return response.text
        except Exception as e:
            span.set_tag(tags.ERROR, True)
            span.log_kv({'event': 'error', 'error.object': e})
            raise

def main():
    tracer = init_tracer('jaeger-example')

    with tracer.start_span('main_process') as span:
        span.log_kv({'event': 'Starting application'})

        # Simulate some work
        time.sleep(0.1)

        # Make a request
        try:
            result = make_request(tracer, 'https://httpbin.org/get')
            span.log_kv({'event': 'Request successful', 'value': result[:100] + '...'})
        except Exception as e:
            span.set_tag(tags.ERROR, True)
            span.log_kv({'event': 'error', 'error.object': e})

        # More work
        time.sleep(0.1)
        span.log_kv({'event': 'Finished application'})

    # Ensure spans are flushed
    time.sleep(2)
    tracer.close()

if __name__ == "__main__":
    logging.getLogger('').handlers = []
    logging.basicConfig(level=logging.INFO)
    main()
```

## OpenTelemetry Tracing

### Setting up OpenTelemetry

You can use the same Jaeger instance as above for the backend, as OpenTelemetry can export to Jaeger.

### Using OpenTelemetry in Python

Install the required packages:

```bash
pip install opentelemetry-api \
            opentelemetry-sdk \
            opentelemetry-exporter-jaeger \
            opentelemetry-instrumentation-requests
```

### Example Application (OpenTelemetry)

Create a file named `opentelemetry_example.py`:

```python
import time
import logging
import requests

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure the tracer
def configure_tracer():
    resource = Resource(attributes={
        SERVICE_NAME: "opentelemetry-example"
    })

    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="localhost",
        agent_port=6831,
    )

    # Create a BatchSpanProcessor and add the exporter to it
    span_processor = BatchSpanProcessor(jaeger_exporter)
    tracer_provider.add_span_processor(span_processor)

    # Instrument requests library
    RequestsInstrumentor().instrument()

    return tracer_provider

def make_request(url):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("make_request") as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", url)

        try:
            response = requests.get(url)
            span.set_attribute("http.status_code", response.status_code)
            return response.text
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise

def main():
    # Configure the tracer
    tracer_provider = configure_tracer()
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("main_process") as span:
        span.add_event("Starting application")

        # Simulate some work
        time.sleep(0.1)

        # Make a request
        try:
            result = make_request("https://httpbin.org/get")
            span.add_event("Request successful", {
                "result": result[:100] + "..."
            })
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))

        # More work
        time.sleep(0.1)
        span.add_event("Finished application")

    # Ensure all spans are exported
    time.sleep(2)
    # Shutdown tracer provider
    tracer_provider.shutdown()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

## Dockerfiles

### Jaeger Dockerfile

Create a file named `Dockerfile.jaeger`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements-jaeger.txt .
RUN pip install --no-cache-dir -r requirements-jaeger.txt

# Copy application code
COPY jaeger_example.py .

# Run the application
CMD ["python", "jaeger_example.py"]
```

Create a `requirements-jaeger.txt` file:

```
jaeger-client==4.8.0
requests==2.28.2
```

### OpenTelemetry Dockerfile

Create a file named `Dockerfile.opentelemetry`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements-opentelemetry.txt .
RUN pip install --no-cache-dir -r requirements-opentelemetry.txt

# Copy application code
COPY opentelemetry_example.py .

# Run the application
CMD ["python", "opentelemetry_example.py"]
```

Create a `requirements-opentelemetry.txt` file:

```
opentelemetry-api==1.18.0
opentelemetry-sdk==1.18.0
opentelemetry-exporter-jaeger==1.18.0
opentelemetry-instrumentation-requests==0.39b0
requests==2.28.2
```

## Running the Examples

### Running the Jaeger All-in-One Container

```bash
docker run -d --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 5775:5775/udp \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 14250:14250 \
  -p 14268:14268 \
  -p 14269:14269 \
  -p 9411:9411 \
  jaegertracing/all-in-one:1.35
```

### Running with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: "3"

services:
  jaeger:
    image: jaegertracing/all-in-one:1.35
    ports:
      - "5775:5775/udp"
      - "6831:6831/udp"
      - "6832:6832/udp"
      - "5778:5778"
      - "16686:16686"
      - "14250:14250"
      - "14268:14268"
      - "14269:14269"
      - "9411:9411"
    environment:
      - COLLECTOR_ZIPKIN_HOST_PORT=:9411

  jaeger-example:
    build:
      context: .
      dockerfile: Dockerfile.jaeger
    depends_on:
      - jaeger
    environment:
      - JAEGER_AGENT_HOST=jaeger
      - JAEGER_AGENT_PORT=6831

  opentelemetry-example:
    build:
      context: .
      dockerfile: Dockerfile.opentelemetry
    depends_on:
      - jaeger
    environment:
      - OTEL_EXPORTER_JAEGER_AGENT_HOST=jaeger
      - OTEL_EXPORTER_JAEGER_AGENT_PORT=6831
```

Run with:

```bash
docker-compose up -d
```

View traces at http://localhost:16686.

### Running Locally

For the Jaeger example:

```bash
python jaeger_example.py
```

For the OpenTelemetry example:

```bash
python opentelemetry_example.py
```

## References

- [Jaeger Documentation](https://www.jaegertracing.io/docs/1.30/client-libraries/)
- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [OpenTelemetry Jaeger Exporter](https://opentelemetry-python.readthedocs.io/en/latest/exporter/jaeger/jaeger.html)
