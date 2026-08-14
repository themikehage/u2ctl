# u2ctl — Suite v2 (Prompts en lenguaje natural)

Tareas complejas y cercanas a un entorno productivo real. A diferencia de la v1,
cada tarea es **solo un prompt en lenguaje natural**: sin comandos sugeridos, sin
pistas de implementación, sin criterio de éxito explícito. El agente debe planificar
el workflow completo (percepción → acción → verificación → manejo de imprevistos)
por su cuenta, como lo haría frente a un usuario real.

---

## Comunicación

### 1. Triage de correo
 Revisá mi Gmail y encontrá el correo no leído más antiguo. Leelo y marcalo como leído.

### 2. Redactar sin enviar
 En Gmail, empezá a redactar un correo nuevo con asunto "Reunión de mañana" y un
 cuerpo de una línea, y dejalo abierto en borrador sin enviarlo.

### 3. Mensaje por WhatsApp
 Abrí WhatsApp, buscá tu chat más reciente y enviá el mensaje "Estoy en camino".

---

## Contenido y entretenimiento

### 4. Búsqueda, reproducción y like
 Abrí YouTube, buscá "receta de pasta", reproducí el primer video que no sea un
 short ni publicidad, dale me gusta y volvé a la lista de resultados.

### 5. Suscribirse a un canal
 En YouTube, abrí el canal del video que estás viendo y suscribite a él.

### 6. Like condicional en Facebook
 Abrí Facebook y dale me gusta a la publicación más reciente de la primera persona
 que aparezca en tu feed, pero solo si todavía no le diste like.

### 7. Flujo entre apps de redes
 Abrí Instagram, mirá un par de historias, y después abrí LinkedIn y dejame en el feed.

---

## Sistema y dispositivo

### 8. Cambiar un ajuste
> Activá el modo oscuro del teléfono y dejá el dispositivo en la pantalla principal.

### 9. Información del dispositivo
> Decime qué modelo de teléfono y qué versión de Android estoy usando.

---

## Robustez y casos adversos

### 10. Diálogo o aviso inesperado
> Abrí cualquier app y, si aparece un diálogo de aviso o consentimiento, descartalo
> para llegar al contenido principal.

### 11. Recuperación del dispositivo
 Asegurate de que el dispositivo esté conectado y operativo. Si no responde o está
 desconectado, arreglalo y confirmá que vuelve a funcionar.

### 12. Selección en contexto ruidoso
 En YouTube, abrí exactamente el tercer video de los resultados de una búsqueda que
 devuelva varios resultados parecidos.

---

## Notas

- Cada prompt es auto-contenido: el agente no recibe estado previo ni contexto adicional.
- La dificultad real está en los imprevistos (diálogos, contenido bajo el pliegue,
  selectores ambiguos, apps que tardan en cargar), no en la tarea en sí.
- Al ejecutar cada tarea, conviene generar el routine file correspondiente en
  `.agents/skills/u2ctl/routines/` (ver §0 del SKILL.md) para que la siguiente
  ejecución del mismo objetivo sea determinista.
