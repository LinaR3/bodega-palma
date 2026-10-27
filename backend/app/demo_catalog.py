"""Small, safe demonstration catalogue for the palm warehouse."""

from decimal import Decimal

DEMO_PRODUCTS = [
    {
        "codigo_qr": "PAL-009101", "nombre": "Guantes de protección recubiertos",
        "categoria": "Elementos de protección personal", "ubicacion": "EPP · Estante A1",
        "unidad_medida": "par", "descripcion": "Guantes reutilizables para manipulación general. Producto completo, sin puntas ni filos.",
        "foto_url": "/productos/guantes.jpg", "stock_inicial": Decimal("12"),
        "stock_minimo": Decimal("4"), "stock_maximo": Decimal("20"),
    },
    {
        "codigo_qr": "PAL-009102", "nombre": "Gafas de seguridad transparentes",
        "categoria": "Elementos de protección personal", "ubicacion": "EPP · Estante A1",
        "unidad_medida": "unidad", "descripcion": "Gafas completas de protección ocular para uso en planta.",
        "foto_url": "/productos/gafas.jpg", "stock_inicial": Decimal("8"),
        "stock_minimo": Decimal("3"), "stock_maximo": Decimal("12"),
    },
    {
        "codigo_qr": "PAL-009103", "nombre": "Tapones auditivos en empaque",
        "categoria": "Elementos de protección personal", "ubicacion": "EPP · Estante A2",
        "unidad_medida": "empaque", "descripcion": "Par de tapones auditivos suaves, empacados y listos para usar.",
        "foto_url": "/productos/tapones.jpg", "stock_inicial": Decimal("15"),
        "stock_minimo": Decimal("5"), "stock_maximo": Decimal("24"),
    },
    {
        "codigo_qr": "PAL-009104", "nombre": "Chaleco reflectivo",
        "categoria": "Elementos de protección personal", "ubicacion": "EPP · Estante A2",
        "unidad_medida": "unidad", "descripcion": "Chaleco de alta visibilidad para labores en planta.",
        "foto_url": "/productos/chaleco.jpg", "stock_inicial": Decimal("6"),
        "stock_minimo": Decimal("2"), "stock_maximo": Decimal("10"),
    },
    {
        "codigo_qr": "PAL-009105", "nombre": "Respirador desechable en caja",
        "categoria": "Elementos de protección personal", "ubicacion": "EPP · Estante A2",
        "unidad_medida": "caja", "descripcion": "Caja cerrada de respiradores desechables de uso industrial.",
        "foto_url": "/productos/respirador.jpg", "stock_inicial": Decimal("10"),
        "stock_minimo": Decimal("3"), "stock_maximo": Decimal("16"),
    },
    {
        "codigo_qr": "PAL-009106", "nombre": "Aceite hidráulico sellado 20 L",
        "categoria": "Lubricantes", "ubicacion": "Lubricantes · Estante B1",
        "unidad_medida": "bidón", "descripcion": "Bidón original cerrado de aceite hidráulico. Se controla por envase completo.",
        "foto_url": "/productos/aceite-hidraulico.jpg", "stock_inicial": Decimal("4"),
        "stock_minimo": Decimal("2"), "stock_maximo": Decimal("8"),
    },
    {
        "codigo_qr": "PAL-009107", "nombre": "Grasa multipropósito en balde",
        "categoria": "Lubricantes", "ubicacion": "Lubricantes · Estante B1",
        "unidad_medida": "balde", "descripcion": "Balde de grasa multipropósito con tapa y sello intactos; se controla como unidad completa.",
        "foto_url": "/productos/grasa.jpg", "stock_inicial": Decimal("3"),
        "stock_minimo": Decimal("1"), "stock_maximo": Decimal("6"),
    },
    {
        "codigo_qr": "PAL-009108", "nombre": "Desengrasante industrial sellado 5 L",
        "categoria": "Aseo y mantenimiento", "ubicacion": "Aseo · Estante C1",
        "unidad_medida": "bidón", "descripcion": "Bidón cerrado de desengrasante. Mantener en su envase original.",
        "foto_url": "/productos/desengrasante.jpg", "stock_inicial": Decimal("7"),
        "stock_minimo": Decimal("2"), "stock_maximo": Decimal("10"),
    },
    {
        "codigo_qr": "PAL-009109", "nombre": "Paños absorbentes en paquete",
        "categoria": "Aseo y mantenimiento", "ubicacion": "Aseo · Estante C1",
        "unidad_medida": "paquete", "descripcion": "Paños reutilizables absorbentes doblados y empacados.",
        "foto_url": "/productos/panos-absorbentes.jpg", "stock_inicial": Decimal("10"),
        "stock_minimo": Decimal("3"), "stock_maximo": Decimal("18"),
    },
    {
        "codigo_qr": "PAL-009110", "nombre": "Balde plástico 20 L",
        "categoria": "Envases y almacenamiento", "ubicacion": "Almacenamiento · Estante C2",
        "unidad_medida": "unidad", "descripcion": "Balde plástico vacío, completo y sin bordes cortantes.",
        "foto_url": "/productos/balde.jpg", "stock_inicial": Decimal("5"),
        "stock_minimo": Decimal("2"), "stock_maximo": Decimal("8"),
    },
]
