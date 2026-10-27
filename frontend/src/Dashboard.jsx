import { useCallback, useEffect, useState } from 'react'

async function request(path, init = {}) {
  const response = await fetch(`/api${path}`, { ...init, headers: {
    Authorization: `Bearer ${localStorage.getItem('bodega-token')}`,
    ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers
  } })
  if (!response.ok) throw new Error(`Error ${response.status}: ${await response.text()}`)
  return response.json()
}

function StockBadge({ state }) { return <span className={`badge ${state.toLowerCase()}`}>{state}</span> }

export default function Dashboard({ onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [filter, setFilter] = useState({})
  const [busy, setBusy] = useState(false)
  const [receiving, setReceiving] = useState({})
  const [catalogFile, setCatalogFile] = useState(null)
  const [importResult, setImportResult] = useState(null)
  const [productCatalog, setProductCatalog] = useState([])
  const [orderProduct, setOrderProduct] = useState('')
  const [orderQuantity, setOrderQuantity] = useState('1')
  const [orderNote, setOrderNote] = useState('')
  const [orderMessage, setOrderMessage] = useState('')

  const refresh = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (filter.q) params.set('q', filter.q)
      if (filter.categoria) params.set('categoria', filter.categoria)
      if (filter.desde) params.set('desde', new Date(`${filter.desde}T00:00:00-05:00`).toISOString())
      if (filter.hasta) params.set('hasta', new Date(`${filter.hasta}T23:59:59-05:00`).toISOString())
      const result = await request(`/dashboard/resumen?${params}`)
      setData(result); setError('')
    } catch (e) { setError(e.message) }
  }, [filter])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 5000)
    return () => clearInterval(timer)
  }, [refresh])

  useEffect(() => {
    request('/productos').then(setProductCatalog).catch(e => setError(e.message))
  }, [])

  async function resolve(id) {
    setBusy(true)
    try { await request(`/discrepancias/${id}/resolver`, { method: 'POST' }); await refresh() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  async function createManualOrder(event) {
    event.preventDefault()
    const quantity = Number(orderQuantity)
    if (!orderProduct || !Number.isSafeInteger(quantity) || quantity <= 0) {
      setError('Selecciona un producto y una cantidad entera mayor que cero.')
      return
    }
    setBusy(true); setError(''); setOrderMessage('')
    try {
      await request('/pedidos/manuales', { method: 'POST', body: JSON.stringify({
        producto_id: Number(orderProduct), cantidad: quantity, observacion: orderNote.trim() || null
      }) })
      const selected = productCatalog.find(p => p.id === Number(orderProduct))
      setOrderMessage(`Pedido manual creado para ${selected?.nombre || 'el producto'}. Quedó pendiente de aprobación.`)
      setOrderQuantity('1'); setOrderNote(''); await refresh()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  async function downloadFile(path, filename) {
    try {
      const response = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${localStorage.getItem('bodega-token')}` } })
      if (!response.ok) throw new Error(`No se pudo descargar el archivo (${response.status}).`)
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a'); link.href = url; link.download = filename
      document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setError(e.message) }
  }

  async function importCatalog(event) {
    event.preventDefault()
    if (!catalogFile) return
    setBusy(true); setImportResult(null); setError('')
    try {
      const form = new FormData(); form.append('file', catalogFile)
      const response = await fetch('/api/catalogo/importar', { method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('bodega-token')}` }, body: form })
      if (!response.ok) {
        let message = `No se pudo importar el archivo (${response.status}).`
        try { message = (await response.json()).detail || message } catch {}
        throw new Error(message)
      }
      setImportResult(await response.json()); setCatalogFile(null); event.target.reset(); await refresh()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  function downloadErrorReport(csv) {
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = 'errores-importacion.csv'
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function transition(alert, estado) {
    setBusy(true)
    try {
      const body = { estado }
      if (estado === 'PEDIDO') body.cantidad_pedida = alert.cantidad_sugerida
      if (estado === 'RECIBIDO') {
        const pending = Number(alert.cantidad_pedida) - Number(alert.cantidad_recibida)
        const quantity = Number(receiving[alert.id] || pending)
        if (!Number.isSafeInteger(quantity) || quantity <= 0 || quantity > pending) throw new Error('Cantidad recibida inválida')
        body.cantidad_recibida = quantity
        body.uuid_movimiento = crypto.randomUUID()
        body.dispositivo = 'panel administrador'
      }
      await request(`/alertas/${alert.id}/transicion`, { method: 'POST', body: JSON.stringify(body) })
      await refresh()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  if (!data && error) return <main className="dashboard"><button onClick={onBack}>Volver</button><p className="notice">{error}</p></main>
  return <main className="dashboard">
    <header><div><h1>Panel de bodega</h1><span>Actualización automática cada 5 segundos</span></div><button className="small" onClick={onBack}>Volver</button></header>
    {error && <p className="notice">{error}</p>}
    <form className="filters" onSubmit={e => { e.preventDefault(); setFilter({ q: query.trim(), categoria: category, desde: from, hasta: to }) }}>
      <label>Producto o código<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar" /></label>
      <label>Categoría<select value={category} onChange={e => setCategory(e.target.value)}><option value="">Todas</option>{(data?.categorias || []).map(c => <option key={c}>{c}</option>)}</select></label>
      <label>Desde<input type="date" value={from} onChange={e => setFrom(e.target.value)} /></label>
      <label>Hasta<input type="date" value={to} onChange={e => setTo(e.target.value)} /></label>
      <button className="primary">Aplicar filtros</button>
    </form>
    <nav className="exports"><button onClick={() => downloadFile('/exportar/pedidos.pdf', 'pedidos-sugeridos.pdf')}>Pedidos PDF</button><button onClick={() => downloadFile('/exportar/pedidos.xlsx', 'pedidos-sugeridos.xlsx')}>Pedidos Excel</button><button onClick={() => downloadFile('/etiquetas.pdf', 'etiquetas-qr.pdf')}>Etiquetas QR PDF</button></nav>
    <section className="orderComposer"><h2>Crear pedido manual</h2><p>Úsalo cuando necesites comprar un producto aunque no esté en estado crítico. El pedido queda como sugerido para que lo revises y apruebes.</p><form onSubmit={createManualOrder}><label>Producto<select value={orderProduct} onChange={e => setOrderProduct(e.target.value)} required><option value="">Selecciona un producto</option>{productCatalog.map(p => <option key={p.id} value={p.id}>{p.nombre} · stock {p.stock_actual} {p.unidad_medida} · {p.categoria}</option>)}</select></label><label>Cantidad a pedir<input type="number" min="1" step="1" inputMode="numeric" value={orderQuantity} onChange={e => setOrderQuantity(e.target.value)} required/></label><label>Motivo o nota (opcional)<input value={orderNote} onChange={e => setOrderNote(e.target.value)} maxLength="300" placeholder="Ej.: mantenimiento programado"/></label><button className="primary" disabled={busy || !productCatalog.length}>{busy ? 'Guardando…' : 'Crear pedido para aprobación'}</button></form>{orderMessage && <p className="manualSuccess" role="status">{orderMessage}</p>}</section>
    <section className="catalogTools"><h2>Catálogo Excel o CSV</h2><div className="exports"><button onClick={() => downloadFile('/catalogo/plantilla.xlsx', 'plantilla-catalogo.xlsx')}>Descargar plantilla</button><button onClick={() => downloadFile('/catalogo/ejemplo.xlsx', 'catalogo-ejemplo.xlsx')}>Descargar 10 productos de ejemplo</button></div><form className="catalogImport" onSubmit={importCatalog}><label>Importar productos<input type="file" accept=".xlsx,.xlsm,.csv" onChange={e => setCatalogFile(e.target.files?.[0] || null)} required/></label><button className="primary" disabled={busy || !catalogFile}>{busy ? 'Procesando…' : 'Importar archivo'}</button></form>{importResult && <div className="importReport" role="status"><strong>Productos importados: {importResult.insertados}</strong>{importResult.errores.length > 0 && <><p>Filas con error: {importResult.errores.length}</p><ul>{importResult.errores.slice(0, 20).map(item => <li key={`${item.fila}-${item.error}`}>Fila {item.fila}: {item.error}</li>)}</ul>{importResult.errores.length > 20 && <p>Se muestran los primeros 20 errores.</p>}{importResult.reporte_csv && <button onClick={() => downloadErrorReport(importResult.reporte_csv)}>Descargar reporte CSV</button>}</>}</div>}</section>
    {data && <>
      <section className="statrow">{Object.entries(data.conteos).map(([key, value]) => <article key={key} className={`stat ${key.toLowerCase()}`}><strong>{value}</strong><span>{key}</span></article>)}</section>
      <section className="dashgrid">
        <article><h2>Críticos ({data.criticos.length})</h2><div className="tablewrap"><table><thead><tr><th>Producto</th><th>Código</th><th>Stock</th><th>Rango</th><th>Estado</th></tr></thead><tbody>{data.criticos.map(p => <tr key={p.id}><td>{p.nombre}</td><td>{p.codigo_qr}</td><td>{p.stock_actual} {p.unidad_medida}</td><td>{p.stock_minimo}–{p.stock_maximo}</td><td><StockBadge state={p.estado} /></td></tr>)}</tbody></table></div></article>
        <article><h2>Pedidos pendientes ({data.alertas.length})</h2>{data.alertas.length === 0 ? <p>No hay pedidos pendientes.</p> : <div className="tablewrap"><table><thead><tr><th>Producto</th><th>Tipo</th><th>Estado</th><th>Cantidad sugerida</th><th>Pedido / recibido</th><th>Nota</th><th>Acción</th></tr></thead><tbody>{data.alertas.map(a => <tr key={a.id}><td>{a.producto}</td><td>{a.es_manual ? 'Manual' : 'Por stock mínimo'}</td><td>{a.estado}</td><td>{a.cantidad_sugerida}</td><td>{a.cantidad_pedida} / {a.cantidad_recibida}</td><td>{a.observacion || '—'}</td><td>{a.estado === 'SUGERIDO' && <button disabled={busy} onClick={() => transition(a, 'APROBADO')}>Aprobar</button>}{a.estado === 'APROBADO' && <button disabled={busy} onClick={() => transition(a, 'PEDIDO')}>Marcar como pedido realizado</button>}{a.estado === 'PEDIDO' && <div className="receive"><input aria-label={`Cantidad recibida ${a.producto}`} type="number" min="1" max={Number(a.cantidad_pedida) - Number(a.cantidad_recibida)} step="1" value={receiving[a.id] ?? (Number(a.cantidad_pedida) - Number(a.cantidad_recibida))} onChange={e => setReceiving({ ...receiving, [a.id]: e.target.value })}/><button disabled={busy} onClick={() => transition(a, 'RECIBIDO')}>Registrar recepción</button></div>}</td></tr>)}</tbody></table></div>}</article>
        <article><h2>Discrepancias abiertas ({data.discrepancias.length})</h2>{data.discrepancias.length === 0 ? <p>Sin discrepancias abiertas.</p> : <div className="tablewrap"><table><thead><tr><th>Producto</th><th>Detalle</th><th>Acción</th></tr></thead><tbody>{data.discrepancias.map(d => <tr key={d.id}><td>{d.producto}<br/><small>{d.codigo_qr}</small></td><td>{d.detalle}</td><td><button disabled={busy} onClick={() => resolve(d.id)}>Resolver</button></td></tr>)}</tbody></table></div>}</article>
        <article><h2>Movimientos recientes</h2><div className="tablewrap"><table><thead><tr><th>Fecha servidor</th><th>Producto</th><th>Tipo</th><th>Cambio</th><th>Usuario</th><th>Área</th></tr></thead><tbody>{data.movimientos.map(m => <tr key={m.id}><td>{new Date(m.fecha_servidor).toLocaleString('es-CO', { timeZone: 'America/Bogota' })}</td><td>{m.producto}</td><td>{m.tipo}</td><td>{m.cantidad_cambio}</td><td>{m.usuario}</td><td>{m.destino_area || '—'}</td></tr>)}</tbody></table></div></article>
      </section>
    </>}
  </main>
}
