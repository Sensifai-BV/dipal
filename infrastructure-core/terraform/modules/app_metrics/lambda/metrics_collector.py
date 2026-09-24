import json
import os
import re
import urllib.request
from datetime import datetime, timezone

import boto3

cloudwatch = boto3.client("cloudwatch")

METRICS_URL = os.environ["METRICS_URL"]
NAMESPACE = os.environ.get("CW_NAMESPACE", "PhotoGear/Django")

# Simple metrics (gauges/counters) — no labels
SIMPLE_METRICS = {
    # Process metrics
    "process_virtual_memory_bytes": "ProcessVirtualMemoryBytes",
    "process_resident_memory_bytes": "ProcessResidentMemoryBytes",
    "process_cpu_seconds_total": "ProcessCpuSecondsTotal",
    "process_open_fds": "ProcessOpenFds",
    "process_max_fds": "ProcessMaxFds",
    # Python GC
    "python_gc_objects_collected_total": None,  # handled as labeled (generation)
    "python_gc_objects_uncollectable_total": None,
    "python_gc_collections_total": None,
    # Django HTTP totals
    "django_http_requests_before_middlewares_total": "HttpRequestsTotal",
    "django_http_responses_before_middlewares_total": "HttpResponsesTotal",
    "django_http_requests_unknown_latency_including_middlewares_total": "UnknownLatencyMiddlewaresTotal",
    "django_http_requests_unknown_latency_total": "UnknownLatencyTotal",
    "django_http_ajax_requests_total": "AjaxRequestsTotal",
    "django_http_responses_streaming_total": "StreamingResponsesTotal",
}

# Labeled metrics — single dimension
LABELED_METRICS = {
    "python_gc_objects_collected_total": {
        "cw_name": "GcObjectsCollectedTotal",
        "dim_key": "generation",
        "dim_name": "Generation",
    },
    "python_gc_objects_uncollectable_total": {
        "cw_name": "GcObjectsUncollectableTotal",
        "dim_key": "generation",
        "dim_name": "Generation",
    },
    "python_gc_collections_total": {
        "cw_name": "GcCollectionsTotal",
        "dim_key": "generation",
        "dim_name": "Generation",
    },
    "django_http_requests_total_by_method_total": {
        "cw_name": "RequestsByMethod",
        "dim_key": "method",
        "dim_name": "Method",
    },
    "django_http_responses_total_by_status_total": {
        "cw_name": "ResponsesByStatus",
        "dim_key": "status",
        "dim_name": "StatusCode",
    },
    "django_http_requests_total_by_transport_total": {
        "cw_name": "RequestsByTransport",
        "dim_key": "transport",
        "dim_name": "Transport",
    },
    "django_http_responses_total_by_templatename_total": {
        "cw_name": "ResponsesByTemplate",
        "dim_key": "templatename",
        "dim_name": "TemplateName",
    },
    "django_http_responses_total_by_charset_total": {
        "cw_name": "ResponsesByCharset",
        "dim_key": "charset",
        "dim_name": "Charset",
    },
    "django_http_exceptions_total_by_type_total": {
        "cw_name": "ExceptionsByType",
        "dim_key": "type",
        "dim_name": "Type",
    },
    "django_http_exceptions_total_by_view_total": {
        "cw_name": "ExceptionsByView",
        "dim_key": "view",
        "dim_name": "View",
    },
    "django_model_inserts_total": {
        "cw_name": "ModelInsertsTotal",
        "dim_key": "model",
        "dim_name": "Model",
    },
    "django_model_updates_total": {
        "cw_name": "ModelUpdatesTotal",
        "dim_key": "model",
        "dim_name": "Model",
    },
    "django_model_deletes_total": {
        "cw_name": "ModelDeletesTotal",
        "dim_key": "model",
        "dim_name": "Model",
    },
    "django_migrations_applied_total": {
        "cw_name": "MigrationsApplied",
        "dim_key": "connection",
        "dim_name": "Connection",
    },
    "django_migrations_unapplied_total": {
        "cw_name": "MigrationsUnapplied",
        "dim_key": "connection",
        "dim_name": "Connection",
    },
}

