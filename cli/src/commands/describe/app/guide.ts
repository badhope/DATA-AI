export const agentGuide = `
WHEN TO USE
  Inspect one app before running it — reveals its mode and the input
  variables / parameters it expects:
    datactl describe app <id> -o json
    datactl describe app <id> -o json | jq '.info.mode'

NEXT
  Feed the discovered inputs to run:
    datactl run app <id> --inputs '{"key":"value"}' -o json

ERROR RECOVERY
  app not found (404)      datactl get app
  not logged in (exit 4)   datactl auth login
`
