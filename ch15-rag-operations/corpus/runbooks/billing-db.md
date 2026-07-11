# Billing database operations

## Tuning autovacuum on the billing DB
The billing database accumulates dead tuples quickly during end-of-month
reconciliation. Lower autovacuum_vacuum_scale_factor to 0.05 on the invoices
and ledger_entries tables so vacuum runs more often on the largest relations.
Watch n_dead_tup in pg_stat_user_tables and confirm bloat drops after the next
cycle. This keeps query plans stable on the billing DB during peak load.

## Resolving ORA-00600 internal error on the billing DB
An ORA-00600 internal error code indicates an unexpected condition in the
database kernel. On the billing DB this has been triggered by a corrupted index
on the ledger_entries table after an unclean shutdown. Capture the first
argument from the ORA-00600 message, match it against the vendor note, then
rebuild the suspect index online and validate the segment. Do not restart the
instance before capturing the trace file, because the diagnostic context is
lost on restart.

## Billing reconciliation runbook
Run the nightly reconciliation job against the billing DB after invoices close.
The job compares ledger_entries totals to the payment processor settlement
file. A mismatch over one cent pages the on-call finance engineer. Re-run the
job with the --dry-run flag first to see the delta before writing corrections.

## Failover for the billing DB replica
The billing DB runs a primary and one synchronous replica. To fail over,
promote the replica with the managed-database console, update the writer
endpoint, and confirm the application picks up the new primary within the
connection-pool refresh interval. Expect about thirty seconds of write
unavailability during promotion.
