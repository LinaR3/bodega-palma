# Decisiones de Fase 1

- **Cantidad entera por artículo:** el catálogo representa presentaciones cerradas e indivisibles (por ejemplo, una botella completa). Se conserva `Numeric(14,3)` por el requisito de no usar floats, pero la API valida existencias, niveles y movimientos como enteros. Si aparecen insumos fraccionables, deberá habilitarse por producto, no globalmente.
- **Stock:** el cliente envía deltas. El servidor registra primero el UUID único y ejecuta un `UPDATE stock_actual = stock_actual + delta ... RETURNING` en la misma transacción. El motor aplica el bloqueo de escritura; no se depende de `SELECT FOR UPDATE`.
- **Reintentos:** la clave única de UUID hace que un reintento exitoso devuelva el movimiento original y no vuelva a aplicar el delta. El reclamo de UUID ocurre antes de actualizar stock; un conflicto revierte la transacción perdedora.
- **Discrepancias:** el egreso que deja stock negativo se acepta y crea una discrepancia vinculada al movimiento. No se modifica ni rechaza el movimiento físico.
- **Orden temporal:** `fecha_servidor` UTC define el orden. `fecha_cliente` es informativa y se conserva en UTC; SQLite almacena UTC sin zona y la capa ORM restaura la zona UTC al leer.
- **Sugerencias:** solo se crean cuando `stock_actual <= stock_minimo`, con `max(0, maximo - actual - tránsito)`. Una sugerencia abierta se actualiza; cuando deja de estar crítico se cancela. Para esta regla se considera tránsito el saldo de alertas en estado `PEDIDO`.
- **Pedidos:** se puede registrar pedido por cantidad completa o parcial. Recepciones parciales crean movimientos ENTRADA con UUID y dejan el pedido PEDIDO hasta completar el saldo. Reintentar el UUID de recepción no duplica ni movimiento ni cantidad recibida.
- **Correcciones:** AJUSTE acepta delta parcial y referencia opcional a movimiento; ANULACION exige referencia y delta opuesto completo, y no permite segunda anulación del mismo movimiento. Los movimientos originales no se mutan ni eliminan.
- **Persistencia:** SQLite WAL por defecto; SQLAlchemy usa expresiones portables y `RETURNING` en SQLite moderno y PostgreSQL. PostgreSQL requiere el driver opcional `psycopg`.
- **Usuario en esta fase:** se incluye entidad mínima para que la auditoría pueda enlazarse después. Hasta Fase 2, `usuario_nombre` es texto no autenticado y no constituye control de acceso.
- **Importación de catálogo:** crea artículos con stock cero. El saldo inicial debe registrarse luego como movimiento ENTRADA individual por el cliente autenticado; el importador nunca acepta un stock absoluto.
