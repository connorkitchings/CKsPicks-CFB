# Historical audit evidence

`v4_2026.yaml` is a byte-for-byte copy of the retired V4 weekly-bets configuration
(formerly `conf/weekly_bets/v4_2026.yaml`). It is historical evidence only: the
`v4_config` root of `../phase1_audit_v1.yaml` reads it and pins its SHA-256
(`expected_sha256`). It is not operational configuration, nothing in the
pipeline loads it, and the retired path `conf/weekly_bets/v4_2026.yaml` must stay
absent. Do not edit the file; a changed byte fails the audit pin.
