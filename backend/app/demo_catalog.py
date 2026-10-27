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
]
