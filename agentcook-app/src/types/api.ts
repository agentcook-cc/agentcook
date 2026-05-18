// Error types
export interface ErrorEnvelope {
  code: string
  message: string
  detail?: Record<string, unknown> | null
}

// Agent types
export interface AgentIdentity {
  name: string
  role: string
  scopes: string[]
  created_at: string
  metadata: Record<string, unknown>
}

// Memory types
export type MemoryEventKind = 'observation' | 'decision' | 'tool_use' | 'user_input' | 'reflection'

export interface MemoryEvent {
  id: string
  timestamp: string
  kind: MemoryEventKind
  content: string
  source?: string | null
  metadata: Record<string, unknown>
}

export interface MemoryEventCreate extends Omit<MemoryEvent, 'id' | 'timestamp'> {}

export interface MemoryEventListResponse {
  items: MemoryEvent[]
  next_cursor?: string | null
}

export interface SearchRequest {
  query: string
  top_k?: number
}

export interface MemoryHit {
  content: string
  score: number
  event?: MemoryEvent | null
}

export interface SearchResponse {
  query: string
  hits: MemoryHit[]
}

// Flush types
export interface FlushRequest {
  confirm: string
  preserve_identity_and_soul?: boolean
}

export interface FlushResponse {
  deleted_event_count: number
  identity_preserved: boolean
  soul_preserved: boolean
}

// Auth types
export interface LoginRequest {
  username: string
  password: string
}

export interface UserInfo {
  id: string
  username: string
  displayName: string
  roles: string[]
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: UserInfo
}

// App specific types
export interface ChatRequest {
  message: string
  session_id?: string
}

export interface ChatStreamEvent {
  content?: string
  delta?: string
  text?: string
}
