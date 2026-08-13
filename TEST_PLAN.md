# u2ctl — Plan de Pruebas Progresivo

Diez tareas escalando en complejidad para poner a prueba el sistema contra apps reales
(Facebook, LinkedIn, YouTube, Gmail, Instagram).

Cada tarea incluye su **criterio de éxito verificable** para que el agente pueda
auto-evaluarse, no solo declarar "lo hice".

---

## Nivel 1-2: Percepción y acciones simples

### 1. Reconocimiento de entorno (solo lectura, sin mutación)

- Comandos: `app current`, `device info`, `setup verify`
- Reportar foreground package, modelo, SDK y fingerprint.
- **Prueba:** envelope JSON limpio, sin tocar el device.
- **Éxito:** `ok: true` en las tres, datos consistentes entre sí.

### 2. Apertura dirigida + tap simple

- App: YouTube
- Abrir YouTube desde el launcher (`--text YouTube`) y tocar el ícono de "Buscar".
- **Prueba:** tap por texto exacto + postcondition `screen_changed`.
- **Éxito:** aparece la barra de búsqueda (verificar con `desc_contains "Buscar"`).

---

## Nivel 3-4: Input y navegación

### 3. Input en campo enfocado

- App: Gmail
- Tocar "Redactar" y escribir un asunto.
- **Prueba:** `ui input` + selector con `text_contains "Redactar"`.
- **Éxito:** `text_typed` devuelto y el dump muestra el asunto en pantalla.

### 4. Scroll-dirigido (bajo el pliegue)

- App: Facebook o LinkedIn
- `ui find --text-contains "<algo que está abajo>" --scroll-direction down`.
- **Prueba:** `ui.find` (reemplaza el loop manual swipe→dump).
- **Éxito:** `found: true` y `scrolls_performed` razonable (no el max).

---

## Nivel 5-6: Gestos y estado

### 5. Long-press + menú contextual

- App: Facebook
- Long-press en un post para abrir el picker de reacciones y elegir una distinta a "Me gusta".
- **Prueba:** `ui.long_press` + reacción.
- **Éxito:** el `content-desc` de la reacción cambia a la elegida.

### 6. Acción condicional por estado (idempotencia lógica)

- App: LinkedIn
- Detectar si un post ya está likeado (`desc_contains "recomendar"` vs `"ninguna reacción"`)
  y dar like **solo si no lo está**.
- **Prueba:** lógica de estado con `desc_contains`.
- **Éxito:** sin doble-like (el contador sube exactamente 1, no 2).

---

## Nivel 7-8: Flujos multi-paso

### 7. Multi-tap con verificación de postcondition

- App: Gmail
- Abrir un mail no leído, marcarlo leído, verificar que el indicador desaparece.
- **Prueba:** secuencia tap→tap→verificar por desc/fingerprint.
- **Éxito:** el estado "no leído" deja de aparecer en el dump.

### 8. Búsqueda + reproducción + back

- App: YouTube
- Buscar un término, abrir el primer resultado, `ui wait` a que cargue el reproductor, volver atrás.
- **Prueba:** input + tap + `ui.wait` + `press back`.
- **Éxito:** fingerprint cambia en cada transición y se vuelve a la lista de resultados.

---

## Nivel 9-10: Cross-app y adversarial

### 9. Flujo multi-app

- Apps: Instagram → LinkedIn
- Pasar de Instagram a LinkedIn vía home/launcher, hacer una acción en cada una.
- **Prueba:** `app current` entre transiciones + postcondition en ambas.
- **Éxito:** el package correcto se reporta en cada etapa.

### 10. Adversario: ambigüedad + recuperación de fallo

- App: Facebook
- Forzar un selector que matchee múltiples (`SELECTOR_MATCHED_MULTIPLE`),
  desambiguar con `--strict-selector`/`--bounds`, y simular un `DEVICE_OFFLINE`
  para probar el reconnect.
- **Prueba:** warning gestionado + recovery.
- **Éxito:** se elige el elemento correcto tras desambiguar, y el reconnect
  devuelve a un estado operativo.

---

## Notas

- Las tareas **5** y **6** exponen los gaps pendientes: el picker de reacciones
  necesita `long_press` + un tap sobre la reacción del overlay (aún sin `ui.find`
  sobre menú), y la **6** sin `--expect-*` requiere un dump extra de verificación manual.
- Al ejecutar cada tarea, conviene generar el routine file correspondiente en
  `.agents/skills/u2ctl/routines/` (ver §0 del SKILL.md).
