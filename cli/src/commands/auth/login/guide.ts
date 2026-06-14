export const agentGuide = `
WHEN TO USE
  Establish a session before any authenticated command. Interactive browser
  device flow:
    datactl auth login
    datactl auth login --host https://cloud.data.ai
    datactl auth login --no-browser     print the code/URL instead of opening

NON-INTERACTIVE
  Agents without a browser can supply a bearer token via the DATA_TOKEN env
  var instead of logging in; datactl reads it on every command. See
  'datactl help account' and 'datactl help external'.

AFTER LOGIN
  datactl auth whoami      check the active session
  datactl auth list        list every authenticated context
  datactl get app          list apps
`
