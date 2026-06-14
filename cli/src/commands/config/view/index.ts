import { DATACommand } from '@/commands/_shared/data-command'
import { Flags } from '@/framework/flags'
import { raw } from '@/framework/output'
import { getConfigurationStore } from '@/store/manager'
import { runConfigView } from './run'

export default class ConfigView extends DATACommand {
  static override description = 'Print the resolved config'

  static override examples = [
    '<%= config.bin %> config view',
    '<%= config.bin %> config view --json',
  ]

  static override flags = {
    json: Flags.boolean({ description: 'emit JSON', default: false }),
  }

  async run(argv: string[]) {
    const { flags } = this.parse(ConfigView, argv)
    return raw(runConfigView({ store: getConfigurationStore(), json: flags.json }))
  }
}
