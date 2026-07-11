# Postmortem: billing API latency regression

## Summary
The billing API p99 latency rose from 120 ms to 1,400 ms over two hours during
month-end close. The cause was index bloat on the ledger_entries table that
degraded the reconciliation query plan, compounded by autovacuum running too
infrequently to keep up with the write rate.

## Impact
Invoice generation slowed and the reconciliation job missed its nightly window.
No data was lost and no incorrect invoice was sent, but the finance team's
close was delayed by three hours.

## Root cause
autovacuum_vacuum_scale_factor was left at the default, so vacuum did not run
often enough on the largest billing tables during the month-end write spike.
Dead tuples accumulated, the planner switched to a sequential scan, and latency
climbed. This is the failure mode the billing autovacuum runbook now prevents.

## Remediation
Lowered autovacuum_vacuum_scale_factor to 0.05 on the invoices and
ledger_entries tables and added a bloat alert on n_dead_tup. Latency returned to
baseline after the next vacuum cycle.
