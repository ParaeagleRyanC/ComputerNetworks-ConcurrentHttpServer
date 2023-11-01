# Single Thread
```
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    19.56s     5.63s   29.28s    57.81%
    Req/Sec     0.00      0.16    22.00     99.99%
  675 requests in 30.01s, 858.25KB read
Requests/sec:     22.49
Transfer/sec:     28.60KB
```

# Thread
```
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    19.56s     5.64s   29.31s    57.73%
    Req/Sec    22.00      0.00    22.00    100.00%
  6706 requests in 30.01s, 8.32MB read
Requests/sec:    223.48
Transfer/sec:    283.94KB
```

# Thread-Pool
```
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency    19.55s     5.64s   29.31s    57.72%
    Req/Sec    22.00      0.00    22.00    100.00%
  6745 requests in 30.01s, 8.37MB read
Requests/sec:    224.76
Transfer/sec:    285.57KB
```

# Async
```
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency   746.84us  310.31us   2.85ms   59.28%
    Req/Sec     1.03k    48.47     1.22k    67.97%
  299995 requests in 30.00s, 372.21MB read
Requests/sec:  10000.10
Transfer/sec:     12.41MB

```