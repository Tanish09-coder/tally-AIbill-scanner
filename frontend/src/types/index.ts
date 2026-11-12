export interface BillItem {
  id: number;
  bill_id: number;
  raw_item_name: string;
  matched_stock_item_name?: string;
  quantity: number;
  unit: string;
  rate: number;
  amount: number;
  discount: number;
  confidence_score: number;
  status: 'VALID' | 'NEEDS_CLARIFICATION' | 'RESOLVED';
}

export interface ClarificationAnswer {
  id: number;
  question_id: number;
  raw_transcript?: string;
  extracted_value: string;
  confirmed_by_user: boolean;
  timestamp: string;
}

export interface ClarificationQuestion {
  id: number;
  bill_id: number;
  target_item_id?: number;
  field_name: string;
  question_hinglish: string;
  question_type: string;
  status: 'PENDING' | 'ANSWERED' | 'SKIPPED';
  created_at: string;
  answers: ClarificationAnswer[];
}

export interface Bill {
  id: number;
  file_path: string;
  original_filename: string;
  file_type: string;
  bill_type: 'SALES' | 'PURCHASE' | 'UNKNOWN';
  invoice_number?: string;
  invoice_date?: string;
  party_name?: string;
  party_address?: string;
  contact_details?: string;
  subtotal: number;
  discount: number;
  additional_charges: number;
  round_off: number;
  final_amount: number;
  status: 'UPLOADED' | 'PROCESSING' | 'CLARIFICATION_REQUIRED' | 'READY_FOR_APPROVAL' | 'APPROVED' | 'POSTED' | 'FAILED';
  is_gst_detected: boolean;
  gst_warning_text?: string;
  confidence_score: number;
  created_at: string;
  updated_at: string;
  items: BillItem[];
}

export interface VoucherItemLine {
  item_name: string;
  stock_item_name: string;
  quantity: number;
  unit: string;
  rate: number;
  amount: number;
  discount: number;
  original_quantity?: number;
  original_rate?: number;
  original_unit?: string;
  conversion_applied?: string;
}

export interface VoucherPreview {
  id: number;
  bill_id: number;
  voucher_type: string;
  party_ledger: string;
  sales_purchase_ledger: string;
  invoice_number: string;
  invoice_date: string;
  items: VoucherItemLine[];
  subtotal: number;
  discount: number;
  additional_charges: number;
  round_off: number;
  final_amount: number;
  narration?: string;
  is_approved: boolean;
  approved_at?: string;
  created_at: string;
  suggested_party_ledger?: string;
  party_match_confidence?: number;
  is_party_matched?: boolean;
  file_path?: string;
}

export interface PartyMapping {
  raw_name: string;
  tally_ledger_name: string;
  is_verified: boolean;
  created_at?: string;
}

export interface SuggestLedgerResult {
  raw_name: string;
  exact_match?: string;
  suggested_ledger?: string;
  parent_group?: string;
  confidence: number;
  candidates: Array<{ name: string; parent?: string; score: number }>;
}

export interface DashboardStats {
  total_bills: number;
  sales_bills: number;
  purchase_bills: number;
  pending_clarifications: number;
  ready_for_approval: number;
  posted_to_tally: number;
  failed_transactions: number;
  tally_connected: boolean;
  active_company: string | null;
}

export interface TallyStatus {
  is_connected: boolean;
  status: 'CONNECTED' | 'DISCONNECTED' | 'COMPANY_NOT_SELECTED' | 'ERROR';
  endpoint: string;
  company_name: string | null;
  message: string;
}

export interface TallyMasterItem {
  name: string;
  parent?: string;
  unit?: string;
}

export interface TallyMastersData {
  ledgers: TallyMasterItem[];
  stock_items: TallyMasterItem[];
  units: string[];
  total_ledgers: number;
  total_stock_items: number;
  last_synced: string | null;
  is_default_fallback?: boolean;
}

export interface TallySyncResult {
  success: boolean;
  company_name?: string;
  ledgers_synced: number;
  stock_items_synced: number;
  units_synced: number;
  timestamp: string;
  message: string;
}

