# Kafka operations

## Consumer lag on the orders topic
Consumer lag on the orders topic means the orders consumer group is falling
behind the produce rate. Read the lag per partition with the consumer-group
describe command. A single hot partition usually points at a skewed partition
key, while uniform lag across partitions points at slow downstream processing.
Add consumer instances up to the partition count, no further, because extra
consumers past the partition count sit idle.

## Rebalancing storms in the orders consumer group
A rebalancing storm is repeated rebalances in the orders consumer group that
stall consumption. The common trigger is a consumer whose processing exceeds
max-poll-interval, so the broker evicts it and the group rebalances. Raise
max-poll-interval or shrink the max-poll-records batch so each poll finishes in
time. Cooperative sticky assignment reduces the blast radius of each rebalance.

## Disk pressure on Kafka brokers
Kafka brokers under disk pressure stop accepting writes and the produce path
errors. Check log-retention settings and confirm old segments are being
deleted. A stuck consumer holding the low-water mark can pin segments and fill
the disk; resolve the lagging consumer before adding storage.
