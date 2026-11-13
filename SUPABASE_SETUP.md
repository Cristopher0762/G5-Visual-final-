# Conexión central de G5-Visual con Supabase

## Arquitectura

- Cada computador ejecuta su propio proceso Python, OpenCV y YOLO y utiliza su cámara local.
- Supabase PostgreSQL conserva usuarios, dispositivos, sesiones, eventos y configuraciones.
- Las Edge Functions `g5-api` y `g5-admin` son la puerta de entrada. La clave privilegiada de Supabase permanece en el entorno administrado de Edge Functions; no se copia a los computadores.
- SQLite (`data/g5.sqlite3`) conserva una copia local de sesiones y datos de trabajo del equipo. No es la base central compartida y no debe copiarse entre computadores.
- No se suben imágenes ni videos a PostgreSQL.

## Configuración en cada computador

1. Extrae el ZIP completo.
2. Ejecuta `instalar.bat`. El instalador crea `.venv`, instala dependencias y copia `.env.example` a `.env` automáticamente si aún no existe.
3. Cuando finalice, ejecuta `iniciar.bat`.
4. Inicia sesión con una de las cuentas migradas y cambia la contraseña temporal.

La instalación no requiere una clave `service_role` ni contraseña de base de datos en el computador. No agregues esos secretos al archivo `.env`. Cada equipo genera su propio `data/device_id`; no compartas ese archivo ni la base SQLite entre equipos.

## Datos migrados

Se migraron los tres usuarios que ya existían en SQLite, una sesión histórica con sus cuatro eventos y la configuración inicial de cámara. Las contraseñas no se guardan en texto plano: se conservaron sus hashes PBKDF2-HMAC-SHA256 y sus sales individuales.

## Alcance y limitaciones de esta integración

- Cada cuenta admite una sola sesión activa en toda la instalación. Un segundo inicio mientras la cuenta está activa se rechaza; no expulsa silenciosamente al primer equipo.
- La sesión usa un lease renovable de 90 segundos mediante heartbeat. Si el equipo se apaga o pierde conexión definitivamente, el acceso se libera al vencer el lease. Mientras la conexión funciona, el navegador renueva el lease cada 20 segundos.
- La captura de cámara y el detector YOLO siguen siendo locales a cada computador.
- La sincronización de sesiones se ejecuta en segundo plano para no bloquear el hilo de captura.
- Se requiere conexión a Internet para autenticación, consulta del historial central y sincronización. SQLite conserva la copia local si la red falla, pero no se garantiza una cola de reintentos persistente para los cambios que no alcancen Supabase.
- Las funciones Edge usan tokens propios de G5-Visual y validan el rol antes de operaciones administrativas. Las tablas tienen RLS habilitado y no conceden acceso directo a `anon` ni `authenticated`.
- La validación de extremo a extremo con una cámara física y dos computadores sigue siendo una prueba pendiente del entorno del usuario.


### Actualización de funciones Edge (versión corregida)

Después de instalar esta versión del proyecto, despliega nuevamente las funciones `g5-admin` y `g5-api` desde los archivos incluidos en `supabase/functions/`. Esto activa las operaciones `reactivate_user` y `reset_password`, y conserva la sesión actual cuando un usuario cambia su propia contraseña. No compartas la clave `service_role`; debe permanecer configurada como secreto del proyecto Supabase.

## Precisión sobre el uso de SQLite en esta versión

El flujo actual de sesiones es **SQLite primero y sincronización posterior a PostgreSQL**: `SqliteRepository.save_session()` confirma la escritura local y luego encola `cloud_sync` en segundo plano. Si la sincronización falla, la copia local permanece, pero no existe una cola persistente de reintentos garantizada.

SQLite también contiene una tabla local `users` para el modo sin conexión/configuración local y crea dos cuentas de demostración si la tabla está vacía. Cuando `G5_API_URL` está configurada, el inicio de sesión y la administración de cuentas consultan Supabase; la tabla local no es la autoridad de autenticación en ese modo. Por tanto, esta versión **todavía no implementa PostgreSQL como primer destino de escritura**. Para ese cambio hace falta una refactorización separada y pruebas de recuperación ante fallos de red.

## Migraciones SQL

Aplica, en orden, todos los archivos de `supabase/migrations/`. La migración `20261113_create_atomic_session_rpc.sql` define `g5_acquire_user_session`, función invocada por `g5-api` para adquirir de forma atómica una sesión por usuario. Si esa función ya existe en el proyecto Supabase, `create or replace function` actualiza su definición de forma idempotente.
