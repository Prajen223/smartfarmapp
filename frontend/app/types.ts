export type SupportedLanguage = "en" | "hi" | "kn";

export interface EntityResult {
  crops?: string[];
  pests?: string[];
  diseases?: string[];
  soil?: string[];
  locations?: string[];
  schemes?: string[];
  fertilizers?: string[];
  nutrients?: string[];
  seasons?: string[];
}

export interface RetrievedDocument {
  doc_id: string;
  title: string;
  category: string;
  source: string;
  url: string;
}

export interface LiveMandiRecord {
  commodity: string;
  variety: string;
  market: string;
  district?: string;
  state?: string;
  arrival_date: string;
  min_price: number;
  max_price: number;
  modal_price: number;
  price_unit?: string;
}

export interface AdapterData {
  service?: string;
  status?: string;
  is_live?: boolean;
  source?: string;
  source_endpoint?: string;
  commodity?: string;
  district?: string;
  state?: string;
  market?: string;
  message?: string;
  live_records?: LiveMandiRecord[];
  post_harvest_advice?: string;
  current_temp_c?: number;
  humidity_pct?: number;
  wind_speed_kmh?: number;
  precipitation_mm?: number;
  spray_advisory?: string;
  spray_safety_rule?: string;
  location?: string;
  official_portal?: string;
  reference_msp?: {
    crop: string;
    marketing_season: string;
    msp_inr_per_quintal: number;
    source: string;
  };
  scheme_details?: {
    name: string;
    benefit: string;
    eligibility?: string;
    helpline?: string;
  };
}

export interface ApiResponse {
  session_id?: string;
  message_id?: string;
  input_text?: string;
  canonical_text?: string;
  question?: string;
  answer: string;
  intent?: string;
  confidence?: number | null;
  rag_confidence?: number | null;
  quality_score?: number | null;
  language?: string;
  language_code?: string;
  sources?: string[];
  audio_base64?: string;
  audio_format?: string;
  stt_provider?: string;
  tts_provider?: string;
  is_low_confidence?: boolean;
  retrieved_documents?: RetrievedDocument[];
  adapter_data?: AdapterData;
  entities?: EntityResult;
  session_context?: {
    turn_count?: number;
    active_crop?: string;
    active_soil?: string;
    last_intent?: string;
  };
}

export interface ChatMessage {
  id: string;
  sender: "farmer" | "assistant";
  text: string;
  timestamp: string;
  isVoice?: boolean;
  transcript?: string;
  language?: string;
  intent?: string;
  confidence?: number;
  sources?: string[];
  audioBase64?: string;
  audioFormat?: string;
  retrievedDocuments?: RetrievedDocument[];
  adapterData?: AdapterData;
  entities?: EntityResult;
  messageId?: string;
  sessionId?: string;
  feedbackRating?: "positive" | "negative";
  feedbackComment?: string;
}

export type VoiceState = "idle" | "recording" | "processing";
