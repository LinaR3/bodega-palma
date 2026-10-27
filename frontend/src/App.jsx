import { useCallback, useEffect, useRef, useState } from 'react'
import QrScanner from 'qr-scanner'
import { db } from './db'
import Dashboard from './Dashboard'

const API = `${location.protocol}//${location.host}/api`
const tokenKey = 'bodega-token'

async function api(path, options = {}) {
  const headers = { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(localStorage.getItem(tokenKey) ? { Authorization: `Bearer ${localStorage.getItem(tokenKey)}` } : {}),
    ...options.headers }
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 12000)
  let response
  try { response = await fetch(`${API}${path}`, { ...options, headers, signal: controller.signal }) }
  finally { clearTimeout(timeout) }
  if (!response.ok) {
    let message = `Error ${response.status}`
    try { message = (await response.json()).detail || message } catch {}
    throw new Error(message)
  }
  if (response.status === 204) return null
  return response.headers.get('content-type')?.includes('application/json') ? response.json() : response.blob()
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem(tokenKey) || '')
  const [role, setRole] = useState(localStorage.getItem('bodega-role') || '')
  const [showDashboard, setShowDashboard] = useState(false)
  const [username, setUsername] = useState('')
  const [secret, setSecret] = useState('')
  const [products, setProducts] = useState([])
  const [matches, setMatches] = useState([])
  const [pending, setPending] = useState([])
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(null)
  const [kind, setKind] = useState('SALIDA')
  const [quantity, setQuantity] = useState('1')
  const [reason, setReason] = useState('Consumo de bodega')
  const [destination, setDestination] = useState('')
  const [cameraOpen, setCameraOpen] = useState(false)
  const [torch, setTorch] = useState(false)
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const videoRef = useRef(null)
  const scannerRef = useRef(null)
  const syncLock = useRef(false)

  const refreshQueue = useCallback(async () => setPending(await db.cola.orderBy('secuencia').toArray()), [])
  const sync = useCallback(async () => {
    if (syncLock.current) return
    syncLock.current = true
    try {
      if (!navigator.onLine || !localStorage.getItem(tokenKey)) return
      await db.cola.where('estado').equals('sincronizando').modify({ estado: 'pendiente' })
      const queued = await db.cola.where('estado').anyOf('pendiente', 'fallido').sortBy('secuencia')
      let applied = false
      for (const move of queued) {
        try {
          await db.cola.where('uuid').equals(move.uuid).modify({ estado: 'sincronizando', error: null })
          await api('/movimientos', { method: 'POST', body: JSON.stringify(move.payload) })
          await db.cola.where('uuid').equals(move.uuid).delete()
          applied = true
        } catch (error) {
          await db.cola.where('uuid').equals(move.uuid).modify({ estado: 'fallido', error: error.message })
        }
      }
      if (applied) {
        try { const latest = await api('/productos'); await db.productos.bulkPut(latest); setProducts(latest) } catch {}
      }
      await refreshQueue()
    } finally {
      syncLock.current = false
    }
  }, [refreshQueue])

  const loadProducts = useCallback(async () => {
    const cached = await db.productos.toArray()
    setProducts(cached)
    if (!navigator.onLine || !localStorage.getItem(tokenKey)) return
    try {
      const fresh = await api('/productos')
      await db.productos.bulkPut(fresh)
      setProducts(fresh)
    } catch (e) { setNotice(`Catálogo local disponible. ${e.message}`) }
  }, [])

  useEffect(() => {
    navigator.storage?.persist?.().catch(() => {})
    refreshQueue(); loadProducts(); sync()
    const onOnline = () => { setIsOnline(true); loadProducts(); sync() }
    const onOffline = () => setIsOnline(false)
    const timer = setInterval(async () => {
      if ((await db.cola.count()) > 0) sync()
    }, 15000)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => { clearInterval(timer); window.removeEventListener('online', onOnline); window.removeEventListener('offline', onOffline); stopScanner() }
  }, [loadProducts, refreshQueue, sync])

  function stopScanner() {
    scannerRef.current?.stop(); scannerRef.current?.destroy(); scannerRef.current = null
  }
  async function startScanner() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setNotice('La cámara requiere HTTPS confiable en este dispositivo. Usa búsqueda manual.'); return
    }
    setCameraOpen(true)
    setTimeout(async () => {
      if (!videoRef.current) return
      try {
        scannerRef.current = new QrScanner(videoRef.current, result => {
          const code = typeof result === 'string' ? result : result.data
          setSearch(code); lookup(code); stopScanner(); setCameraOpen(false)
        }, { preferredCamera: 'environment', maxScansPerSecond: 8, returnDetailedScanResult: true })
        await scannerRef.current.start()
      } catch (error) { setNotice(`No se pudo iniciar cámara: ${error.message}`); setCameraOpen(false); stopScanner() }
    }, 0)
  }
  async function toggleTorch() {
    try { if (!scannerRef.current || !(await scannerRef.current.hasFlash())) { setNotice('Linterna no disponible en este equipo.'); return }
      if (torch) await scannerRef.current.turnFlashOff(); else await scannerRef.current.turnFlashOn()
      setTorch(!torch)
    } catch { setNotice('La linterna no está disponible en este navegador.') }
  }
  async function lookup(value = search) {
    const term = value.trim()
    if (!term) return
    setMatches([])
    const local = await db.productos.toArray()
    const match = local.find(p => p.codigo_qr.toLowerCase() === term.toLowerCase()) ||
      local.filter(p => p.nombre.toLowerCase().includes(term.toLowerCase()))
    if (Array.isArray(match)) {
      if (match.length === 1) setSelected(match[0])
      else if (match.length > 1) { setMatches(match); setNotice(`Hay ${match.length} coincidencias; seleccione el producto.`) }
      else { setSelected(null); setNotice('Producto no encontrado.') }
    } else setSelected(match || null)
    if ((!match || (Array.isArray(match) && match.length === 0)) && navigator.onLine) {
      try {
        const remote = await api(`/productos?q=${encodeURIComponent(term)}`)
        await db.productos.bulkPut(remote)
        setProducts(remote)
        if (remote.length === 1) setSelected(remote[0])
        else if (remote.length > 1) { setMatches(remote); setNotice(`Hay ${remote.length} coincidencias; seleccione el producto.`) }
        else setNotice('Producto no encontrado.')
        return
      } catch (error) { setNotice(`No se pudo consultar el servidor: ${error.message}`); return }
    }
    if (!navigator.onLine && !match) setNotice('Producto no está en el catálogo descargado. Conéctese para buscarlo.')
    else if (!match) setNotice('Producto no encontrado.')
  }
  async function login(event) {
    event.preventDefault()
    try {
      const result = await api('/auth/login', { method: 'POST', body: JSON.stringify({ usuario: username, clave: secret, dispositivo: navigator.userAgent.slice(0, 100) }) })
      localStorage.setItem(tokenKey, result.token); setToken(result.token); setSecret(''); setNotice(`Sesión iniciada: ${result.nombre}`)
      localStorage.setItem('bodega-role', result.rol); setRole(result.rol)
      loadProducts(); sync()
    } catch (error) { setNotice(error.message) }
  }
  async function saveMove(event) {
    event.preventDefault()
    const qty = Number(quantity)
    if (!selected || !Number.isSafeInteger(qty) || qty <= 0) { setNotice('Ingrese una cantidad entera mayor que cero.'); return }
    const payload = { uuid: crypto.randomUUID(), producto_id: selected.id, tipo: kind,
      cantidad_cambio: kind === 'SALIDA' ? -qty : qty, motivo: reason,
      destino_area: destination || null, usuario_nombre: username || 'Bodega',
      dispositivo: navigator.userAgent.slice(0, 100), fecha_cliente: new Date().toISOString() }
    await db.cola.add({ uuid: payload.uuid, producto_id: selected.id, estado: 'pendiente', payload, error: null })
    setSelected(null); setSearch(''); setQuantity('1'); setDestination(''); setNotice('Movimiento guardado en el dispositivo.')
    await refreshQueue(); await sync()
  }
  async function logout() {
    try { await api('/auth/logout', { method: 'POST' }) } catch {}
    localStorage.removeItem(tokenKey); setToken(''); setNotice('Sesión cerrada.')
    localStorage.removeItem('bodega-role'); setRole('')
  }

  if (token && role === 'ADMIN' && showDashboard) return <Dashboard onBack={() => setShowDashboard(false)} />

  if (!token) return <main className="login"><h1>Bodega Palma</h1><p>Control local de inventario</p><form onSubmit={login}>
    <label>Usuario<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required /></label>
    <label>PIN o contraseña<input type="password" value={secret} onChange={e => setSecret(e.target.value)} inputMode="numeric" autoComplete="current-password" required /></label>
    <button className="primary">Ingresar</button></form><p className="muted">El primer inicio requiere conexión con el servidor de planta.</p>{notice && <p role="status">{notice}</p>}</main>

  return <main className="app"><header><div><h1>Bodega</h1><span>{isOnline ? 'Conectado' : 'Sin conexión'}</span></div><div className="headbuttons">{role === 'ADMIN' && <button className="small" onClick={() => setShowDashboard(true)}>Panel admin</button>}<button className="small" onClick={logout}>Salir</button></div></header>
    <section className="syncbar"><strong>{pending.length} pendiente{pending.length === 1 ? '' : 's'}</strong><button onClick={sync}>Sincronizar ahora</button></section>
    {pending.some(m => m.estado === 'fallido') && <section className="errors" aria-live="polite"><h2>Movimientos con error</h2>{pending.filter(m => m.estado === 'fallido').map(m => <p key={m.uuid}><strong>{products.find(p => p.id === m.producto_id)?.nombre || `Producto ${m.producto_id}`}</strong> · {m.uuid.slice(0, 8)} · {m.error}</p>)}</section>}
    {notice && <p className="notice" role="status">{notice}</p>}
    <section className="search"><h2>Buscar insumo</h2><div className="searchrow"><input value={search} onChange={e => { setSearch(e.target.value); setMatches([]) }} onKeyDown={e => e.key === 'Enter' && lookup()} placeholder="Código QR o nombre" aria-label="Código QR o nombre"/><button onClick={() => lookup()}>Buscar</button></div>
      <button className="primary camera" onClick={cameraOpen ? () => { stopScanner(); setCameraOpen(false) } : startScanner}>{cameraOpen ? 'Cerrar cámara' : 'Escanear QR'}</button>
      {cameraOpen && <div className="cameraBox"><video ref={videoRef} muted playsInline/><button onClick={toggleTorch}>{torch ? 'Apagar linterna' : 'Encender linterna'}</button></div>}
      {matches.length > 0 && !selected && <div className="results">{matches.slice(0, 8).map(p => <button key={p.id} className="result" onClick={() => { setSelected(p); setMatches([]); setNotice('') }}>{p.foto_url && <img className="productphoto thumb" src={p.foto_url} alt="" loading="lazy"/>}<strong>{p.nombre}</strong><span>{p.codigo_qr} · {p.ubicacion}</span></button>)}</div>}
    </section>
    {selected && <section className="selected"><div className="producttitle">{selected.foto_url && <img className="productphoto" src={selected.foto_url} alt={`Foto de ${selected.nombre}`}/>}<div><h2>Confirmar producto</h2><p className="productname">{selected.nombre}</p><p>{selected.codigo_qr} · {selected.ubicacion}</p>{selected.descripcion && <p>{selected.descripcion}</p>}</div><button className="small" onClick={() => setSelected(null)}>Cambiar</button></div>
      <p>Stock del último catálogo: <strong>{selected.stock_actual} {selected.unidad_medida}</strong></p>
      <form onSubmit={saveMove}>
        <div className="segmented"><button type="button" className={kind === 'SALIDA' ? 'active' : ''} onClick={() => setKind('SALIDA')}>Salida</button><button type="button" className={kind === 'ENTRADA' ? 'active' : ''} onClick={() => setKind('ENTRADA')}>Entrada</button></div>
        <label>Cantidad<input type="number" min="1" step="1" inputMode="numeric" value={quantity} onChange={e => setQuantity(e.target.value)} required/></label>
        <label>Motivo<input value={reason} onChange={e => setReason(e.target.value)} required/></label>
        <label>Área o destino (opcional)<input value={destination} onChange={e => setDestination(e.target.value)}/></label>
        <button className="primary done">Guardar movimiento</button>
      </form>
    </section>}
    <footer>Catálogo: {products.length} producto{products.length === 1 ? '' : 's'} en este dispositivo. <button onClick={async () => { await loadProducts(); await sync() }}>Actualizar</button></footer>
  </main>
}
