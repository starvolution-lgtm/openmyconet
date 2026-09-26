-- =============================================================================
-- BioComm Schema v3 -- Rueckbau (downgrade der Migration 4b7c9e2d1f35).
-- Die Migration prueft vorher, dass es weder Einsaetze noch zurueckgestellte
-- Anlieferungen gibt, und bricht sonst verstaendlich ab.
-- =============================================================================
DROP TABLE sandbox.delivery_waiting, live.delivery_waiting;
DROP TABLE sandbox.device_deployment, live.device_deployment;
DROP PROCEDURE biocomm_common.core_0003(text);
