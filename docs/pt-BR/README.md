# DATA-AI

> Um agente de IA que finalmente entende os dados da sua empresa.

Olha. Você já sabe como é. Toda empresa tem uma pilha de relatórios financeiros, documentos internos, fichas de clientes, arquivos de projetos, aquela pasta que ninguém ousa abrir, e umas planilhas de Excel que basicamente são o sistema nervoso da empresa. Nada conversa entre si, ninguém acha nada, e quem de verdade entende os dados está se afogando em pedidos.

A gente construiu o **DATA-AI** pra isso.

**DATA-AI** é um agente de IA auto-hospedado que mora do lado dos seus dados empresariais — financeiro, conhecimento interno, o que importa — e faz o trabalho chato por você. Faz uma pergunta, ele vasculha seus arquivos e responde com fontes. Manda uma tarefa, ele executa. Relatório semanal de `/finance/2025-Q4/`? Feito em dois minutos, não em dois dias.

## O que vem na caixa

- **Bases de conhecimento que realmente conhecem o seu negócio** — joga PDFs, Word, planilhas, exports do Notion, wikis internas, dumps de texto. Ele indexa, aprende, e responde como um colega que está há dez anos na casa.
- **Workflows que se desenham, não se programam** — arrasta uns blocos, conecta, salva. Limpeza de dados, relatórios mensais, "resume tudo que é novo em `/legal/`", "marca os contratos que vencem esse trimestre", o que for.
- **Agentes que terminam o serviço** — dá um objetivo. Ele quebra em passos, chama as ferramentas certas, confere o próprio trabalho, e te conta o que fez. Menos cobrar, mais entregar.
- **Modelos, você escolhe** — OpenAI, Claude, DeepSeek, seu Llama local, aquele obscuro que o time adora. Pluga, ele usa.
- **Vector DB, você escolhe** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Usa o que já tá rodando.
- **Uma UI que não dá vontade de fechar** — console pra admins, chat pra usuários, API pra engenheiros.

## Por que a gente construiu

A gente testou as opções SaaS. Depois as "open-core". Depois tentou montar sozinho com chamada pura na API da OpenAI, até escrever o mesmo boilerplate pela quarta vez e cansar.

Então fizemos algo que a gente usaria de verdade:

- **Auto-hospedado** — roda numa caixa Linux, sem Kubernetes.
- **Seus dados ficam com você** — não saem da sua rede, cada chamada de modelo é auditável.
- **Sem ligação de vendas** — é open source, o código tá aqui.
- **Sem "a gente entrega em Q3"** — feature é feita quando alguém precisa.

## Colocando pra rodar

O jeito fácil (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

Na mão (sem Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # um terminal
./dev/start-web    # outro
```

Abre <http://localhost:3000>. Guia completo em [`docs/`](./docs/).

## Arquitetura, em um parágrafo

Backend em Python + Flask, organizado por domínio pra achar as coisas. Frontend em Next.js (o moderno, não o de 2018). PostgreSQL pros dados estruturados. Vector DB que você escolher pras embeddings. Celery + Redis pra tudo que não pode bloquear o usuário. Sistema de plugins pra adicionar modelos, ferramentas e integrações sem forkar o repo.

## Contribuindo

A gente aceita PR. Lê o [CONTRIBUTING.md](./CONTRIBUTING.md) antes, pra não perder um sábado.

## Licença

[Apache 2.0](./LICENSE). Faz o que quiser, só mantém o aviso de copyright.
