export interface Choice { id: string; text: string }
export interface Question { id: string; text: string; choices: Choice[]; candidate_format?: 'newline' | 'inline' }
export interface ScoreRequest { context: string; case_id?: string; image_ids?: string[]; questions: Question[] }
export interface PathwayRequest {
  case: {case_id: string; context: string; step: number; evidence?: {source_id: string; text: string; available_at_step: number}[]; image_ids?: string[]};
  workflow: {id: string; version: string; root: string; nodes: Record<string, {terminal?: boolean; question?: string; protocol?: string; actions?: {id: string; description: string; next: string}[]}>};
  node_id: string;
  history?: {node_id: string; action_id: string}[];
}
export interface Decision {
  id: string; created_at: string; case_id?: string | null; requires_review: true;
  score_kind: 'candidate_softmax';
  backend: {mode: 'fixture' | 'model'; model: string; step: number | null; checkpoint_sha256: string; revision?: string; training_identity?: string; quantization?: string};
  questions: {id: string; text: string; choices: (Choice & {score: number})[]; proposed_action_id: string; score_margin: number; candidate_format: 'newline' | 'inline'}[];
  proposed_next_node_id?: string; pathway?: Record<string, unknown>;
  latency_ms: number; cache: Record<string, unknown>;
}
export interface Review {question_id: string; action_id: string; reviewer: string; note?: string}
export interface SavedReview extends Review {id: string; decision_id: string; is_correction: boolean; proposed_action_id: string; created_at: string}
export interface Examples {
  mode: 'fixture' | 'live'; credential_configured: boolean;
  reasoning: {default_enabled: false; preview_available: boolean; live_available: boolean};
  pathway: PathwayRequest; score: ScoreRequest;
  photos: {attribution: string; source: string; license: string; examples: {id: string; title: string; url: string; context: string; source_id: string; source_split: string}[]};
}
export interface ReasoningSettings {
  enabled?: boolean; max_tokens?: number; max_rounds?: number; max_tool_calls?: number;
  additional_prompt?: string; max_context_chars?: number;
}
export interface ReasoningInput {
  request?: ScoreRequest | PathwayRequest;
  example_id?: 'pathway' | 'example-1' | 'example-2' | 'example-3';
  patient?: string; as_of_step?: number; reasoning?: ReasoningSettings;
}
export interface Refinement {
  enabled: boolean; mode: 'disabled' | 'scripted_tool_demo' | 'frozen_pretrained_nemotron';
  original_context: string; context: string; includes_question: boolean;
  tokens_used: number; rounds_used: number; tool_calls_used: number;
  source_ids: string[]; stop_reason: string; trace: Record<string, unknown>[];
  budget: {max_tokens: number; max_rounds: number; max_tool_calls: number; max_context_chars: number};
}
export interface RequestOptions {signal?: AbortSignal}
export interface DecisionClient {
  examples(options?: RequestOptions): Promise<Examples>;
  precomputed(id: string, options?: RequestOptions): Promise<{delivery: 'precomputed'; example_id: string; recorded_at: string; decision: Decision}>;
  health(options?: RequestOptions): Promise<{ready: boolean; backend: Decision['backend']}>;
  score(payload: ScoreRequest, options?: RequestOptions): Promise<Decision>;
  reason(payload: ReasoningInput, options?: RequestOptions): Promise<{decision: Decision; refinement: Refinement}>;
  refinePreview(payload: ReasoningInput, options?: RequestOptions): Promise<{delivery: 'scripted_tool_preview'; refinement: Refinement}>;
  propose(payload: PathwayRequest, options?: RequestOptions): Promise<Decision>;
  scoreExample(id: string, payload?: Partial<Pick<ScoreRequest, 'context' | 'case_id' | 'questions'>>, options?: RequestOptions): Promise<Decision>;
  decision(id: string, options?: RequestOptions): Promise<Decision & {input: Record<string, unknown>}>;
  review(id: string, payload: Review, options?: RequestOptions): Promise<SavedReview>;
}
export class DecisionAPIError extends Error {status: number; retryable: boolean}
export function createDecisionClient(options?: {baseUrl?: string; fetch?: typeof fetch; timeoutMs?: number}): DecisionClient;
