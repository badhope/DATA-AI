import { join } from 'node:path'
import { DATACommand } from '@/commands/_shared/data-command'
import { raw } from '@/framework/output'
import { resolveConfigDir } from '@/store/dir'
import { CONFIG_FILE_NAME } from '@/store/manager'

export default class ConfigPath extends DATACommand {
  static override description = 'Print the resolved config.yml path'

  static override examples = [
    '<%= config.bin %> config path',
  ]

  async run(argv: string[]) {
    this.parse(ConfigPath, argv)
    return raw(
      join(resolveConfigDir(), CONFIG_FILE_NAME),
    )
  }
}
