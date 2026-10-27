# Instalación y puesta en marcha

## Decisiones de despliegue

Se usa **Caddy** como terminador HTTPS y servidor de los estáticos de React; el backend solo escucha dentro de Docker o en `127.0.0.1`. CORS acepta únicamente el origen configurado. SQLite WAL es el valor inicial. Docker Compose incluye una API, Caddy, volumen persistente de datos y logs Docker rotativos; Ubuntu sin Docker usa systemd. No se publica el puerto 8000.

La dirección de la planta debe tener una IP reservada por DHCP y un nombre DNS interno, recomendado `bodega.planta`. Configure la resolución desde el router/DNS de la planta. Si se va a entrar por IP, inclúyala como SAN del certificado y edite el nombre de sitio de Caddy. Evite confiar en `*.local`, que algunos teléfonos reservan para mDNS.

## Requisitos de LAN y mini PC

- Ubuntu Server 22.04/24.04 de 64 bits, usuario administrativo, IP fija/reservada y reloj sincronizado.
- Enrutador con Wi-Fi de bodega; celulares y mini PC en la misma LAN/VLAN. Reserve una red estable para el equipo.
- Firewall: permitir TCP 443 desde la subred de la planta; bloquear acceso WAN y TCP 8000. No hacer port forwarding.
- Usar SSD, no una tarjeta SD. Conectar mini PC y router/AP al UPS.

## Certificado HTTPS y confianza en Android

