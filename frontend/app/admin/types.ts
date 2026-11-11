export interface SummaryMetrics {
    total_farmers: number;
    total_sessions: number;
    active_sessions: number;
    total_queries: number;
    today_queries: number;
    unanswered_queries: number;
    feedback: {
        positive: number;
        negative: number;
        has_feedback_data: boolean;
        satisfaction_rate?: number;
    };
}

export interface DailyUsagePoint {
    date: string;
    queries: number;
    sessions: number;
}

export interface LanguageMetric {
    code: string;
    language: string;
    count: number;
    percentage: number;
}

export interface IntentMetric {
    intent: string;
    label: string;
    count: number;
    percentage: number;
}

export interface RecentActivityItem {
    message_id: string;
    session_id_masked: string;
    farmer_id_masked: string;
    query_preview: string;
    language: string;
    intent: string;
    confidence: number | null;
    created_at: string;
}

export interface AdminAnalyticsData {
    summary: SummaryMetrics;
    daily_usage: DailyUsagePoint[];
    language_distribution: LanguageMetric[];
    intent_distribution: IntentMetric[];
    recent_activity: RecentActivityItem[];
}

export interface ReviewRecordItem {
    review_id: string;
    created_at: string;
    query: string;
    canonical_text: string;
    intent: string;
    confidence: number;
    quality_score: number;
    source_reliability: number;
    evidence_grounding_score: number;
    status: "pending" | "approved" | "corrected" | "rejected";
    original_answer: string;
    flag_reason: string;
    language: string;
    sources: string[];
    corrected_answer?: string | null;
    reviewer_notes?: string | null;
    reviewed_at?: string | null;
    reviewer_username?: string | null;
}

export interface ReviewStats {
    total: number;
    pending: number;
    approved: number;
    corrected: number;
    rejected: number;
}

export interface UnansweredQueriesResponse {
    total: number;
    limit: number;
    offset: number;
    stats: ReviewStats;
    queries: ReviewRecordItem[];
}

export interface AdminUser {
    username: string;
    role: string;
}

export interface KnowledgeRecordItem {
    doc_id: string;
    category: string;
    title: string;
    sub_category: string;
    source_name: string;
    organization: string;
    official_url: string;
    verification_status: string;
    is_live_fetched?: boolean;
    retrieval_timestamp: string;
    content_en: string;
    content_hi?: string;
    content_ta?: string;
    content_kn?: string;
    crops_applicable: string[];
    soil_types_applicable?: string[];
    nutrients_applicable?: string[];
    seasons_applicable?: string[];
    tags: string[];
    guardrail_notice?: string;
    access_note?: string;
}

export interface KnowledgeBaseStats {
    total_records: number;
    matching_records: number;
    category_counts: Record<string, number>;
    top_crops: string[];
    vector_chunks: number;
    vector_backend: string;
    in_sync: boolean;
}

export interface KnowledgeBaseResponse {
    records: KnowledgeRecordItem[];
    total: number;
    limit: number;
    offset: number;
    stats: KnowledgeBaseStats;
}

export interface KnowledgeSyncStatus {
    backend: string;
    total_records: number;
    total_chunks: number;
    is_synchronized: boolean;
    categories: string[];
    crops: string[];
    languages_supported: string[];
    storage_directory: string;
}

export interface UploadPreviewData {
    filename: string;
    file_type: string;
    word_count: number;
    character_count: number;
    extracted_text: string;
    suggested_title: string;
    suggested_category: string;
    suggested_crops: string[];
    metadata: Record<string, unknown>;
    notice: string;
}

export interface FarmerFeedbackItem {
    feedback_id: string;
    session_id: string;
    message_id: string;
    rating: "positive" | "negative";
    comment?: string | null;
    farmer_id?: string | null;
    language: string;
    intent?: string | null;
    query_text?: string | null;
    answer_text?: string | null;
    review_id?: string | null;
    created_at: string;
    updated_at: string;
    review_detail?: ReviewRecordItem;
}

export interface FeedbackSummaryStats {
    total_ratings: number;
    positive: number;
    negative: number;
    satisfaction_rate: number;
}

export interface FeedbackListResponse {
    items: FarmerFeedbackItem[];
    total: number;
    limit: number;
    offset: number;
    stats: FeedbackSummaryStats;
}

export interface FeedbackDailyTrendPoint {
    date: string;
    positive: number;
    negative: number;
    total: number;
    satisfaction_rate: number;
}

export interface FeedbackLanguageMetric {
    code: string;
    language: string;
    count: number;
    positive: number;
    negative: number;
    satisfaction_rate: number;
}

export interface FeedbackIntentMetric {
    intent: string;
    label: string;
    count: number;
    positive: number;
    negative: number;
    satisfaction_rate: number;
}

export interface FeedbackAnalyticsResponse {
    satisfaction_rate: number;
    total_ratings: number;
    positive_ratings: number;
    negative_ratings: number;
    daily_trend: FeedbackDailyTrendPoint[];
    by_language: FeedbackLanguageMetric[];
    by_intent: FeedbackIntentMetric[];
}
