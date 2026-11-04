+++
date = '2027-01-01T10:00:00+03:30'
draft = false
title = 'Observability for JetStream: metrics, logs and traces'
seoTitle = 'JetStream Observability: Metrics, Logs, Traces'
description = 'Add Prometheus metrics, structured slog logs and W3C trace context propagation through NATS headers to a Go JetStream worker, with real output.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "observability", "metrics", "tracing", "prometheus", "slog", "opentelemetry"]
cover = { image = "/images/covers/nats-jetstream-observability.png", alt = "Observability for JetStream: metrics, logs and traces", hiddenInSingle = true }
+++

Picture a queue worker that has been running quietly for a week. One Monday morning someone notices that emails sent "on signup" arrive an hour late. The worker never crashed and there is no error in any log. It simply fell behind: messages came in faster than it could handle them, and the backlog grew a little more every minute. Nobody was looking at the one number that would have shown it.

A queue makes this kind of problem easy to miss. The publisher and the worker never talk to each other directly, so a slow or failing message leaves no obvious trail. The worker from the [previous post](/posts/go-graceful-shutdown-workers/) now stops cleanly, but that does not tell us what it is doing while it runs. In this post we add the three usual signals that answer that:

- **Metrics** answer "is it healthy right now?" They are numbers sampled over time.
- **Logs** answer "what happened to this particular message?" They are lines of text, one per event.
- **Traces** answer "how did one request travel from the publisher to the worker?" They link the work done on both sides into one story.

> The demo is one local Go program. I re-ran it with Go 1.27, an embedded `nats-server` v2.15.1 with {{< term "jetstream" "JetStream" >}}, `nats.go` v1.54.0, `prometheus/client_golang` v1.23.2 and OpenTelemetry v1.43.0. A publisher sends about 60 jobs per second to a single worker that handles one job at a time and sleeps 5 to 49 ms per job at random. Every 10th job fails on its first delivery. The program runs for 9 seconds, and everything below is its real output.

For what the consumer is and how the lag numbers come about, see [the scaling post](/posts/nats-jetstream-scaling-lag/). For `slog` basics, see [config, structured logging and errors](/posts/go-config-logging-errors/).

## Metrics: three questions, three instruments

Before any code, here is the idea in plain words. A metric is a number that the program keeps up to date and that a monitoring system (here Prometheus) reads every few seconds. Because it is read again and again, you can draw it over time and alert on it. Prometheus has a few types of metrics. We need three:

- A **counter** only goes up: "how many messages have been processed so far". You usually look at how fast it grows.
- A **gauge** goes up and down: "how many messages are waiting right now".
- A **histogram** counts observations into buckets, for example "how many jobs took up to 25 ms, up to 50 ms, and so on". From the buckets you can estimate a {{< term "percentile" "percentile" >}}, such as "95% of jobs took less than 50 ms".

Our worker needs one of each:

```go
processed = prometheus.NewCounterVec(prometheus.CounterOpts{
    Name: "worker_messages_total"}, []string{"result"})
duration = prometheus.NewHistogram(prometheus.HistogramOpts{
    Name: "worker_process_seconds",
    Buckets: []float64{0.01, 0.025, 0.05, 0.1, 0.25}})
pending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_pending"})
ackPending = prometheus.NewGauge(prometheus.GaugeOpts{Name: "consumer_num_ack_pending"})
```

After each message the worker calls `processed.WithLabelValues(result).Inc()` and `duration.Observe(...)`. The `result` label is `ok`, `failed` or `redelivered_ok`; the worker decides it from `Metadata().NumDelivered`, which says how many times the server has delivered this message so far. The `result` label splits one counter into three series: how many succeeded, how many failed, and how many succeeded on a retry.

The two lag gauges are different. The worker cannot know how many messages are waiting behind it, but the server does. So a separate goroutine asks the server twice a second, with `ConsumerInfo`:

```go
for ctx.Err() == nil {
    if ci, err := js.ConsumerInfo("JOBS", "w"); err == nil {
        pending.Set(float64(ci.NumPending))
        ackPending.Set(float64(ci.NumAckPending))
    }
    time.Sleep(500 * time.Millisecond)
}
```

`NumPending` is the number of messages in the stream that the server has not delivered to the consumer yet. `NumAckPending` is the number it has delivered but that have not been acknowledged yet.

While the program ran, I read the metrics endpoint with `curl 127.0.0.1:<port>/metrics | grep -E '^(worker_|consumer_)'`. This is the real output, taken about six seconds in (I left out the `0.1` and `0.25` buckets, which show 191, the same as `+Inf`):

```text
consumer_num_ack_pending 5
consumer_num_pending 139
worker_messages_total{result="failed"} 17
worker_messages_total{result="ok"} 160
worker_messages_total{result="redelivered_ok"} 14
worker_process_seconds_bucket{le="0.01"} 22
worker_process_seconds_bucket{le="0.025"} 89
worker_process_seconds_bucket{le="0.05"} 188
worker_process_seconds_bucket{le="+Inf"} 191
worker_process_seconds_sum 5.329840419
worker_process_seconds_count 191
```

Let me read it line by line.

