# DATA-AI · Node.js SDK

Typed client for the DATA-AI HTTP API. Works in Node 18+ and modern browsers.

## Install

```bash
npm install @data-ai/sdk
# or
pnpm add @data-ai/sdk
```

## Usage

```ts
import { DataClient, ChatClient } from '@data-ai/sdk'

const client = new DataClient({
  baseUrl: 'http://localhost:5001',
  apiKey: process.env.DATA_AI_KEY,
})

const chat = new ChatClient(client)
const answer = await chat.send({
  appId: '<your-app-id>',
  input: { question: 'What was Q4 revenue?' },
})
```

Full API surface in `src/`. Generated docs at <https://docs.data-ai.ai/sdk/node>.
