import { DATACommand } from '@/commands/_shared/data-command'
import { Flags } from '@/framework/flags'
import { realStreams } from '@/sys/io/streams'
import { runUseHost } from './use-host'

export default class UseHost extends DATACommand {
  static override description = 'Switch the active DATA host'

  static override examples = [
    '<%= config.bin %> use host',
    '<%= config.bin %> use host --domain cloud.data.ai',
  ]

  static override flags = {
    domain: Flags.string({ description: 'host domain to switch to, e.g. cloud.data.ai (interactive picker shown when omitted in TTY)', default: '' }),
  }

  async run(argv: string[]): Promise<void> {
    const { flags } = this.parse(UseHost, argv)
    await runUseHost({ io: realStreams(), host: flags.domain !== '' ? flags.domain : undefined })
  }
}
