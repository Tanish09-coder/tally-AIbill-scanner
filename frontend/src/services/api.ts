import axios from 'axios';
import {
  Bill,
  DashboardStats,
  TallyStatus,
  ClarificationQuestion,
  VoucherPreview,
  TallyMastersData,
  TallySyncResult,
} from '../types';

const client = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // Dashboard
  getStats: async (): Promise<DashboardStats> => {
    const res = await client.get('/dashboard/stats');
    return res.data;
  },

  // Tally
  getTallyStatus: async (): Promise<TallyStatus> => {
    const res = await client.get('/tally/status');
    return res.data;
  },
  syncTallyMasters: async (): Promise<TallySyncResult> => {
    const res = await client.post('/tally/sync-masters');
    return res.data;
  },
  getTallyMasters: async (): Promise<TallyMastersData> => {
    const res = await client.get('/tally/masters');
    return res.data;
  },
  savePartyMapping: async (rawName: string, tallyLedgerName: string) => {
    const res = await client.post('/tally/party-mapping', {
      raw_name: rawName,
      tally_ledger_name: tallyLedgerName,
    });
    return res.data;
  },
  getPartyMappings: async () => {
    const res = await client.get('/tally/party-mappings');
    return res.data;
  },
  suggestLedger: async (rawName: string, billType?: string) => {
    const res = await client.post('/tally/suggest-ledger', {
      raw_name: rawName,
      bill_type: billType,
    });
    return res.data;
  },
  createLedger: async (ledgerName: string, parentGroup: string = "Sundry Debtors") => {
    const res = await client.post('/tally/create-ledger', {
      ledger_name: ledgerName,
      parent_group: parentGroup,
      confirmed: true
    });
    return res.data;
  },
  createStockItem: async (itemName: string, parentGroup: string = "Primary", uom: string = "NOS") => {
    const res = await client.post('/tally/create-stock-item', {
      item_name: itemName,
      parent_group: parentGroup,
      uom: uom,
      confirmed: true
    });
    return res.data;
  },

  // Bills
  getBills: async (statusFilter?: string, typeFilter?: string): Promise<{ total: number; bills: Bill[] }> => {
    const params: Record<string, string> = {};
    if (statusFilter) params.status_filter = statusFilter;
    if (typeFilter) params.bill_type_filter = typeFilter;
    const res = await client.get('/bills/', { params });
    return res.data;
  },

  getBill: async (id: number): Promise<Bill> => {
    const res = await client.get(`/bills/${id}`);
    return res.data;
  },

  uploadBills: async (files: File[], billTypeHint?: string): Promise<Bill[]> => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    if (billTypeHint) formData.append('bill_type_hint', billTypeHint);

    const res = await client.post('/bills/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  scanBill: async (id: number): Promise<Bill> => {
    const res = await client.post(`/bills/${id}/scan`);
    return res.data;
  },

  deleteBill: async (id: number): Promise<{ success: boolean; message: string }> => {
    const res = await client.delete(`/bills/${id}`);
    return res.data;
  },

  deleteFailedBills: async (): Promise<{ success: boolean; message: string; deleted_count: number }> => {
    const res = await client.delete('/bills/cleanup/failed');
    return res.data;
  },

  // Clarifications
  getQuestions: async (billId: number): Promise<ClarificationQuestion[]> => {
    const res = await client.get(`/clarifications/bills/${billId}/questions`);
    return res.data;
  },

  answerQuestion: async (
    questionId: number,
    userResponse: string,
    isVoice: boolean = false
  ) => {
    const res = await client.post(`/clarifications/questions/${questionId}/answer`, {
      question_id: questionId,
      user_response: userResponse,
      is_voice: isVoice,
    });
    return res.data;
  },

  // Vouchers
  getVoucherPreview: async (billId: number): Promise<VoucherPreview> => {
    const res = await client.get(`/vouchers/bills/${billId}/preview`);
    return res.data;
  },

  updateVoucher: async (voucherId: number, data: Partial<VoucherPreview>): Promise<VoucherPreview> => {
    const res = await client.put(`/vouchers/${voucherId}`, data);
    return res.data;
  },

  approveAndPost: async (voucherId: number) => {
    const res = await client.post(`/vouchers/${voucherId}/approve-and-post`, {
      voucher_id: voucherId,
      confirmed: true,
    });
    return res.data;
  },

  // Voice STT & TTS
  textToSpeech: async (text: string) => {
    const res = await client.post('/voice/tts', { text });
    return res.data;
  },

  transcribeAudio: async (audioBlob: Blob): Promise<{ transcript: string }> => {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'mic_record.wav');
    const res = await client.post('/voice/stt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
};