Para una instalación pequeña puede generarse un certificado local con mkcert. mkcert está pensado principalmente para desarrollo local; en una planta con varios teléfonos, la opción de operación preferida es una CA interna administrada por la organización y desplegada a los dispositivos controlados. Nunca distribuya `rootCA-key.pem`: quien tenga esa llave puede emitir certificados para suplantar sitios. mkcert también advierte que sus clientes móviles requieren instalar la raíz de CA. Consulte [documentación del proyecto mkcert](https://github.com/FiloSottile/mkcert).

En un equipo de administración de certificados:

1. Instale mkcert desde su fuente oficial y ejecute `mkcert -install` bajo la cuenta administrativa elegida. Ejemplo Ubuntu: instale primero `libnss3-tools`; instale el binario firmado/publicado según el README oficial.
2. Desde `deploy/`, cree el directorio privado `certs/` y genere el certificado para los nombres que resolverán los teléfonos. Por ejemplo: `mkcert -cert-file certs/bodega.planta.pem -key-file certs/bodega.planta-key.pem bodega.planta 192.168.10.20`. Sustituya la IP por la IP reservada real.
3. Obtenga solo el certificado raíz público con `mkcert -CAROOT`; copie `rootCA.pem` fuera de la carpeta del CA y cámbiele la extensión a `rootCA.crt` si Android la exige. **No copie `rootCA-key.pem` a los celulares ni al repositorio.** Proteja la llave del certificado de servidor; deje los archivos de `deploy/certs` fuera de Git.
4. Verifique el certificado del servidor con `openssl x509 -in deploy/certs/bodega.planta.pem -noout -subject -ext subjectAltName` y confirme que DNS/IP de uso esté en SAN.
5. Instale la raíz en cada Android (los rótulos cambian por fabricante/versión): copie `rootCA.crt` por cable USB a **Descargas**; abra **Ajustes > Seguridad y privacidad > Más ajustes de seguridad > Cifrado y credenciales > Instalar un certificado > Certificado de CA**; seleccione el archivo, acepte el aviso e identifíquelo como “Bodega Planta”. En algunos Android, use el buscador de Ajustes con “Instalar certificado de CA”. Desbloquee con PIN si lo pide.
6. Abra Chrome en el celular y entre a `https://bodega.planta`. Verifique que no aparezca advertencia y que el certificado presentado contenga el nombre correcto. Si Android/Chrome no acepta la CA de usuario, deténgase: instale la CA como CA de sistema mediante la administración de dispositivos de la planta, o use una CA interna apropiada para los equipos. No ignore el aviso TLS.
7. En Chrome, seleccione **Instalar aplicación** o **Añadir a pantalla principal**. Permita cámara solo al usar el escáner. En Ajustes de Android, la CA puede revocarse/eliminarse cuando un teléfono salga de servicio.

La cámara y el Service Worker requieren un origen seguro. La cámara/linterna también dependen del hardware, permisos y navegador; siempre está disponible la búsqueda manual.

## Opción A: Docker Compose

1. Instale Docker Engine y el plugin Docker Compose siguiendo la guía oficial de Ubuntu. Clone/copíe el repositorio a `/opt/bodega`.
2. Monte un disco externo con UUID estable en `/mnt/bodega-backups`. Cree permisos para que el usuario admin y el proceso de backup lo puedan usar. Para la instalación, `mountpoint -q /mnt/bodega-backups` debe dar éxito.
3. Copie `deploy/.env.example` a `deploy/.env`. Ajuste `BACKUP_HOST_DIR`, `BACKUP_RETENTION_DAYS`; deje `DATABASE_URL` para el host systemd como ejemplo, dentro del contenedor Compose usa `/data/bodega.db`.
4. Coloque el par de certificado/llave en `deploy/certs/` con los nombres indicados en `deploy/Caddyfile`. La llave debe ser legible solo para Caddy y no ir a Git. En Docker, compruebe el grupo numérico de Caddy (`docker run --rm caddy:2-alpine id caddy`), asígnele ese grupo al archivo de llave y use modo `0640`; el certificado público puede ir `0644`. En systemd del host, use grupo `caddy` y modo `0640` para la llave.
5. Ejecute desde `deploy/`: `docker compose -f compose.yaml up -d --build`. Revise `docker compose ps`, `docker compose logs -f api web` y `curl -fsS https://bodega.planta/health` desde un equipo que ya confíe en la CA.
6. Cree la cuenta administradora: `docker compose -f compose.yaml exec api python -m app.create_user admin --rol ADMIN`. Use la contraseña interactiva. Luego cree la cuenta PIN compartida: `docker compose -f compose.yaml exec api python -m app.create_user bodega --rol BODEGUERO`. Mantenga la cuenta admin separada.
7. Copie y habilite `deploy/systemd/bodega-docker-backup.{service,timer}` en `/etc/systemd/system/`; ejecute `sudo systemctl daemon-reload`, `sudo systemctl enable --now bodega-docker-backup.timer` y `sudo systemctl start bodega-docker-backup.service`. Confirme un archivo en el disco externo y revise `systemctl status bodega-docker-backup.service`.

Compose solo expone 443. Su servicio de backup se ejecuta en el host, confirma que el disco externo está montado y luego invoca la API de backup SQLite desde el contenedor.

## Opción B: Ubuntu Server sin Docker

1. Instale Python 3.11+, Node.js 22, Caddy y herramientas de build disponibles en Ubuntu. Copie el proyecto a `/opt/bodega`; cree usuario/grupo de sistema `bodega` y asigne el proyecto de lectura, datos/logs de escritura.
2. Cree `/var/lib/bodega` y `/var/log/bodega`, propiedad `bodega:bodega`; monte el disco de backup por UUID en `/mnt/bodega-backups` y verifique `mountpoint`.
3. En `backend/`: cree `.venv`, instale `pip install -e '.[test]'`, luego `alembic upgrade head`. Cree el primer admin con `.venv/bin/python -m app.create_user admin --rol ADMIN` usando `sudo -u bodega`; cree también `bodega --rol BODEGUERO` con el mismo comando interactivo.
4. Cree `/etc/bodega/bodega.env` con permisos `0640`, propietario `root:bodega`. Incluya `DATABASE_URL=sqlite:////var/lib/bodega/bodega.db`, `CORS_ORIGINS=https://bodega.planta`, `APP_TIMEZONE=America/Bogota`, `LOG_FILE=/var/log/bodega/bodega.log`, `BACKUP_DIR=/mnt/bodega-backups` y `BACKUP_RETENTION_DAYS=30`.
5. En `frontend/`, ejecute `npm ci && npm run build`. Copie `deploy/Caddyfile` a `/etc/caddy/Caddyfile`, `deploy/certs/*` a `/etc/caddy/certs/` y configure permisos de lectura para el usuario `caddy` (grupo `caddy`, modo `0640` para llave). Copie `frontend/dist` a `/opt/bodega/frontend/dist`; ajuste la ruta `root` en Caddyfile a esa carpeta.
6. Copie `deploy/systemd/bodega.service` a `/etc/systemd/system/`; ajuste rutas si cambió `/opt/bodega`. Use el `caddy.service` que instala el paquete oficial Caddy; valide con `caddy validate --config /etc/caddy/Caddyfile`.
7. `sudo systemctl daemon-reload`; habilite `bodega.service` y Caddy; `sudo systemctl enable --now bodega.service caddy.service`. Revise `journalctl -u bodega -f`, `journalctl -u caddy -f`, `curl -fsS https://bodega.planta/health`.
8. Copie `bodega-backup.service` y `bodega-backup.timer`, luego habilite el timer. Ejecute una vez `sudo systemctl start bodega-backup.service`; confirme backup e integridad antes de entregar.

## Restauración de backup SQLite

1. Ponga la PWA en aviso de mantenimiento; detenga el servicio: `sudo systemctl stop bodega` (o `docker compose stop api`).
2. Elija un backup validado; confirme `sqlite3 BACKUP.sqlite3 'PRAGMA integrity_check;'` devuelve `ok`.
3. En systemd ejecute `sudo -u bodega /opt/bodega/backend/.venv/bin/python /opt/bodega/scripts/restore_sqlite.py BACKUP.sqlite3 /var/lib/bodega/bodega.db`. En Docker, con API detenida, ejecute `docker compose -f deploy/compose.yaml run --rm --no-deps --user 10001:10001 --entrypoint python api /app/backend/scripts/restore_sqlite.py /backups/ARCHIVO.sqlite3 /data/bodega.db`. El script crea una copia `pre-restore` de la base actual y reemplaza atómicamente tras validar.
4. Reinicie el servicio; confirme `/health`, inicio de sesión, catálogo, movimientos recientes y la hora de último backup. Registre fecha, backup usado y responsable.

La restauración SQLite tiene prueba automática con backup real y verificación de integridad (`backend/tests/test_backup.py`). Para PostgreSQL, el backup usa `pg_dump --format=custom`; restaure con `pg_restore` sobre una base nueva, verifique conteos y cambie `DATABASE_URL` en una ventana de mantenimiento. No se copia el archivo SQLite activo con `cp`.

## UPS, apagado y acceso remoto

- Seleccione un UPS con USB que el mini PC pueda leer; proteja también módem/router y punto de acceso. Dimensione autonomía para apagar ordenadamente (objetivo mínimo 10 minutos bajo carga real).
- Configure NUT (`nut-server`/`nut-client`) para iniciar `systemctl poweroff` con batería baja; pruebe el corte de energía fuera de producción y confirme parada limpia. No desconecte el mini PC como método normal de apagado.
- Compruebe periódicamente `systemctl status bodega`, timers, espacio de disco, espacio del backup y logs `journalctl`. Cambie la batería del UPS según prueba/capacidad.
- Tailscale es opcional: instálelo solo en equipos autorizados, aplique ACL/grupos mínimos y MFA, no publique la API en internet y no permita escrituras administrativas remotas sin decisión explícita de la planta. La app offline seguirá necesitando sincronizar al volver a la LAN/VPN.

## Checklist de entrega

- [ ] IP reservada y DNS interno resuelve desde todos los Android.
- [ ] CA y certificado incluyen SAN esperado; Android abre el sitio sin advertencias.
- [ ] PWA se puede instalar y cámara funciona; se probó búsqueda manual y lector tipo teclado.
- [ ] Un movimiento offline aparece pendiente, luego sincroniza una sola vez al volver la red.
- [ ] Un doble reintento no duplica stock; delta que deja negativo genera discrepancia.
- [ ] Admin puede resolver discrepancia y el evento queda auditado.
- [ ] `/health` confirma API y BD; puerto 8000 no es accesible desde la LAN.
- [ ] Backup nocturno corrió hacia disco externo; restauración a copia aislada fue verificada.
- [ ] UPS apaga ordenadamente mini PC/router/AP.
