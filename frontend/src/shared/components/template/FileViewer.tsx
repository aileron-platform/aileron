export interface CommandData {
  name: string;
  description?: string;
  content?: string;
}
export interface AgentData {
  name: string;
  description?: string;
  model?: string;
  instructions?: string;
}
