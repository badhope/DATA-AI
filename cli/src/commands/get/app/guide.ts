export const agentGuide = `
DISCOVERY
  List apps to find their ids and modes before running one:
    datactl get app -o json          all apps in the default workspace
    datactl get app -A -o json       across every workspace you can see
    datactl get app <id> -o json     one app's basic info

  Each app's "mode" (chat / advanced-chat / completion / workflow / agent-chat)
  decides how you call run app. Use 'datactl describe app <id>' for the full
  input schema.

ERROR RECOVERY
  not logged in (exit 4)   datactl auth login
  empty list               wrong workspace — try -A or --workspace <id>
`
