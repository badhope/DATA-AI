import { DATACommand } from '@/commands/_shared/data-command'
import { Flags } from '@/framework/flags'
import { raw } from '@/framework/output'
import { runEnvList } from './run-list'

export default class EnvList extends DATACommand {
  static override description = 'Show every DATA_* env var datactl reads'

  static override examples = [
    '<%= config.bin %> env list',
    '<%= config.bin %> env list --json',
  ]

  static override flags = {
    json: Flags.boolean({ description: 'emit JSON', default: false }),
  }

  async run(argv: string[]) {
    const { flags } = this.parse(EnvList, argv)
    return raw(runEnvList({ json: flags.json }))
  }
}
