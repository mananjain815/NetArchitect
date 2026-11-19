# Verification guide (Packet Tracer / GNS3)

1. `cd backend && python -m app.cli export --out ../exports` (already done; re-run after any engine change).
2. For each profile open `exports/<profile>_cabling.md` and build the topology (2911 routers, 3560 / 2960 switches).
   The hub router needs one routed port per WAN link: add NIM/HWIC modules, or use a bigger router.
3. Paste each `exports/<profile>/<DEVICE>.cfg` into its device CLI (files start with `enable` / `configure terminal`).
4. Packet Tracer only: IKE/IPsec lines marked `! PACKET TRACER` need the SHA-1 / DH-5 alternatives.
5. Run the checks in the table at the bottom of `ai_audit_log.md`, screenshot results, include them in your submission.
6. `exports/<profile>_full_config.txt` are the three "verification export" files required by the specification.
