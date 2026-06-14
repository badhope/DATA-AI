import type { AuthedContext, AuthedContextOptions } from './authed-command'
import { Command } from '@/framework/command'
import { buildAuthedContext } from './authed-command'

export abstract class DATACommand extends Command {
  protected async authedCtx(opts: AuthedContextOptions): Promise<AuthedContext> {
    return buildAuthedContext(this, opts)
  }
}
