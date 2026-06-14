import type { CommandEffect } from '@/framework/command'
import { DATACommand } from '@/commands/_shared/data-command'
import { Flags } from '@/framework/flags'
import { realStreams } from '@/sys/io/streams'
import { agentGuide } from './guide'
import { runLogin } from './login'

export default class Login extends DATACommand {
  static override description = 'Sign in to DATA via OAuth device flow'

  static override effect: CommandEffect = 'write'

  static override examples = [
    '<%= config.bin %> auth login',
    '<%= config.bin %> auth login --host https://cloud.data.ai',
    '<%= config.bin %> auth login --no-browser',
  ]

  static override flags = {
    'host': Flags.string({
      description: 'DATA host URL',
      default: '',
    }),
    'no-browser': Flags.boolean({
      description: 'do not auto-open the browser',
      default: false,
    }),
    'insecure': Flags.boolean({
      description: 'allow http:// hosts (local-dev only)',
      default: false,
    }),
  }

  async run(argv: string[]): Promise<void> {
    const { flags } = this.parse(Login, argv)
    await runLogin({
      io: realStreams(),
      host: flags.host,
      noBrowser: flags['no-browser'],
      insecure: flags.insecure,
    })
  }

  override agentGuide(): string {
    return agentGuide
  }
}