- `consumer_num_pending 139`: 139 messages are waiting in the stream. The publisher sends about 60 per second, and one worker with 5 to 49 ms per job cannot keep up with that, so this number keeps growing while the program runs. This is exactly the "worker fell behind" signal from the opening.
- `consumer_num_ack_pending 5`: five messages were delivered and are not acknowledged yet. One of them is the message being processed right now. I believe most of the rest are failed messages waiting out their one-second `NakWithDelay` before the server redelivers them, because the counters show 17 failures and only 14 retries done. The gauge is sampled every half second, so it can be a little older than the counters.
- `worker_messages_total`: 191 messages in total. 17 failed on the first delivery, 160 succeeded, and 14 of the failed ones were already retried successfully. The other 3 were still waiting for their retry when I looked.
- Buckets are cumulative: `le="0.05"` means "took at most 0.05 seconds" and counts every job up to that limit. So 188 of 191 jobs took 50 ms or less, and 89 took 25 ms or less. For a rough 95th percentile, take 95% of 191, about 182, and find the first bucket that holds that many: it is the 0.05 bucket. So "95% of jobs took 50 ms or less".
- `sum / count` is the mean: 5.33 s divided by 191 is about 28 ms. That is what we expect, since the handler sleeps between 5 and 49 ms. The machine was busy while I ran this, so I do not publish exact latency numbers; the counts above are the reliable part.

So which metric answers which question:

- **Is it slow?** The histogram.
- **Is it failing?** The counter: the share of `failed` and `redelivered_ok` out of the total.
- **Is it backing up?** `consumer_num_pending`. A high `consumer_num_ack_pending` that does not go down is a different problem: messages that were handed out and never acknowledged point to stuck or slow handlers.

A pitfall with labels: every different combination of label values is a separate **time series**, a separate line that Prometheus must store. If you label by message ID or user ID, the number of series grows without limit, and that can take your Prometheus down. Keep labels to small fixed sets such as `result` or `subject`, and put the per-message details in logs and traces.

## Logs: one JSON line per attempt

Metrics tell us that something is wrong, but not which message. For that we need logs. I use `log/slog` with its JSON handler, which writes each log line as a JSON object, so a log system can search by field. The trick is to attach the message coordinates once, with `log.With(...)`, so every line for that message carries them: `trace_id`, `stream_seq` (the message's position in the stream), `delivery` (which attempt this is) and `subject`. I strip the `time` field here only to keep the output short.

These are the real lines for job 10 of this run. The first is its failed first attempt and the second is the retry, about a second later, after other jobs had been processed in between:

```json
{"level":"ERROR","msg":"processing failed, will retry","trace_id":"bf9fafe748b0075f7053c4cf8e65c3d3","stream_seq":10,"delivery":1,"subject":"jobs.run","err":"upstream timeout"}
{"level":"INFO","msg":"processed","trace_id":"bf9fafe748b0075f7053c4cf8e65c3d3","stream_seq":10,"delivery":2,"subject":"jobs.run","result":"redelivered_ok"}
```

`stream_seq` identifies the message and `delivery` says which attempt we are looking at. With the same `trace_id` on both lines, you can search for one value and follow the message across retries. The trace ID is generated by the publisher; the next section shows how it reaches the worker.

## Traces: carrying context through NATS headers

A trace connects the work done in different programs for one request. It is made of **spans**, where a {{< term "tracing-span" "span" >}} is one timed piece of work, such as "publish this message" or "process this message". Each span has an ID, and a child span records its parent's ID. For the worker's span to be a child of the publisher's span, the publisher must pass its IDs along with the message. That is called propagating the context.

NATS messages can carry headers, just like HTTP requests, so the W3C `traceparent` header is a natural place for it. The standard format of that header is the version, trace ID, span ID and flags, joined with dashes. The publisher starts a span and injects the context into `msg.Header`. The worker extracts it and starts a child span. I used the real OpenTelemetry SDK with its stdout exporter (an exporter that prints finished spans as JSON), not a hand-written header, and `propagation.TraceContext{}` does the formatting:

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

`nats.Header` is a `map[string][]string`, which has the same shape as `http.Header`, so it works with `propagation.HeaderCarrier` directly.

The worker logged trace `bf9fafe7...` for job 10. I filtered the exporter's output for that trace ID and printed the span name, span ID and parent ID of each span:

```text
publish jobs.run  span a7ea4be0b56bf913  parent 0000000000000000
process jobs.run  span 0f90631928129dbb  parent a7ea4be0b56bf913
process jobs.run  span 9ed57a5cf1fb5a99  parent a7ea4be0b56bf913
```

The first line is the publisher's span. A parent of all zeros means "no parent": it is the root. Both `process` spans name the publisher's span as their parent. They are the failed first attempt and the successful retry. So one trace shows the whole life of job 10: published once, processed twice. The trace and span IDs are random, so you will see different ones on every run.

## What to alert on

Metrics are only useful if someone is told when they look bad. I will not invent thresholds, because they depend on your system, but these are the three signals I would watch:

- `consumer_num_pending` that keeps growing instead of settling at a level. A short spike is normal. A line that only goes up means the worker cannot keep up.
- A rising share of `failed` or `redelivered_ok` out of all messages.
- Any message in the dead-letter stream from [the retry post](/posts/nats-jetstream-retry-dlq/). Its depth should normally be zero, so any growth is worth a look.

Choose the thresholds from your own baseline: watch the normal values for a while, then alert on clear departures from them. Alerts that fire all the time teach people to ignore them, which is called {{< term "alert-fatigue" "alert fatigue" >}}.

## Blind spots and costs

- `ConsumerInfo` is a request to the server. Sample it every second or so, not once per message.
- The gauges are only as fresh as the sampling interval. In the output above, `consumer_num_ack_pending` was up to half a second behind the counters.
- Histogram buckets are fixed when you create the histogram. Choose them around the latencies you really have. If every job falls into the last bucket, the histogram tells you nothing.
- Propagating the header only helps if every hop extracts it too. A service that republishes a message without copying its headers breaks the trace in two.
- The stdout exporter is for demos. In production you send spans to a collector.

## What's next

Everything here ran against a server embedded in the same Go program, which also makes testing easy: you do not need Docker or a shared server. The next post, [Testing JetStream services with an embedded nats-server](/posts/nats-jetstream-testing/), builds on exactly that.
