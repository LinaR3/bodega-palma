import Dexie from 'dexie'

export const db = new Dexie('bodega-palma')
db.version(1).stores({
  productos: 'id,codigo_qr,nombre,categoria',
  cola: '++secuencia,&uuid,producto_id,estado',
  ajustes: 'clave'
})