LINE_RE = re.compile(
    r'^(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>\S+)$'
)
LABEL_RE = re.compile(r'(\w+)="([^"]*)"')


def parse_labels(label_str):
    if not label_str:
        return {}
    return dict(LABEL_RE.findall(label_str))


def parse_prometheus(text):
    metrics = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        name = m.group("name")
        labels = parse_labels(m.group("labels"))
        try:
            value = float(m.group("value"))
        except ValueError:
            continue
        if name not in metrics:
            metrics[name] = []
        metrics[name].append({"labels": labels, "value": value})
    return metrics


def build_metric_data(metrics):
    metric_data = []
    now = datetime.now(timezone.utc)

    # Simple metrics (no dimensions)
    for prom_name, cw_name in SIMPLE_METRICS.items():
        if cw_name is None:
            continue
        entries = metrics.get(prom_name, [])
        for entry in entries:
            if not entry["labels"]:
                metric_data.append({
                    "MetricName": cw_name,
                    "Timestamp": now,
                    "Value": entry["value"],
                    "Unit": "None",
                })

    # Single-dimension labeled metrics
    for prom_name, config in LABELED_METRICS.items():
        entries = metrics.get(prom_name, [])
        for entry in entries:
            dim_value = entry["labels"].get(config["dim_key"], "unknown")
            metric_data.append({
                "MetricName": config["cw_name"],
                "Timestamp": now,
                "Value": entry["value"],
                "Unit": "Count",
                "Dimensions": [
                    {"Name": config["dim_name"], "Value": dim_value},
                ],
            })

    # --- Histogram-derived: Overall request latency (incl middlewares) ---
    latency_sum = metrics.get(
        "django_http_requests_latency_including_middlewares_seconds_sum", []
    )
    latency_count = metrics.get(
        "django_http_requests_latency_including_middlewares_seconds_count", []
    )
    if latency_sum and latency_count:
        s = latency_sum[0]["value"]
        c = latency_count[0]["value"]
        metric_data.append({
            "MetricName": "RequestLatencyTotalSum",
            "Timestamp": now,
            "Value": round(s * 1000, 2),
            "Unit": "Milliseconds",
        })
        metric_data.append({
            "MetricName": "RequestLatencyTotalCount",
            "Timestamp": now,
            "Value": c,
            "Unit": "Count",
        })
        if c > 0:
            metric_data.append({
                "MetricName": "RequestLatencyAvg",
                "Timestamp": now,
                "Value": round(s / c * 1000, 2),
                "Unit": "Milliseconds",
            })

    # Latency percentiles from histogram buckets
    latency_buckets = metrics.get(
        "django_http_requests_latency_including_middlewares_seconds_bucket", []
    )
    if latency_buckets and latency_count:
        total = latency_count[0]["value"]
        if total > 0:
            for percentile, label in [(0.50, "p50"), (0.90, "p90"), (0.95, "p95"), (0.99, "p99")]:
                target = total * percentile
                for bucket in latency_buckets:
                    le_val = bucket["labels"].get("le", "+Inf")
                    if le_val == "+Inf":
                        continue
                    try:
                        le = float(le_val)
                    except ValueError:
                        continue
                    if bucket["value"] >= target:
                        metric_data.append({
                            "MetricName": f"RequestLatency{label.upper()}",
                            "Timestamp": now,
                            "Value": round(le * 1000, 2),
                            "Unit": "Milliseconds",
                        })
                        break

    # --- Latency by view (sum / count per view+method) ---
    view_sum = metrics.get(
        "django_http_requests_latency_seconds_by_view_method_sum", []
    )
    view_count = metrics.get(
        "django_http_requests_latency_seconds_by_view_method_count", []
    )
    count_map = {}
    for entry in view_count:
        key = (entry["labels"].get("view", ""), entry["labels"].get("method", ""))
        count_map[key] = entry["value"]

    for entry in view_sum:
        view = entry["labels"].get("view", "unknown")
        method = entry["labels"].get("method", "unknown")
        key = (view, method)
        c = count_map.get(key, 0)
        if c > 0:
            metric_data.append({
                "MetricName": "LatencyByView",
                "Timestamp": now,
                "Value": round(entry["value"] / c * 1000, 2),
                "Unit": "Milliseconds",
                "Dimensions": [
                    {"Name": "View", "Value": view},
                    {"Name": "Method", "Value": method},
                ],
            })
        metric_data.append({
            "MetricName": "RequestCountByView",
            "Timestamp": now,
            "Value": c,
            "Unit": "Count",
            "Dimensions": [
                {"Name": "View", "Value": view},
                {"Name": "Method", "Value": method},
            ],
        })

    # --- Responses by status+view+method (multi-dimension) ---
    status_view_entries = metrics.get(
        "django_http_responses_total_by_status_view_method_total", []
    )
    for entry in status_view_entries:
        status = entry["labels"].get("status", "unknown")
        view = entry["labels"].get("view", "unknown")
        method = entry["labels"].get("method", "unknown")
        metric_data.append({
            "MetricName": "ResponsesByStatusViewMethod",
            "Timestamp": now,
            "Value": entry["value"],
            "Unit": "Count",
            "Dimensions": [
                {"Name": "StatusCode", "Value": status},
                {"Name": "View", "Value": view},
                {"Name": "Method", "Value": method},
            ],
        })

    # --- Request body size histogram ---
    body_sum = metrics.get("django_http_requests_body_total_bytes_sum", [])
    body_count = metrics.get("django_http_requests_body_total_bytes_count", [])
    if body_sum and body_count:
        metric_data.append({
            "MetricName": "RequestBodyBytesTotal",
            "Timestamp": now,
            "Value": body_sum[0]["value"],
            "Unit": "Bytes",
        })
        c = body_count[0]["value"]
        if c > 0:
            metric_data.append({
                "MetricName": "RequestBodyBytesAvg",
                "Timestamp": now,
                "Value": round(body_sum[0]["value"] / c, 2),
                "Unit": "Bytes",
            })

    # --- Response body size histogram ---
    resp_body_sum = metrics.get("django_http_responses_body_total_bytes_sum", [])
    resp_body_count = metrics.get("django_http_responses_body_total_bytes_count", [])
    if resp_body_sum and resp_body_count:
        metric_data.append({
            "MetricName": "ResponseBodyBytesTotal",
            "Timestamp": now,
            "Value": resp_body_sum[0]["value"],
            "Unit": "Bytes",
        })
        c = resp_body_count[0]["value"]
        if c > 0:
            metric_data.append({
                "MetricName": "ResponseBodyBytesAvg",
                "Timestamp": now,
                "Value": round(resp_body_sum[0]["value"] / c, 2),
                "Unit": "Bytes",
            })

    # --- Requests by view+transport+method (multi-dimension) ---
    view_transport = metrics.get(
        "django_http_requests_total_by_view_transport_method_total", []
    )
    for entry in view_transport:
        view = entry["labels"].get("view", "unknown")
        method = entry["labels"].get("method", "unknown")
        transport = entry["labels"].get("transport", "unknown")
        metric_data.append({
            "MetricName": "RequestsByViewTransportMethod",
            "Timestamp": now,
            "Value": entry["value"],
            "Unit": "Count",
            "Dimensions": [
                {"Name": "View", "Value": view},
                {"Name": "Method", "Value": method},
                {"Name": "Transport", "Value": transport},
            ],
        })

    return metric_data


def publish_metrics(metric_data):
    batch_size = 1000
    for i in range(0, len(metric_data), batch_size):
        batch = metric_data[i : i + batch_size]
        cloudwatch.put_metric_data(Namespace=NAMESPACE, MetricData=batch)
        print(f"Published {len(batch)} metrics to {NAMESPACE}")


def handler(event, context):
    try:
        req = urllib.request.Request(METRICS_URL, headers={"User-Agent": "MetricsCollector/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
    except Exception as e:
        print(f"Failed to fetch metrics from {METRICS_URL}: {e}")
        raise

    metrics = parse_prometheus(text)
    print(f"Parsed {len(metrics)} metric families")

    metric_data = build_metric_data(metrics)
    print(f"Built {len(metric_data)} CloudWatch metric data points")

    if metric_data:
        publish_metrics(metric_data)

    return {"statusCode": 200, "body": json.dumps({"metrics_published": len(metric_data)})}
