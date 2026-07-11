# Redis operations

## Redis OOM and maxmemory policy
When Redis hits its maxmemory limit the OOM behavior depends on the eviction
policy. With noeviction set, writes fail with an OOM command-not-allowed error
while reads still serve. Switch the session cache to allkeys-lru so the least
recently used keys are evicted under pressure rather than failing writes. Size
maxmemory to about seventy-five percent of the instance memory to leave room for
the copy-on-write fork during persistence.

## Redis replication lag
Replication lag on a Redis replica grows when the replica cannot keep up with
the primary write stream, often during an RDB save. Check master-repl-offset
against the replica offset. A large backlog buffer absorbs short spikes; a
persistent gap means the replica is undersized or the network is saturated.

## Evictions on the session cache
Evictions on the session cache log out users early because their session keys
are dropped. Track evicted-keys in INFO stats. A spike in evictions means the
working set outgrew maxmemory; raise the limit or shorten session TTLs so the
cache holds the active set without churning.
