# DATA-AI

> Un agent IA qui comprend enfin les données de votre entreprise.

Bon, tu connais le topo. Chaque boîte a un tas de rapports financiers, de documents internes, de fiches clients, de dossiers de projets, ce dossier que personne n'ose toucher, et quelques feuilles Excel qui font office de système nerveux. Rien ne communique, personne ne trouve rien, et ceux qui comprennent vraiment les données croulent sous les demandes.

**DATA-AI** est né pour ça.

**DATA-AI** est un agent IA auto-hébergé qui vit à côté de vos données d'entreprise — finance, connaissance interne, ce qui compte — et fait le boulot chiant à votre place. Tu poses une question, il fouille tes fichiers et te répond avec les sources. Tu lui confies une tâche, il l'exécute. Le rapport hebdo de `/finance/2025-Q4/` ? Deux minutes, pas deux jours.

## Ce qu'il y a dans la boîte

- **Des bases de connaissance qui connaissent vraiment ton métier** — balance PDF, Word, tableurs, exports Notion, wikis internes, dumps de texte brut. Il indexe, apprend, et répond comme un collègue qui est là depuis dix ans.
- **Des workflows qu'on dessine, pas qu'on code** — glisse quelques blocs, branche-les, sauvegarde. Nettoyage de données, rapports mensuels, « résume-moi tout ce qui est neuf dans `/legal/` », « signale les contrats qui expirent ce trimestre », ce que tu veux.
- **Des agents qui vont au bout** — donne-leur un objectif. Ils découpent en étapes, appellent les bons outils, vérifient leur travail, et te disent ce qu'ils ont fait. Moins de garde-fous, plus de livraisons.
- **Les modèles, tu choisis** — OpenAI, Claude, DeepSeek, ton Llama local, l'obscur que ton équipe adore. Branche, ça marche.
- **La base vectorielle, tu choisis** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Utilise celle qui tourne déjà.
- **Une UI qu'on ne déteste pas** — console pour les admins, chat pour les utilisateurs, API pour les ingénieurs.

## Pourquoi on l'a fait

On a essayé les SaaS. Puis les « open-core ». Puis on s'est dit qu'on allait le coder nous-mêmes avec l'API OpenAI brute, jusqu'à écrire le même boilerplate pour la quatrième fois et en avoir marre.

Du coup on a fait un truc qu'on utiliserait vraiment :

- **Auto-hébergé** — tourne sur une seule boîte Linux, pas besoin de Kubernetes.
- **Tes données restent chez toi** — rien ne sort de ton réseau, chaque appel à un modèle est auditable.
- **Pas d'appel commercial** — c'est open source, le code est là.
- **Pas de « on l'ajoutera en Q3 »** — les features se construisent quand quelqu'un en a besoin.

## Pour le lancer

La voie facile (Docker) :

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

À la main (sans Docker) :

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # un terminal
./dev/start-web    # un autre
```

Ouvre <http://localhost:3000>. Le guide complet est dans [`docs/`](./docs/).

## L'architecture, en un paragraphe

Backend Python + Flask, organisé par domaine pour s'y retrouver. Frontend Next.js (le moderne, pas celui de 2018). PostgreSQL pour les données structurées. La vector DB de ton choix pour les embeddings. Celery + Redis pour tout ce qui ne doit pas bloquer l'utilisateur. Un système de plugins pour ajouter modèles, outils et intégrations sans forker le repo.

## Contribuer

On accepte les PR. Lis d'abord [CONTRIBUTING.md](./CONTRIBUTING.md), ne gâche pas ton samedi.

## Licence

[Apache 2.0](./LICENSE). Fais ce que tu veux, garde juste l'avis de copyright.
