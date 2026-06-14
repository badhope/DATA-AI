# DATA-AI

> Un agente IA che finalmente capisce i dati della tua azienda.

Senti. Sai già com'è. Ogni azienda ha un mucchio di report finanziari, documenti interni, schede clienti, file di progetto, quella cartella che nessuno osa toccare, e un paio di fogli Excel che di fatto sono il sistema nervoso dell'azienda. Niente parla con niente, nessuno trova niente, e chi davvero capisce i dati affoga nelle richieste.

**DATA-AI** l'abbiamo fatto per quello.

**DATA-AI** è un agente IA auto-ospitato che vive accanto ai dati della tua azienda — finanza, conoscenza interna, la roba che conta — e fa il lavoro noioso al posto tuo. Gli fai una domanda, scava nei tuoi file e ti risponde con le fonti. Gli dai un compito, lo porta a termine. Report settimanale di `/finance/2025-Q4/`? Pronto in due minuti, non due giorni.

## Cosa c'è dentro

- **Knowledge base che conoscono davvero il tuo business** — buttagli dentro PDF, Word, fogli di calcolo, export di Notion, wiki interne, dump di testo. Indicizza, impara, e risponde come un collega che è in azienda da dieci anni.
- **Workflow che si disegnano, non si programmano** — trascini dei blocchi, li colleghi, salvi. Pulizia dati, report mensili, "riassumi tutto quello che è nuovo in `/legal/`", "segnala i contratti che scadono questo trimestre", quello che ti serve.
- **Agenti che portano a casa il risultato** — dagli un obiettivo. Lo spezza in passi, chiama gli strumenti giusti, controlla il suo lavoro, e ti dice cosa ha fatto. Mmeno sorveglianza, più consegne.
- **I modelli, scegli tu** — OpenAI, Claude, DeepSeek, il tuo Llama locale, quell'obscuro a cui il team giura fedeltà. Lo attacchi, l'agente lo usa.
- **Vector DB, scegli tu** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Usa quello che hai già in piedi.
- **Una UI che non fa venir voglia di chiuderla** — console per admin, chat per utenti, API per chi preferisce digitare.

## Perché l'abbiamo fatto

Abbiamo provato le opzioni SaaS. Poi le "open-core". Poi abbiamo provato a costruircelo da soli con chiamate pure all'API di OpenAI, finché abbiamo scritto lo stesso boilerplate per la quarta volta e ci siamo stufati.

Così abbiamo fatto qualcosa che useremmo davvero:

- **Auto-ospitato** — gira su una singola scatola Linux, niente Kubernetes.
- **I tuoi dati restano tuoi** — non escono dalla tua rete, ogni chiamata a un modello è auditabile.
- **Niente telefonate commerciali** — è open source, il codice è qui.
- **Niente "lo aggiungiamo in Q3"** — le feature si fanno quando qualcuno ne ha bisogno.

## Per farlo partire

Il modo facile (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

A mano (senza Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # un terminale
./dev/start-web    # un altro
```

Apri <http://localhost:3000>. Guida completa in [`docs/`](./docs/).

## Architettura, in un paragrafo

Backend in Python + Flask, organizzato per domini così si trova tutto. Frontend in Next.js (quello moderno, non quello del 2018). PostgreSQL per i dati strutturati. La vector DB che scegli per gli embedding. Celery + Redis per tutto quello che non deve bloccare l'utente. Un sistema di plugin per aggiungere modelli, strumenti e integrazioni senza forkare il repo.

## Contribuire

Accettiamo PR. Leggi prima [CONTRIBUTING.md](./CONTRIBUTING.md), non sprecare un sabato.

## Licenza

[Apache 2.0](./LICENSE). Fai quello che vuoi, lascia solo l'avviso di copyright.
