export type CommandAction =
  | { kind: 'add'; id: null; title: string; value: null }
  | { kind: 'due'; id: number; title: null; value: string | null }
  | { kind: 'done'; id: number; title: null; value: null }

export interface CommandResponse {
  actions: CommandAction[]
  ask: string | null
}
