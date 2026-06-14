# Algorise — Bot de trading de cripto con IA (web + PWA móvil)

Bot de trading de criptomonedas **asistido por IA**, totalmente funcional, que opera con
**dinero ficticio (paper trading)** usando **precios reales de Binance**. Pensado para
**uso local** (corre en tu PC) con una **web** y una **app móvil (PWA)** que comparten la
misma base de código. Todo el comportamiento del bot se **personaliza desde la interfaz,
sin tocar código** (riesgo, stop-loss, monedas, estrategia, IA…).

> ⚠️ **Modo papel.** No se usa dinero real. Es una herramienta educativa; el trading de
> cripto es de alto riesgo. El paso a dinero real está previsto como trabajo futuro y
> requerirá añadir claves de Binance y confirmaciones de seguridad.

---

## ¿Qué hace?

- **Cerebro híbrido**: estrategias cuantitativas (indicadores técnicos: EMA, RSI, MACD,
  Bollinger, ATR) generan las señales y una **capa de IA gratuita** las **valida y explica**
  en lenguaje natural (confirmar/vetar + nivel de confianza).
- **IA gratuita y configurable** desde la UI: por defecto **Ollama** (modelo local, gratis
  y privado); alternativas **Groq** y **Google Gemini** (capas gratuitas).
- **Gestión de riesgo completa**: % de riesgo por operación, stop-loss/take-profit (% o por
  ATR), trailing stop, máximo de posiciones, límite de pérdida diaria y circuit breaker por
  drawdown. Con **perfiles de un clic**: Conservador / Equilibrado / Agresivo.
- **Paper trading realista**: cartera virtual con comisión y slippage simulados, P&L en vivo.
- **Backtesting**: valida una estrategia+config sobre histórico antes de operar.
- **Panel en vivo** por WebSocket: equity, posiciones, decisiones de la IA y registro.
- **PWA**: instalable en el móvil, accesible desde tu red local.

---

## Arquitectura

```
Algorise/
  backend/    Python · FastAPI + bot (ccxt, indicadores, riesgo, IA, backtesting) · SQLite
  frontend/   React + TypeScript + Vite + Tailwind · PWA
  scripts/    arranque rápido en Windows (PowerShell)
```

- **Base de datos local**: SQLite (un archivo `backend/algorise.db`, cero configuración).
  Portable a Postgres/Supabase cambiando `DATABASE_URL`.
- **Datos de mercado**: Binance vía `ccxt` (datos públicos, sin claves).

---

## Puesta en marcha (uso local)

Requisitos: **Python 3.11+** y **Node 20+**.

### 1) Backend (API + bot)
```powershell
./scripts/start-backend.ps1
```
La primera vez crea el entorno virtual, instala dependencias y copia `.env`. Arranca en
`http://localhost:8000` (documentación de la API en `http://localhost:8000/docs`).

### 2) Frontend (web + PWA)
En otra terminal:
```powershell
./scripts/start-frontend.ps1
```
Abre `http://localhost:5173`. Usuario por defecto: **admin / admin**.

> Arranque manual (sin scripts):
> - Backend: `cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt; .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
> - Frontend: `cd frontend; npm install; npm run dev`

### 3) Usar desde el móvil (misma red WiFi)
1. Averigua la IP local de tu PC: `ipconfig` (busca "Dirección IPv4", p.ej. `192.168.1.50`).
2. En el móvil abre `http://192.168.1.50:5173`.
3. El frontend llamará automáticamente al backend en `http://192.168.1.50:8000`.
4. En el navegador del móvil: menú → **"Añadir a pantalla de inicio"** para instalar la PWA.

Si Windows bloquea la conexión, permite Python/Node en el Firewall (red privada).

---

## La IA (gratis)

La capa de IA solo **razona sobre indicadores ya calculados** (validar/explicar), así que un
modelo pequeño basta. Elige el proveedor en **Configuración → Inteligencia artificial**:

- **Ollama (recomendado, local y gratis)**:
  1. Instala Ollama: <https://ollama.com>
  2. Descarga un modelo: `ollama pull llama3.1:8b` (o `qwen2.5:7b`).
  3. En la UI: proveedor `ollama`, modelo `llama3.1:8b`. (Necesita ~8 GB de RAM libres.)
- **Groq / Gemini (gratis, por internet — útil si tu PC va justo)**:
  - Consigue una API key gratuita y ponla en `backend/.env` (`GROQ_API_KEY` o `GEMINI_API_KEY`).
  - En la UI elige el proveedor y un modelo (p.ej. Groq `llama-3.1-8b-instant`, Gemini `gemini-1.5-flash`).

Si la IA no está disponible, el bot **sigue funcionando** solo con la señal cuantitativa.

---

## Configurar el bot (sin tocar código)

Todo se edita en la pestaña **Configuración** y se aplica en caliente:
- General: capital virtual, moneda base, marco temporal, pares a operar.
- Estrategia activa y sus parámetros.
- Riesgo: sliders de % de riesgo, SL/TP, trailing, límites y breaker; o un **perfil** de un clic.
- IA: proveedor, modelo, umbral de veto, temperatura.

Arranca/para el bot desde el **Panel**. Usa **Backtesting** para validar antes.

---

## Tests
```powershell
cd backend
.venv\Scripts\python -m pytest
```

---

## Despliegue gratuito 24/7 (opcional)

Para que el bot opere sin tu PC encendido:
- **Backend**: VM **Oracle Cloud "Always Free"** (siempre encendida, sin coste) o **Fly.io**.
- **Frontend PWA**: **Cloudflare Pages / Vercel / Netlify** (estático gratis).
- **IA en nube**: usa **Groq/Gemini** (gratis) en vez de Ollama para no cargar la VM.
- **BBDD**: SQLite en la VM o Postgres (Supabase) cambiando `DATABASE_URL`.

Recuerda cambiar `SECRET_KEY` y la contraseña por defecto si lo expones a internet.

---

## Hoja de ruta
- [x] Paper trading completo, configurable, con IA y backtesting (MVP).
- [ ] Notificaciones push de operaciones.
- [ ] Más estrategias y modelos ML.
- [ ] **Dinero real** (Binance con claves) con confirmaciones y kill switch reforzado.
