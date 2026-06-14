import { ENV_REGISTRY } from '@/env/registry'
import { CONTRACT } from './contract'

export type HelpTopic = {
  readonly name: string
  readonly summary: string
  readonly render: () => string
}

const ACCOUNT_HELP_TEXT = `datactl: account-bearer onboarding

  1. Sign in interactively (browser device flow):
       datactl auth login

  2. List accessible apps in your default workspace:
       datactl get app

  3. Describe one app to see its parameters:
       datactl describe app <id>

  4. Run an app and capture structured output:
       datactl run app <id> "hello" -o json

Tips:
  * 'datactl auth list' shows your authenticated contexts; 'datactl use host'
    and 'datactl use account' switch between them.
  * Pass --workspace <id> to target a non-default workspace.
  * Pass --stream to 'datactl run app' for live token/event output.
  * 'datactl env list' shows every env var datactl reads.
`

const EXTERNAL_HELP_TEXT = `datactl: external-SSO bearer onboarding

  Most agents authenticate as a human account (see 'datactl help account').
  External-SSO bearers (dfoe_) skip the human flow and exchange an upstream
  identity for a DATA token. The CLI surfaces the same commands but a
  smaller dataset:

  1. Acquire a token through your SSO provider (out of band).
  2. Hand it to the CLI:
       datactl auth login --external --token "$DATA_TOKEN"

  3. List apps your subject is permitted to invoke:
       datactl get app

  4. Run an app:
       datactl run app <id> "hello" -o json

Notes:
  * 'datactl get workspace' returns an empty list for external bearers — that
    is expected; external subjects have no workspace membership.
  * Tokens are best stored in DATA_TOKEN; datactl reads it on every command.
`

function renderEnvironment(): string {
  let out = 'ENVIRONMENT VARIABLES\n\n'
  for (const v of ENV_REGISTRY) {
    out += `  ${v.name}\n      ${v.description}\n`
    if (v.sensitive)
      out += '      (treat as secret; never echoed)\n'
    out += '\n'
  }
  return out
}

function renderAgent(): string {
  const exitCodes = Object.entries(CONTRACT.exitCodes)
    .map(([code, desc]) => `  ${code}  ${desc}`)
    .join('\n')

  return `datactl: agent operating guide

OUTPUT
  Pass -o json (or -o yaml) on every command — the JSON shape is stable and
  documented. Without it you get human tables meant for a terminal.

DISCOVERY
  datactl help -o json        full command tree + this contract, machine-readable
  datactl get app -o json     list apps (ids + modes)
  datactl describe app <id>   one app's mode and input schema

AUTH
  Interactive:     datactl auth login         (browser device flow)
  Non-interactive: export DATA_TOKEN=<bearer>  (read on every command)
  Details:         datactl help account / datactl help external

EXIT CODES
${exitCodes}

ERRORS
  Under -o json/yaml a failure writes a structured envelope to stderr:
    ${CONTRACT.errorEnvelope.shape}

HUMAN-IN-THE-LOOP
  ${CONTRACT.hitl.description}
  Resume: ${CONTRACT.hitl.resume}

RETRY
  Idempotent GET/PUT/DELETE retry on transient errors (default 3); POST/PATCH
  never. Override with --http-retry <n> or DATACTL_HTTP_RETRY.
`
}

export const TOPICS: readonly HelpTopic[] = [
  {
    name: 'account',
    summary: 'Agent-onboarding text for account bearers (dfoa_)',
    render: () => ACCOUNT_HELP_TEXT,
  },
  {
    name: 'agent',
    summary: 'Cross-command contract for agents driving datactl',
    render: renderAgent,
  },
  {
    name: 'environment',
    summary: 'Long-form documentation for every DATA_* env var',
    render: renderEnvironment,
  },
  {
    name: 'external',
    summary: 'Agent-onboarding text for external-SSO bearers (dfoe_)',
    render: () => EXTERNAL_HELP_TEXT,
  },
]

export function findTopic(name: string): HelpTopic | undefined {
  return TOPICS.find(t => t.name === name)
}
