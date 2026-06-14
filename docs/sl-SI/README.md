# DATA-AI

> AI agent, ki končno razume podatke vašega podjetja.

Glej. Veš kako je. Vsako podjetje ima kup finančnih poročil, internih dokumentov, evidenc strank, projektnih datotek, tisto mapo, ki se je nihče ne upa dotakniti, in par Excelov, ki so dejansko živčni sistem firme. Nič se med seboj ne pogovarja, nihče ne najde nič, in ljudje, ki podatke res razumejo, so zasuti s prošnjami.

**DATA-AI** smo naredili za to.

**DATA-AI** je self-hosted AI agent, ki živi tik ob vaših podjetniških podatkih — finance, notranje znanje, tisto, kar šteje — in opravi dolgočasno delo namesto vas. Vprašate ga, prebrska vaše datoteke in odgovori z viri. Date mu nalogo, jo izvede. Tedensko poročilo za `/finance/2025-Q4/`? V dveh minutah, ne v dveh dneh.

## Kaj je v škatli

- **Baze znanja, ki vaše posle res poznajo** — vrzite vanj PDF-je, Word, preglednice, Notion izvoze, interne wiki-je, navadno besedilo. Indeksira, se uči, in odgovarja kot sodelavec, ki je pri hiši že deset let.
- **Delotoki, ki se rišejo, ne programirajo** — povlecite nekaj blokov, jih povežite, shranite. Čiščenje podatkov, mesečna poročila, "povzemi vse novo v `/legal/`", "označi pogodbe, ki potečejo to četrtletje", kar hočete.
- **Agenti, ki delo speljejo do konca** — dajte jim cilj. Razbijejo ga na korake, pokličejo prava orodja, preverijo svoje delo, in povedo kaj so naredili. Manj nadzora, več izdelkov.
- **Modeli, vaša izbira** — OpenAI, Claude, DeepSeek, vaš lokalni Llama, tista obskurna, ki jo vaša ekipa prisega. Priklopite, agent jo uporabi.
- **Vector DB, vaša izbira** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Uporabite tisto, ki že laufa.
- **Spletni UI, ki vam ne gre na živce** — konzola za admin-e, chat za končne uporabnike, API za inženirje.

## Zakaj smo naredili

Preizkusili smo SaaS. Potem "open-core". Potem smo še sami poskusili s surovimi klici na OpenAI API, dokler nismo četrtič pisali istega boilerplate-a in nam je bilo dovolj.

Tako smo naredili nekaj, kar bi sami res uporabljali:

- **Self-hosted** — laufa na eni sami Linux škatli, brez Kubernetes-a.
- **Vaši podatki ostanejo vaši** — ne gredo ven iz omrežja, vsak klic modela je auditabilen.
- **Brez klicanja prodaje** — odprta koda, koda je tu.
- **Brez "dodali bomo v Q3"** — funkcije naredimo, ko jih nekdo potrebuje.

## Zagon

Lahka pot (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

Ročno (brez Docker-ja):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # en terminal
./dev/start-web    # drug terminal
```

Odprite <http://localhost:3000>. Celoten vodič v [`docs/`](./docs/).

## Arhitektura, v enem odstavku

Backend Python + Flask, razdeljen po domenah, da se stvari najdejo. Frontend Next.js (moderni, ne tisti iz 2018). PostgreSQL za strukturirane podatke. Vector DB po vaši izbiri za embeddings. Celery + Redis za vse, kar ne sme blokirati uporabnika. Plugin sistem, da dodate modele, orodja in integracije, brez forkanja repozitorija.

## Prispevajte

PR-je sprejemamo. Najprej preberite [CONTRIBUTING.md](./CONTRIBUTING.md), da vam ne bo šla sobota v nič.

## Licenca

[Apache 2.0](./LICENSE). Delajte kar hočete, samo obvestilo o avtorskih pravicah pustite.
