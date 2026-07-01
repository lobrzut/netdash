@echo off
REM One-shot cleanup of removed secondbrain stack services on VM 192.168.1.248
set PLINK=plink -batch -ssh root@192.168.1.248 -pw root -hostkey "ssh-ed25519 SHA256:MM/MONmA1tkhGEXos9KiJQtkzJZvjoRhOrARmmqXd9o"
set DB=/opt/stacks/netdash/data/netdash.db

echo === DRY-RUN: secondbrain-related services ===
%PLINK% "python3 -c \"import sqlite3;c=sqlite3.connect('%DB%');k=['hermes','khoj','secondbrain','second-brain','second_brain'];rows=[r for r in c.execute('SELECT id,name,host,port,is_online,url FROM services') if any(x in (r[1] or '').lower() or x in (r[5] or '').lower() for x in k)];print('count',len(rows));[print(r) for r in rows]\""

if "%1"=="--apply" goto apply
echo.
echo Run with --apply to delete listed rows and restart netdash.
exit /b 0

:apply
echo === DELETE ===
%PLINK% "python3 -c \"import sqlite3;c=sqlite3.connect('%DB%');k=['hermes','khoj','secondbrain','second-brain','second_brain'];ids=[r[0] for r in c.execute('SELECT id,name,url FROM services') if any(x in (r[1] or '').lower() or x in (r[2] or '').lower() for x in k)];c.executemany('DELETE FROM services WHERE id=?',[(i,) for i in ids]);c.commit();print('deleted',len(ids))\""

echo === Trigger health check ===
%PLINK% "curl -s -c /tmp/nd.cj -X POST http://127.0.0.1:18787/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"changeme\"}' > /dev/null && curl -s -b /tmp/nd.cj -X POST http://127.0.0.1:18787/api/services/health-check"

echo === Restart netdash (after image update with health fix) ===
%PLINK% "cd /opt/stacks/netdash && docker compose restart netdash 2>/dev/null || docker restart netdash"
