# DATA-AI

> Ein KI-Agent, der endlich eure Unternehmensdaten versteht.

Schau. Du kennst das Problem. Jedes Unternehmen sitzt auf einem Berg Finanzberichte, interne Dokumente, Kundendaten, Projektdateien, diesem einen Ordner, an den sich niemand rantraut, und ein paar Excel-Sheets, die quasi das Nervensystem der Firma sind. Nichts redet miteinander, niemand findet was, und die Leute, die die Daten wirklich verstehen, ertrinken in Anfragen.

Genau dafür haben wir **DATA-AI** gebaut.

**DATA-AI** ist ein selbstgehosteter KI-Agent, der direkt neben euren Unternehmensdaten lebt — Finanzen, internes Wissen, das, was zählt — und die langweilige Arbeit für euch übernimmt. Ihr stellt eine Frage, er wühlt sich durch eure Dateien und antwortet mit Quellen. Ihr gebt ihm eine Aufgabe, erledigt er. Wochenbericht aus `/finance/2025-Q4/`? In zwei Minuten fertig, nicht in zwei Tagen.

## Was drin ist

- **Wissensbasen, die euer Geschäft wirklich kennen** — füttert PDFs, Word-Dokumente, Tabellen, Notion-Exporte, interne Wikis, Text-Dumps. Er indexiert, lernt, und antwortet wie ein Kollege, der seit zehn Jahren dabei ist.
- **Workflows, die man zeichnet, nicht codiert** — ein paar Blöcke ziehen, verdrahten, speichern. Datenbereinigung, Monatsberichte, „Fass mir alles Neue in `/legal/` zusammen", „Markiere alle Verträge, die dieses Quartal auslaufen", was ihr wollt.
- **Agenten, die den Job zu Ende bringen** — gib einem ein Ziel. Er zerlegt es in Schritte, ruft die richtigen Tools, prüft seine Arbeit, und sagt dir, was er gemacht hat. Weniger Beaufsichtigen, mehr Liefern.
- **Modelle, eure Wahl** — OpenAI, Claude, DeepSeek, euer lokales Llama, das Obskure, auf das euer Team schwört. Anstecken, läuft.
- **Vektor-DB, eure Wahl** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Nutzt, was ihr eh schon laufen habt.
- **Eine Web-UI, die man nicht hasst** — Konsole für Admins, Chat für Endnutzer, API für Ingenieure, die lieber tippen.

## Warum wir das gebaut haben

Wir haben die SaaS-Optionen probiert. Dann die „Open-Core"-Optionen. Dann haben wir versucht, es selbst mit rohen OpenAI-API-Aufrufen zu basteln, bis wir zum vierten Mal denselben Boilerplate geschrieben haben und keine Lust mehr hatten.

Also haben wir etwas gebaut, das wir selbst wirklich benutzen würden:

- **Selbstgehostet** — läuft auf einer Linux-Kiste, kein Kubernetes nötig.
- **Eure Daten bleiben eure** — gehen nicht raus, jeder Modellaufruf ist auditierbar.
- **Keine Vertriebsanrufe** — Open Source, der Code liegt hier.
- **Kein „Kommt in Q3"** — Features werden gebaut, wenn sie jemand braucht.

## Starten

Der einfache Weg (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

Per Hand (ohne Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # ein Terminal
./dev/start-web    # ein anderes
```

Dann <http://localhost:3000> aufmachen. Komplette Anleitung in [`docs/`](./docs/).

## Architektur, in einem Absatz

Python + Flask im Backend, nach Domänen sortiert, damit man was findet. Next.js im Frontend (die moderne Variante, nicht die von 2018). PostgreSQL für strukturierte Daten. Vektor-DB eurer Wahl für Embeddings. Celery + Redis für alles, was den Nutzer nicht blockieren soll. Plugin-System, damit ihr Modelle, Tools und Integrationen anflanschen könnt, ohne das Repo zu forken.

## Mitmachen

Wir nehmen PRs. Erst [CONTRIBUTING.md](./CONTRIBUTING.md) lesen, damit der Samstag nicht umsonst ist.

## Lizenz

[Apache 2.0](./LICENSE). Macht damit, was ihr wollt, lasst nur den Copyright-Hinweis stehen.
