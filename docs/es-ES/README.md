# DATA-AI

> Un agente de IA que por fin entiende los datos de tu empresa.

Mira. Ya sabes de qué va. Cada empresa tiene un montón de informes financieros, documentos internos, fichas de clientes, archivos de proyectos, esa carpeta que nadie se atreve a tocar, y unas hojas de Excel que son básicamente el sistema nervioso de la empresa. Nada se habla entre sí, nadie encuentra nada, y la gente que de verdad entiende los datos se ahoga en peticiones.

**DATA-AI** existe para eso.

**DATA-AI** es un agente de IA auto-hospedado que vive al lado de tus datos empresariales — finanzas, conocimiento interno, lo que importa — y hace el trabajo aburrido por ti. Le haces una pregunta, escarba en tus archivos y te la responde con fuentes. Le mandas una tarea, la ejecuta. ¿Informe semanal de `/finance/2025-Q4/`? Hecho en dos minutos, no en dos días.

## Qué hay dentro

- **Bases de conocimiento que de verdad conocen tu negocio** — métele PDF, Word, hojas de cálculo, exports de Notion, wikis internos, volcados de texto plano. Los indexa, aprende de ellos y responde como un compañero que lleva diez años ahí.
- **Workflows que se dibujan, no se programan** — arrastra unos bloques, conéctalos, guarda. Limpieza de datos, informes mensuales, "resúmeme todo lo nuevo en `/legal/`", "marca los contratos que vencen este trimestre", lo que sea.
- **Agentes que terminan el trabajo** — dale un objetivo. Lo parte en pasos, llama a las herramientas correctas, revisa su propio trabajo, y te cuenta qué hizo. Menos cuidar, más entregar.
- **Modelos, tú decides** — OpenAI, Claude, DeepSeek, tu Llama local, ese raro que tu equipo adora. Lo enchufas, el agente lo usa.
- **Vector DB, tú decides** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Usa el que ya tengas corriendo.
- **Una UI que no da ganas de cerrar** — consola para admins, chat para usuarios, API para ingenieros.

## Por qué lo construimos

Probamos las opciones SaaS. Luego las "open-core". Luego montarlo nosotros a base de llamadas a la API de OpenAI, hasta que escribimos el mismo boilerplate por cuarta vez y nos cansamos.

Así que hicimos algo que de verdad quisiéramos usar:

- **Auto-hospedado** — corre en una sola caja Linux, sin Kubernetes.
- **Tus datos se quedan en tu casa** — no salen de tu red, cada llamada a un modelo es auditable.
- **Sin llamadas comerciales** — es open source, el código está aquí.
- **Sin "lo añadimos en Q3"** — las features se construyen cuando alguien las necesita.

## Arrancarlo

La forma fácil (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

La forma manual (sin Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # una terminal
./dev/start-web    # otra
```

Abre <http://localhost:3000>. La guía completa en [`docs/`](./docs/).

## Arquitectura, en un párrafo

Backend en Python + Flask, organizado por dominios para encontrar las cosas. Frontend en Next.js (el moderno, no el de 2018). PostgreSQL para los datos estructurados. La vector DB que elijas para embeddings. Celery + Redis para todo lo que no debería bloquear al usuario. Un sistema de plugins para añadir modelos, herramientas e integraciones sin forkear el repo.

## Contribuir

Aceptamos PRs. Lee [CONTRIBUTING.md](./CONTRIBUTING.md) antes, no malgastes un sábado.

## Licencia

[Apache 2.0](./LICENSE). Haz lo que quieras, sólo deja el aviso de copyright.
