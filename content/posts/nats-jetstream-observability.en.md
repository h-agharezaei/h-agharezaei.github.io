+++
date = '2027-01-01T10:00:00+03:30'
draft = false
title = 'Observability for JetStream: metrics, logs and traces'
seoTitle = 'JetStream Observability: Metrics, Logs, Traces'
description = 'Add Prometheus metrics, structured slog logs and W3C trace context propagation through NATS headers to a Go JetStream worker, with real output.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "observability", "metrics", "tracing", "prometheus", "slog", "opentelemetry"]
cover = { image = "/images/covers/nats-jetstream-observability.png", alt = "Observability for JetStream: metrics, logs and traces", hiddenInSingle = true }
+++

In the [previous post](/posts/go-graceful-shutdown-workers/) the worker learned to stop cleanly, but when something goes wrong we still mostly guess. A queue makes this worse: the publisher and the worker never talk directly, so a slow or failing message leaves no obvious trail. This post adds the three usual signals: **metrics** (is it healthy right now?), **logs** (what happened to this message?) and **traces** (how did one request travel from publisher to worker?).

The demo is one local Go program: an embedded `nats-server` v2.15.1 with JetStream, `nats.go` v1.54.0, `prometheus/client_golang` v1.23.2 and OpenTelemetry v1.43.0, on Go 1.26. A publisher sends about 60 jobs per second to a single serial worker. Every 10th job fails on its first delivery. For the lag numbers themselves see [the scaling post](/posts/nats-jetstream-scaling-lag/); for `slog` basics see [config, logging and errors](/posts/go-config-logging-errors/).

## Metrics: three questions, three instruments

```go
processed = prometheus.NewCounterVec(prometheus.CounterOpts{
    Name: "worker_messages_total"}, []string{"result"})
duration = prometheus.NewHistogram(prometheus.HistogramOpts{
    Name: "worker_process_seconds",
    Buckets: []float64{0.01, 0.025, 0.05, 0.1, 0.25}})
pending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_pending"})
ackPending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_ack_pending"})
```

The worker does `processed.WithLabelValues(result).Inc()` and `duration.Observe(...)` after each message, where `result` is `ok`, `failed` or `redelivered_ok` (decided from `Metadata().NumDelivered`). The lag gauges are not touched by the worker. A separate goroutine samples `ConsumerInfo` twice a second:

```go
for ctx.Err() == nil {
    if ci, err := js.ConsumerInfo("JOBS", "w"); err == nil {
        pending.Set(float64(ci.NumPending))
        ackPending.Set(float64(ci.NumAckPending))
    }
    time.Sleep(500 * time.Millisecond)
}
```

With the worker under load I ran `curl localhost:9100/metrics | grep -E '^(worker_|consumer_)'` (trimmed):

```text
consumer_num_ack_pending 5
consumer_num_pending 162
worker_messages_total{result="failed"} 17
worker_messages_total{result="ok"} 155
worker_messages_total{result="redelivered_ok"} 13
worker_process_seconds_bucket{le="0.025"} 75
worker_process_seconds_bucket{le="0.05"} 181
worker_process_seconds_bucket{le="+Inf"} 185
worker_process_seconds_sum 5.429341470999997
worker_process_seconds_count 185
```

Which metric answers which question:

- **Is it slow?** The histogram. Sum divided by count is the mean (here about 29 ms); the buckets give percentiles. (The machine was busy, load average near 10, so treat the absolute times as rough.)
- **Is it failing?** The counter. The share of `failed` and `redelivered_ok` against the total.
- **Is it backing up?** `consumer_num_pending`. 162 here means the publisher is faster than this single worker. `consumer_num_ack_pending` is different: messages delivered but not acked yet, so a high value that does not move points to stuck or slow handlers.

Careful with labels: every distinct label combination is a separate time series. Labeling by message ID or user ID creates unbounded series and can take your Prometheus down. Keep labels to small fixed sets (`result`, `subject`) and put per-message detail in logs and traces.

## Logs: one JSON line per attempt

I use `log/slog` with a JSON handler and attach the message coordinates once with `log.With(...)`: `trace_id`, `stream_seq`, `delivery` and `subject`. The `time` field is stripped here only to keep the output short. Real lines:

```json
{"level":"ERROR","msg":"processing failed, will retry","trace_id":"9b02d5c801cb5d9b61787ea8fcf97a45","stream_seq":10,"delivery":1,"subject":"jobs.run","err":"upstream timeout"}
{"level":"INFO","msg":"processed","trace_id":"9b02d5c801cb5d9b61787ea8fcf97a45","stream_seq":10,"delivery":2,"subject":"jobs.run","result":"redelivered_ok"}
```

`stream_seq` identifies the message in the stream, and `delivery` tells you which attempt this is. Together with `trace_id` you can follow one message across retries.

## Traces: context through NATS headers

NATS messages carry headers, so the W3C `traceparent` header fits naturally. The publisher starts a span and injects the context into `msg.Header`; the worker extracts it and starts a child span. I used the real OpenTelemetry SDK with the stdout exporter (not a hand-written header), and `propagation.TraceContext{}` does the formatting:

```go
// publisher
pctx, span := tracer.Start(ctx, "publish jobs.run", trace.WithSpanKind(trace.SpanKindProducer))
msg := nats.NewMsg("jobs.run")
otel.GetTextMapPropagator().Inject(pctx, propagation.HeaderCarrier(msg.Header))
js.PublishMsg(msg)
span.End()

// worker
pctx := otel.GetTextMapPropagator().Extract(ctx, propagation.HeaderCarrier(m.Header))
_, span := tracer.Start(pctx, "process jobs.run", trace.WithSpanKind(trace.SpanKindConsumer))
```

`nats.Header` is a `map[string][]string`, so it works with `propagation.HeaderCarrier` directly. The worker logged trace `9b02d5c8...` for job 10, and filtering the exporter output for that ID gave:

```text
publish jobs.run  span 3eb7ba61771c4eb6  parent 0000000000000000
process jobs.run  span 2ae949162024bb0b  parent 3eb7ba61771c4eb6
process jobs.run  span 5c206277c8cc28eb  parent 3eb7ba61771c4eb6
```

Same trace ID on both sides, and the failed first attempt and the retry are two child spans of the same publish span.

## What to alert on

Without inventing numbers: alert on `consumer_num_pending` that keeps growing instead of settling (the worker cannot keep up), on a rising share of `failed` or `redelivered_ok`, and on any messages in the dead-letter stream from [the retry post](/posts/nats-jetstream-retry-dlq/), where the depth should normally be zero. Pick thresholds from your own baseline.

## A few things to watch

- `ConsumerInfo` is a request to the server; sample every second or so, not per message.
- The gauges are only as fresh as the sampling interval.
- Histogram buckets are fixed at creation. Choose them around your real latencies.
- Propagating the header only helps if every hop also extracts it; a service that republishes without copying headers breaks the trace.
- The stdout exporter is for demos. In production you export to a collector.

## What's next

Everything here ran against an embedded server, which also makes testing easy. The next post is about testing JetStream services with an embedded nats-server.
