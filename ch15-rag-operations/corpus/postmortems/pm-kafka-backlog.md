# Postmortem: orders backlog from a rebalancing storm

## Summary
The orders topic built a two-hour consumer backlog after a deploy. A new
consumer build increased per-message processing time past max-poll-interval, so
the broker repeatedly evicted consumers and the orders consumer group entered a
rebalancing storm that stalled consumption.

## Timeline
Consumer lag alerted thirty minutes after the deploy. On-call correlated the lag
onset with the deploy timestamp and rolled back. The group stabilized within ten
minutes of the rollback and drained the backlog over the next hour.

## Root cause
The new build added a synchronous downstream call per message that pushed
processing past max-poll-interval. The broker treated the slow consumer as dead,
triggered a rebalance, and the cycle repeated. max-poll-records was also left at
the default, so each poll fetched too large a batch to finish in time.

## Follow-ups
Make the downstream call asynchronous, lower max-poll-records, and add a
processing-time histogram so a regression past the poll interval alerts before
it triggers a rebalancing storm.
