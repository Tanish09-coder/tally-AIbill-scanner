import React, { useState, useEffect, useMemo, useRef } from 'react';
import { VoucherPreview, VoucherItemLine, TallyMastersData } from '../../types';
import { X, CheckCircle, Loader2, ArrowRight, UserPlus, RefreshCw, Layers, Edit3, Trash2, Plus } from 'lucide-react';
import { api } from '../../services/api';
import { SearchableSelect, SelectOption } from '../common/SearchableSelect';

// Intelligent fuzzy & token similarity helper for matching raw text against Tally masters
function computeBestMatch(
  query: string,
  ledgers: Array<{ name: string; parent?: string }>
): { name: string; parent?: string; score: number; isExact: boolean } | null {
  if (!query || !ledgers || ledgers.length === 0) return null;
  const cleanQ = query.toLowerCase().replace(/[,.\-_/()[\]]/g, ' ').trim().replace(/\s+/g, ' ');
  if (!cleanQ) return null;
  const wordsQ = new Set(cleanQ.split(' ').filter(Boolean));

  let best: { name: string; parent?: string; score: number; isExact: boolean } | null = null;
  let bestScore = 0;

  for (const l of ledgers) {
    const cleanL = l.name.toLowerCase().replace(/[,.\-_/()[\]]/g, ' ').trim().replace(/\s+/g, ' ');
    if (cleanQ === cleanL) {
      return { name: l.name, parent: l.parent, score: 1.0, isExact: true };
    }

    const wordsL = new Set(cleanL.split(' ').filter(Boolean));
    let score = 0;

    // 1. Prefix match boost (e.g. "harsh industries" inside "harsh industries , ghoti")
    if (cleanL.startsWith(cleanQ) || cleanQ.startsWith(cleanL)) {
      const minLen = Math.min(cleanQ.length, cleanL.length);
      const maxLen = Math.max(cleanQ.length, cleanL.length);
      score = Math.max(score, 0.90 + (minLen / maxLen) * 0.08);
    }

    // 2. Word subset check (all words of one are inside the other)
    let common = 0;
    wordsQ.forEach((w) => {
      if (wordsL.has(w)) common++;
    });

    const isSubset = common === wordsQ.size || common === wordsL.size;
    if (isSubset && common > 0) {
      const subsetScore = 0.88 + (common / Math.max(wordsQ.size, wordsL.size)) * 0.10;
      score = Math.max(score, subsetScore);
    } else if (common > 0) {
      const jaccard = common / (wordsQ.size + wordsL.size - common);
      if (jaccard >= 0.4) {
        score = Math.max(score, 0.70 + jaccard * 0.25);
      }
    }

    if (score > bestScore) {
      bestScore = score;
      best = { name: l.name, parent: l.parent, score, isExact: score >= 0.98 };
    }
  }

  if (best && bestScore >= 0.60) {
    return best;
  }
  return null;
}

interface VoucherPreviewModalProps {
  voucher: VoucherPreview;
  onClose: () => void;
  onSuccessPost: () => void;
}

export const VoucherPreviewModal: React.FC<VoucherPreviewModalProps> = ({
  voucher,
  onClose,
  onSuccessPost,
}) => {
  const [currentVoucher, setCurrentVoucher] = useState<VoucherPreview>(voucher);
  const [masters, setMasters] = useState<TallyMastersData | null>(null);
  const [isLoadingMasters, setIsLoadingMasters] = useState(false);
  const [isSyncingMasters, setIsSyncingMasters] = useState(false);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);

  const [isPosting, setIsPosting] = useState(false);
  const [isCreatingLedger, setIsCreatingLedger] = useState(false);
  const [postResult, setPostResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingItemIndex, setEditingItemIndex] = useState<number | null>(null);

  // Load masters on mount
  useEffect(() => {
    loadMasters();
  }, []);

  // Ensure default accounting ledger strictly matches voucher type (Sales -> SALES A/C, Purchase -> PURCHASE A/C)
  useEffect(() => {
    const isSales = currentVoucher.voucher_type.toLowerCase() === 'sales';
    const targetDefault = isSales ? 'SALES A/C' : 'PURCHASE A/C';
    const current = (currentVoucher.sales_purchase_ledger || '').trim();

    if (
      (isSales && current.toLowerCase().includes('purchase')) ||
      (!isSales && current.toLowerCase().includes('sales')) ||
      current === 'Sales Accounts' ||
      current === 'Purchase Accounts' ||
      !current
    ) {
      setCurrentVoucher((prev) => ({ ...prev, sales_purchase_ledger: targetDefault }));
      api.updateVoucher(currentVoucher.id, { sales_purchase_ledger: targetDefault }).catch(() => {});
    }
  }, [currentVoucher.voucher_type]);

  const loadMasters = async () => {
    setIsLoadingMasters(true);
    try {
      const data = await api.getTallyMasters();
      setMasters(data);
    } catch (err) {
      console.warn('Could not load cached masters:', err);
    } finally {
      setIsLoadingMasters(false);
    }
  };

  const handleSyncMasters = async () => {
    setIsSyncingMasters(true);
    setSyncNotice(null);
    setError(null);
    try {
      const res = await api.syncTallyMasters();
      if (res.success) {
        setSyncNotice(res.message || `Synced ${res.ledgers_synced} ledgers from Tally!`);
        await loadMasters();
      } else {
        setError(res.message || 'Failed to sync masters from Tally.');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to sync with TallyPrime. Ensure company is open.');
    } finally {
      setIsSyncingMasters(false);
    }
  };

  // Check if current party exists verbatim in Tally masters
  const isCurrentPartyExact = useMemo(() => {
    if (!masters?.ledgers || !currentVoucher.party_ledger) return false;
    const cleanCurrent = currentVoucher.party_ledger.trim().toLowerCase();
    return masters.ledgers.some((l) => l.name.trim().toLowerCase() === cleanCurrent);
  }, [masters, currentVoucher.party_ledger]);

  // Compute best suggested master from Tally
  const suggestedParty = useMemo(() => {
    if (!masters?.ledgers || !currentVoucher.party_ledger) return null;
    return computeBestMatch(currentVoucher.party_ledger, masters.ledgers);
  }, [masters, currentVoucher.party_ledger]);

  // Check if error contains missing ledger name
  const missingLedgerMatch = error ? error.match(/Ledger '([^']+)' does not exist/i) : null;
  const missingLedgerName = missingLedgerMatch ? missingLedgerMatch[1] : null;

  // Compute best suggestion for the missing ledger
  const errorSuggestedParty = useMemo(() => {
    if (!missingLedgerName || !masters?.ledgers) return null;
    return computeBestMatch(missingLedgerName, masters.ledgers);
  }, [missingLedgerName, masters]);

  // Build sorted options for Party Ledgers
  const partyLedgerOptions = useMemo<SelectOption[]>(() => {
    if (!masters || !masters.ledgers) {
      return [
        { value: 'Cash', label: 'Cash', group: 'Cash-in-Hand' },
        { value: currentVoucher.party_ledger, label: currentVoucher.party_ledger, group: 'Detected Party' },
      ];
    }
    const isSales = currentVoucher.voucher_type.toLowerCase() === 'sales';
    const primaryGroup = isSales ? 'Sundry Debtors' : 'Sundry Creditors';

    const list = [...masters.ledgers];
    // Sort so primary group and Cash come first
    list.sort((a, b) => {
      const aIsPrimary = a.parent?.toLowerCase().includes(primaryGroup.toLowerCase()) || a.name.toLowerCase() === 'cash';
      const bIsPrimary = b.parent?.toLowerCase().includes(primaryGroup.toLowerCase()) || b.name.toLowerCase() === 'cash';
      if (aIsPrimary && !bIsPrimary) return -1;
      if (!aIsPrimary && bIsPrimary) return 1;
      return a.name.localeCompare(b.name);
    });

    const opts: SelectOption[] = list.map((l) => ({
      value: l.name,
      label: l.name,
      group: l.parent || 'General Ledger',
    }));

    // If suggested match exists and current is not exact match, put suggested at the very top!
    if (suggestedParty && !isCurrentPartyExact) {
      opts.unshift({
        value: suggestedParty.name,
        label: `💡 ${suggestedParty.name} (${Math.round(suggestedParty.score * 100)}% Match)`,
        group: '✨ Suggested Master (from Tally)',
      });
    }

    // Ensure currently selected party is present
    if (
      currentVoucher.party_ledger &&
      !opts.some((o) => o.value.toLowerCase() === currentVoucher.party_ledger.toLowerCase())
    ) {
      opts.unshift({
        value: currentVoucher.party_ledger,
        label: currentVoucher.party_ledger,
        group: 'Raw Bill Party',
      });
    }

    return opts;
  }, [masters, currentVoucher.voucher_type, currentVoucher.party_ledger, suggestedParty, isCurrentPartyExact]);

  // Build sorted options for Accounting Ledgers (Sales -> SALES A/C, Purchase -> PURCHASE A/C)
  const accountingLedgerOptions = useMemo<SelectOption[]>(() => {
    const isSales = currentVoucher.voucher_type.toLowerCase() === 'sales';
    const targetParent = isSales ? 'sales accounts' : 'purchase accounts';
    const targetDefault = isSales ? 'SALES A/C' : 'PURCHASE A/C';

    if (!masters || !masters.ledgers) {
      return [
        { value: targetDefault, label: targetDefault, group: isSales ? 'Sales Accounts' : 'Purchase Accounts' },
      ];
    }

    // Filter to relevant Sales/Purchase accounts from user's Tally masters
    const matchingLedgers = masters.ledgers.filter((l) => {
      const parent = (l.parent || '').toLowerCase();
      const name = l.name.toLowerCase();
      return parent.includes(targetParent) || (isSales ? name.includes('sale') : name.includes('purchase'));
    });

    const opts: SelectOption[] = matchingLedgers.map((l) => ({
      value: l.name,
      label: l.name,
      group: l.parent || (isSales ? 'Sales Accounts' : 'Purchase Accounts'),
    }));

    if (!opts.some((o) => o.value.toUpperCase() === targetDefault)) {
      opts.unshift({
        value: targetDefault,
        label: targetDefault,
        group: isSales ? 'Sales Accounts' : 'Purchase Accounts',
      });
    }

    // Put primary default (SALES A/C or PURCHASE A/C) at the very top
    opts.sort((a, b) => {
      if (a.value.toUpperCase() === targetDefault) return -1;
      if (b.value.toUpperCase() === targetDefault) return 1;
      return a.label.localeCompare(b.label);
    });

    return opts;
  }, [masters, currentVoucher.voucher_type]);

  // Stock items options
  const stockItemOptions = useMemo<SelectOption[]>(() => {
    if (!masters || !masters.stock_items) return [];
    return masters.stock_items.map((item) => ({
      value: item.name,
      label: item.name,
      group: item.parent || 'Stock Item',
      subLabel: item.unit ? `Unit: ${item.unit}` : undefined,
    }));
  }, [masters]);

  // Handle party change and auto-save
  const handlePartyChange = async (newParty: string) => {
    const rawOrig = currentVoucher.party_ledger;
    setCurrentVoucher((prev) => ({ ...prev, party_ledger: newParty }));
    setError(null);
    try {
      await api.updateVoucher(currentVoucher.id, { party_ledger: newParty });
      if (rawOrig && rawOrig.toLowerCase() !== newParty.toLowerCase()) {
        await api.savePartyMapping(rawOrig, newParty);
      }
    } catch (err) {
      console.warn('Auto-save failed:', err);
    }
  };

  // Accept suggested party with 1 click
  const handleAcceptSuggestedParty = async (suggestedName: string) => {
    const rawOrig = currentVoucher.party_ledger;
    setCurrentVoucher((prev) => ({ ...prev, party_ledger: suggestedName }));
    setError(null);
    try {
      await api.updateVoucher(currentVoucher.id, { party_ledger: suggestedName });
      if (rawOrig && rawOrig.toLowerCase() !== suggestedName.toLowerCase()) {
        await api.savePartyMapping(rawOrig, suggestedName);
      }
    } catch (err) {
      console.warn('Auto-save suggestion failed:', err);
    }
  };

  // Handle switch to suggested master and post immediately
  const handleSwitchAndPost = async (suggestedName: string) => {
    setIsPosting(true);
    setError(null);
    try {
      const rawOrig = currentVoucher.party_ledger;
      setCurrentVoucher((prev) => ({ ...prev, party_ledger: suggestedName }));
      await api.updateVoucher(currentVoucher.id, {
        party_ledger: suggestedName,
        sales_purchase_ledger: currentVoucher.sales_purchase_ledger,
        items: currentVoucher.items,
      });
      if (rawOrig && rawOrig.toLowerCase() !== suggestedName.toLowerCase()) {
        await api.savePartyMapping(rawOrig, suggestedName);
      }
      const res = await api.approveAndPost(currentVoucher.id);
      if (res.success) {
        setPostResult(res);
        onSuccessPost();
      } else {
        setError(res.message || 'Tally rejected the voucher.');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to communicate with TallyPrime.');
    } finally {
      setIsPosting(false);
    }
  };

  // Handle accounting ledger change and auto-save
  const handleAccountChange = async (newAcct: string) => {
    setCurrentVoucher((prev) => ({ ...prev, sales_purchase_ledger: newAcct }));
    try {
      await api.updateVoucher(currentVoucher.id, { sales_purchase_ledger: newAcct });
    } catch (err) {
      console.warn('Auto-save failed:', err);
    }
  };

  // Handle invoice date change and auto-save
  const handleDateChange = async (newDate: string) => {
    setCurrentVoucher((prev) => ({ ...prev, invoice_date: newDate }));
    try {
      await api.updateVoucher(currentVoucher.id, { invoice_date: newDate });
    } catch (err) {
      console.warn('Auto-save date failed:', err);
    }
  };

  // Handle stock item name change for a line item
  const handleStockItemChange = async (idx: number, newStockItemName: string) => {
    const updatedItems = [...currentVoucher.items];
    const itemMaster = masters?.stock_items.find(
      (m) => m.name.toLowerCase() === newStockItemName.toLowerCase()
    );
    const targetUnit = itemMaster?.unit || 'KG';
    const it = updatedItems[idx];

    let finalQty = it.quantity;
    let finalRate = it.rate;
    let finalUnit = targetUnit;
    let convApplied = it.conversion_applied;

    const origUnit = (it.original_unit || it.unit).toUpperCase();
    const origQty = it.original_quantity || it.quantity;
    const origRate = it.original_rate || it.rate;

    // Handle QTL -> KG conversion dynamically if target is KG and original was QTL
    if ((origUnit.includes('QTL') || origUnit.includes('QUINTAL') || origUnit === 'Q') && targetUnit.toUpperCase() === 'KG') {
      finalQty = origQty * 100.0;
      finalRate = origRate / 100.0;
      finalUnit = 'KG';
      convApplied = `Converted from ${origQty} QTL @ ₹${origRate}/QTL`;
    }

    updatedItems[idx] = {
      ...it,
      stock_item_name: newStockItemName,
      quantity: finalQty,
      rate: finalRate,
      unit: finalUnit,
      conversion_applied: convApplied,
    };

    setCurrentVoucher((prev) => ({ ...prev, items: updatedItems }));
    setEditingItemIndex(null);

    try {
      await api.updateVoucher(currentVoucher.id, { items: updatedItems });
    } catch (err) {
      console.warn('Auto-save item failed:', err);
    }
  };

  // Auto-sync debounced ref
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const syncVoucherToBackend = (v: VoucherPreview) => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(async () => {
      try {
        await api.updateVoucher(v.id, {
          items: v.items,
          subtotal: v.subtotal,
          discount: v.discount,
          additional_charges: v.additional_charges,
          round_off: v.round_off,
          final_amount: v.final_amount,
        });
      } catch (err) {
        console.warn('Auto-sync voucher details failed:', err);
      }
    }, 400);
  };

  // Handle line item field changes: quantity, unit, rate, amount
  const handleItemFieldChange = (
    idx: number,
    field: 'quantity' | 'unit' | 'rate' | 'amount',
    value: string | number
  ) => {
    const updatedItems = [...currentVoucher.items];
    const it = { ...updatedItems[idx] };

    if (field === 'quantity') {
      const q = typeof value === 'number' ? value : parseFloat(value) || 0;
      it.quantity = q;
      // Auto-recalculate amount: Qty * Rate
      it.amount = Math.round(q * (it.rate || 0) * 100) / 100;
    } else if (field === 'rate') {
      const r = typeof value === 'number' ? value : parseFloat(value) || 0;
      it.rate = r;
      // Auto-recalculate amount: Qty * Rate
      it.amount = Math.round((it.quantity || 0) * r * 100) / 100;
    } else if (field === 'amount') {
      const a = typeof value === 'number' ? value : parseFloat(value) || 0;
      it.amount = a;
      // Auto-recalculate rate: Amount / Qty (if qty > 0)
      if (it.quantity > 0) {
        it.rate = Math.round((a / it.quantity) * 100) / 100;
      }
    } else if (field === 'unit') {
      it.unit = String(value);
    }

    updatedItems[idx] = it;

    // Recalculate subtotal and final_amount
    const newSubtotal = Math.round(updatedItems.reduce((acc, item) => acc + (Number(item.amount) || 0), 0) * 100) / 100;
    const newFinal = Math.round(
      (newSubtotal - (currentVoucher.discount || 0) + (currentVoucher.additional_charges || 0) + (currentVoucher.round_off || 0)) * 100
    ) / 100;

    const newVoucher = {
      ...currentVoucher,
      items: updatedItems,
      subtotal: newSubtotal,
      final_amount: newFinal,
    };

    setCurrentVoucher(newVoucher);
    syncVoucherToBackend(newVoucher);
  };

  // Add a new empty line item
  const handleAddItem = () => {
    const defaultStock = stockItemOptions[0]?.value || 'Item';
    const newItem: VoucherItemLine = {
      item_name: defaultStock,
      stock_item_name: defaultStock,
      quantity: 1,
      unit: 'KG',
      rate: 0,
      amount: 0,
      discount: 0,
    };
    const updatedItems = [...currentVoucher.items, newItem];
    const newSubtotal = Math.round(updatedItems.reduce((acc, item) => acc + (Number(item.amount) || 0), 0) * 100) / 100;
    const newFinal = Math.round(
      (newSubtotal - (currentVoucher.discount || 0) + (currentVoucher.additional_charges || 0) + (currentVoucher.round_off || 0)) * 100
    ) / 100;

    const newVoucher = {
      ...currentVoucher,
      items: updatedItems,
      subtotal: newSubtotal,
      final_amount: newFinal,
    };
    setCurrentVoucher(newVoucher);
    syncVoucherToBackend(newVoucher);
  };

  // Delete a line item
  const handleDeleteItem = (idx: number) => {
    if (currentVoucher.items.length <= 1) return;
    const updatedItems = currentVoucher.items.filter((_, i) => i !== idx);
    const newSubtotal = Math.round(updatedItems.reduce((acc, item) => acc + (Number(item.amount) || 0), 0) * 100) / 100;
    const newFinal = Math.round(
      (newSubtotal - (currentVoucher.discount || 0) + (currentVoucher.additional_charges || 0) + (currentVoucher.round_off || 0)) * 100
    ) / 100;

    const newVoucher = {
      ...currentVoucher,
      items: updatedItems,
      subtotal: newSubtotal,
      final_amount: newFinal,
    };
    setCurrentVoucher(newVoucher);
    syncVoucherToBackend(newVoucher);
  };

  // Handle editing totals (Discount, Hamali, Round Off)
  const handleTotalsChange = (updates: { discount?: number; additional_charges?: number; round_off?: number }) => {
    const nextDisc = updates.discount !== undefined ? updates.discount : (currentVoucher.discount || 0);
    const nextAddl = updates.additional_charges !== undefined ? updates.additional_charges : (currentVoucher.additional_charges || 0);
    const nextRound = updates.round_off !== undefined ? updates.round_off : (currentVoucher.round_off || 0);

    const newFinal = Math.round(((currentVoucher.subtotal || 0) - nextDisc + nextAddl + nextRound) * 100) / 100;

    const newVoucher = {
      ...currentVoucher,
      discount: nextDisc,
      additional_charges: nextAddl,
      round_off: nextRound,
      final_amount: newFinal,
    };

    setCurrentVoucher(newVoucher);
    syncVoucherToBackend(newVoucher);
  };

  const handleApproveAndPost = async () => {
    setIsPosting(true);
    setError(null);
    setSyncNotice(null);
    try {
      // First ensure latest updates are synced to backend
      await api.updateVoucher(currentVoucher.id, {
        party_ledger: currentVoucher.party_ledger,
        sales_purchase_ledger: currentVoucher.sales_purchase_ledger,
        invoice_date: currentVoucher.invoice_date,
        items: currentVoucher.items,
        subtotal: currentVoucher.subtotal,
        discount: currentVoucher.discount,
        additional_charges: currentVoucher.additional_charges,
        round_off: currentVoucher.round_off,
        final_amount: currentVoucher.final_amount,
      });

      const res = await api.approveAndPost(currentVoucher.id);
      if (res.success) {
        setPostResult(res);
        onSuccessPost();
      } else {
        setError(res.message || 'Tally rejected the voucher.');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to communicate with TallyPrime.');
    } finally {
      setIsPosting(false);
    }
  };

  const handleCreateMissingLedger = async (ledgerName: string) => {
    setIsCreatingLedger(true);
    setError(null);
    try {
      const group = currentVoucher.voucher_type.toLowerCase() === 'sales' ? 'Sundry Debtors' : 'Sundry Creditors';
      await api.createLedger(ledgerName, group);
      await loadMasters(); // Refresh masters cache
      // Retry posting voucher
      await handleApproveAndPost();
    } catch (err: any) {
      setError(err?.response?.data?.detail || `Failed to create ledger '${ledgerName}' in Tally.`);
    } finally {
      setIsCreatingLedger(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-2xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="bg-slate-900 text-white p-4 sm:p-5 flex items-center justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Non-GST {currentVoucher.voucher_type} Voucher
              </span>
              <span className="text-xs text-slate-400">Ref: #{currentVoucher.invoice_number}</span>
            </div>
            <h2 className="text-base sm:text-lg font-bold mt-1">TallyPrime Voucher Verification & Mapping</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Sync Masters Notification Sub-Header */}
        <div className="bg-slate-100 border-b border-slate-200 px-5 py-2.5 flex items-center justify-between text-xs text-slate-600">
          <div className="flex items-center gap-2 truncate pr-2">
            <Layers className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="truncate">
              Tally Masters: <strong>{masters?.total_ledgers ?? 0} ledgers</strong>,{' '}
              <strong>{masters?.total_stock_items ?? 0} items</strong> loaded
              {masters?.is_default_fallback && ' (Default set)'}
            </span>
          </div>
          <button
            type="button"
            onClick={handleSyncMasters}
            disabled={isSyncingMasters || isLoadingMasters}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-slate-300 text-slate-700 hover:border-emerald-500 hover:text-emerald-700 font-semibold transition disabled:opacity-50 shrink-0 shadow-2xs cursor-pointer"
            title="Fetch latest ledgers & items from TallyPrime"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncingMasters ? 'animate-spin text-emerald-600' : ''}`} />
            <span>{isSyncingMasters ? 'Syncing...' : 'Sync Masters'}</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 sm:p-6 space-y-4 overflow-y-auto text-slate-800 text-xs sm:text-sm">
          {syncNotice && (
            <div className="p-3 bg-emerald-50 border border-emerald-300 rounded-xl text-emerald-900 text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{syncNotice}</span>
            </div>
          )}

          {/* Smart Tally Master Suggestion Box */}
          {!isCurrentPartyExact && suggestedParty && (
            <div className="bg-linear-to-r from-amber-50 to-orange-50 border-2 border-amber-300 rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in slide-in-from-top duration-300">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-amber-500/20 text-amber-700 flex items-center justify-center shrink-0 text-lg">
                  💡
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-amber-950 uppercase tracking-wide">
                      Tally Master Suggestion
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-200 text-amber-900 font-bold">
                      {Math.round(suggestedParty.score * 100)}% Match
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 mt-1">
                    Bill party <strong>"{currentVoucher.party_ledger}"</strong> ke liye Tally master mila hai:{' '}
                    <strong className="text-emerald-800 text-sm font-bold">"{suggestedParty.name}"</strong>
                    {suggestedParty.parent && (
                      <span className="text-slate-500 text-[11px] ml-1.5 font-medium">({suggestedParty.parent})</span>
                    )}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleAcceptSuggestedParty(suggestedParty.name)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white rounded-xl text-xs font-bold shrink-0 shadow-md shadow-emerald-600/20 flex items-center justify-center gap-1.5 cursor-pointer transition"
              >
                <CheckCircle className="w-4 h-4" />
                <span>Use "{suggestedParty.name}"</span>
              </button>
            </div>
          )}

          {/* Party and Account Selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div>
              <SearchableSelect
                label="Buyer / Seller Party Ledger (Tally)"
                value={currentVoucher.party_ledger}
                options={partyLedgerOptions}
                onChange={handlePartyChange}
                placeholder="Search or pick party..."
                allowCustom={true}
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                Select buyer/seller from Tally or type custom name.
              </span>
            </div>

            <div>
              <SearchableSelect
                label="Accounting Ledger (Sales / Purchase)"
                value={currentVoucher.sales_purchase_ledger}
                options={accountingLedgerOptions}
                onChange={handleAccountChange}
                placeholder="Search accounting ledger..."
                allowCustom={true}
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                Tally account ledger (Non-GST Sales or Purchase).
              </span>
            </div>

            <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-200 sm:col-span-2">
              <div className="flex items-center gap-2">
                <span className="text-slate-600 font-medium">Invoice Date:</span>
                <input
                  type="text"
                  value={currentVoucher.invoice_date}
                  onChange={(e) => handleDateChange(e.target.value)}
                  placeholder="DD-MM-YYYY"
                  className="px-2.5 py-1 bg-white border border-slate-300 rounded-lg text-xs font-bold text-slate-900 focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs w-32"
                  title="Edit invoice date (DD-MM-YYYY) before creating voucher in Tally"
                />
              </div>
              <div>
                <span className="text-slate-500">Voucher Type: </span>
                <span className="font-semibold text-slate-800">{currentVoucher.voucher_type} (Non-GST)</span>
              </div>
            </div>
          </div>

          {/* Items Table with Stock Item mapping */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-slate-700">Line Items & Stock Item Matching:</span>
              <span className="text-[11px] text-slate-500">Click item name to remap to Tally stock</span>
            </div>

            {/* Auto Unit Conversion Alert */}
            {currentVoucher.items.some((it) => it.conversion_applied || (it.original_unit && it.original_unit !== it.unit)) && (
              <div className="mb-2 p-2.5 bg-indigo-50 border border-indigo-200 rounded-xl text-indigo-900 text-xs flex items-center justify-between gap-2 shadow-2xs">
                <div className="flex items-center gap-2">
                  <span className="text-sm">⚖️</span>
                  <span>
                    <strong>Auto Unit Conversion:</strong> Mandi bill Quintal (QTL) units ko Tally ke master <strong>KG</strong> mein convert kiya gaya hai (1 QTL = 100 KG). Rates automatically adjust ho gaye hain.
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded-full bg-indigo-200 text-indigo-900 font-bold text-[10px] shrink-0">
                  1 QTL = 100 KG
                </span>
              </div>
            )}

            <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3">Item / Stock Name</th>
                    <th className="py-2.5 px-2 text-right w-24">Qty</th>
                    <th className="py-2.5 px-2 text-center w-20">Unit</th>
                    <th className="py-2.5 px-2 text-right w-28">Rate</th>
                    <th className="py-2.5 px-2 text-right w-32">Amount</th>
                    <th className="py-2.5 px-1 text-center w-8"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {currentVoucher.items.map((it, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/70 transition">
                      <td className="py-2.5 px-3 font-medium text-slate-900 max-w-[200px] align-top">
                        {editingItemIndex === idx && stockItemOptions.length > 0 ? (
                          <div className="flex items-center gap-1.5">
                            <SearchableSelect
                              compact={true}
                              value={it.stock_item_name || it.item_name}
                              options={stockItemOptions}
                              onChange={(val) => handleStockItemChange(idx, val)}
                              placeholder="Select Tally stock item..."
                              allowCustom={true}
                              className="w-full"
                            />
                            <button
                              type="button"
                              onClick={() => setEditingItemIndex(null)}
                              className="text-slate-400 hover:text-slate-600 p-1 cursor-pointer"
                              title="Cancel"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div
                            onClick={() => setEditingItemIndex(idx)}
                            className="cursor-pointer group flex items-center justify-between gap-1 hover:text-emerald-700"
                            title="Click to change Tally stock item"
                          >
                            <span className="truncate font-bold text-slate-900">{it.stock_item_name || it.item_name}</span>
                            <Edit3 className="w-3 h-3 text-slate-400 group-hover:text-emerald-600 opacity-60 group-hover:opacity-100 shrink-0" />
                          </div>
                        )}
                        {it.stock_item_name && it.stock_item_name !== it.item_name && (
                          <span className="block text-[10px] text-slate-400 truncate mt-0.5">
                            OCR: {it.item_name}
                          </span>
                        )}
                      </td>

                      {/* Editable Qty */}
                      <td className="py-2 px-2 text-right align-top">
                        <input
                          type="number"
                          step="any"
                          value={it.quantity === 0 ? '' : it.quantity}
                          placeholder="0"
                          onChange={(e) => {
                            const val = e.target.value === '' ? 0 : parseFloat(e.target.value);
                            handleItemFieldChange(idx, 'quantity', isNaN(val) ? 0 : val);
                          }}
                          className="w-full px-2 py-1 text-right text-xs font-mono font-bold text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs"
                          title="Edit quantity"
                        />
                        {it.original_quantity && it.original_unit && it.original_unit !== it.unit && (
                          <span className="block text-[10px] text-emerald-700 font-sans font-semibold mt-0.5 text-right" title={`Original from bill: ${it.original_quantity} ${it.original_unit}`}>
                            ⚡ {it.original_quantity} {it.original_unit}
                          </span>
                        )}
                      </td>

                      {/* Editable Unit */}
                      <td className="py-2 px-2 text-center align-top">
                        <input
                          type="text"
                          value={it.unit}
                          onChange={(e) => {
                            handleItemFieldChange(idx, 'unit', e.target.value.toUpperCase());
                          }}
                          placeholder="Unit"
                          className="w-full px-1.5 py-1 text-center text-xs font-bold uppercase text-slate-700 bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:bg-white focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs"
                          title="Edit unit (KG, QTL, BAGS, NOS)"
                        />
                      </td>

                      {/* Editable Rate */}
                      <td className="py-2 px-2 text-right align-top">
                        <div className="relative">
                          <span className="absolute left-2 top-1.5 text-slate-400 text-xs">₹</span>
                          <input
                            type="number"
                            step="any"
                            value={it.rate === 0 ? '' : it.rate}
                            placeholder="0.00"
                            onChange={(e) => {
                              const val = e.target.value === '' ? 0 : parseFloat(e.target.value);
                              handleItemFieldChange(idx, 'rate', isNaN(val) ? 0 : val);
                            }}
                            className="w-full pl-5 pr-2 py-1 text-right text-xs font-mono text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs"
                            title="Edit rate per unit"
                          />
                        </div>
                        {it.original_rate && it.original_unit && it.original_unit !== it.unit && (
                          <span className="block text-[10px] text-slate-400 font-sans mt-0.5 text-right" title={`Original rate: ₹${it.original_rate}/${it.original_unit}`}>
                            ₹{it.original_rate.toFixed(0)}/{it.original_unit}
                          </span>
                        )}
                      </td>

                      {/* Editable Amount */}
                      <td className="py-2 px-2 text-right align-top">
                        <div className="relative">
                          <span className="absolute left-2 top-1.5 text-slate-400 text-xs">₹</span>
                          <input
                            type="number"
                            step="any"
                            value={it.amount === 0 ? '' : it.amount}
                            placeholder="0.00"
                            onChange={(e) => {
                              const val = e.target.value === '' ? 0 : parseFloat(e.target.value);
                              handleItemFieldChange(idx, 'amount', isNaN(val) ? 0 : val);
                            }}
                            className="w-full pl-5 pr-2 py-1 text-right text-xs font-mono font-bold text-slate-900 bg-white border border-slate-300 rounded-lg focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs"
                            title="Edit total amount"
                          />
                        </div>
                      </td>

                      {/* Delete Item */}
                      <td className="py-2 px-1 text-center align-top">
                        <button
                          type="button"
                          onClick={() => handleDeleteItem(idx)}
                          disabled={currentVoucher.items.length <= 1}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
                          title="Delete line item"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Add Item Row footer */}
              <div className="p-2.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
                <button
                  type="button"
                  onClick={handleAddItem}
                  className="px-3 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 rounded-lg flex items-center gap-1.5 transition cursor-pointer shadow-2xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Line Item</span>
                </button>
                <span className="text-[11px] text-slate-500">
                  Editing Qty or Rate recalculates Amount automatically.
                </span>
              </div>
            </div>
          </div>

          {/* Financial Totals (Editable) */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col gap-2 ml-auto sm:w-80 text-xs">
            <div className="flex justify-between items-center text-slate-600">
              <span className="font-medium">Subtotal:</span>
              <span className="font-mono font-bold text-slate-900">₹{currentVoucher.subtotal.toFixed(2)}</span>
            </div>

            <div className="flex justify-between items-center text-slate-600">
              <span className="font-medium">Discount:</span>
              <div className="flex items-center gap-1">
                <span className="text-slate-400 font-mono">-₹</span>
                <input
                  type="number"
                  step="any"
                  value={currentVoucher.discount || ''}
                  placeholder="0.00"
                  onChange={(e) => {
                    const d = parseFloat(e.target.value) || 0;
                    handleTotalsChange({ discount: d });
                  }}
                  className="w-24 px-2 py-0.5 text-right font-mono text-xs border border-slate-300 rounded-md bg-white focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs"
                  title="Edit discount amount"
                />
              </div>
            </div>

            <div className="flex justify-between items-center text-slate-600">
              <span className="font-medium">Addl. Charges (Hamali):</span>
              <div className="flex items-center gap-1">
                <span className="text-slate-400 font-mono">+₹</span>
                <input
                  type="number"
                  step="any"
                  value={currentVoucher.additional_charges || ''}
                  placeholder="0.00"
                  onChange={(e) => {
                    const a = parseFloat(e.target.value) || 0;
                    handleTotalsChange({ additional_charges: a });
                  }}
                  className="w-24 px-2 py-0.5 text-right font-mono text-xs border border-slate-300 rounded-md bg-white focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs"
                  title="Edit additional charges (Hamali)"
                />
              </div>
            </div>

            <div className="flex justify-between items-center text-slate-600">
              <span className="font-medium">Round Off:</span>
              <div className="flex items-center gap-1">
                <span className="text-slate-400 font-mono">₹</span>
                <input
                  type="number"
                  step="any"
                  value={currentVoucher.round_off || ''}
                  placeholder="0.00"
                  onChange={(e) => {
                    const ro = parseFloat(e.target.value) || 0;
                    handleTotalsChange({ round_off: ro });
                  }}
                  className="w-24 px-2 py-0.5 text-right font-mono text-xs border border-slate-300 rounded-md bg-white focus:outline-none focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 shadow-2xs"
                  title="Edit round off"
                />
              </div>
            </div>

            <div className="flex justify-between items-center text-sm font-bold text-slate-900 pt-2 border-t border-slate-200">
              <span>Final Total (Non-GST):</span>
              <span className="font-mono text-emerald-700 text-base font-extrabold">₹{currentVoucher.final_amount.toFixed(2)}</span>
            </div>
          </div>

          {/* Result or Error */}
          {postResult && (
            <div className="p-3.5 bg-emerald-100 border border-emerald-300 rounded-xl text-emerald-900 text-xs font-semibold">
              ✅ {postResult.message}
            </div>
          )}
          {error && (
            <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs space-y-3">
              <div className="flex items-center gap-2">
                <span className="font-semibold">⚠️ {error}</span>
              </div>
              {missingLedgerName && (
                <div className="pt-2 border-t border-rose-200/80 space-y-2.5">
                  {errorSuggestedParty && (
                    <div className="bg-linear-to-r from-amber-100 to-orange-100 border border-amber-300 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 shadow-xs">
                      <div>
                        <div className="flex items-center gap-1.5 font-bold text-amber-950 text-xs">
                          <span>💡 Found matching Master in Tally:</span>
                          <span className="text-[10px] px-2 py-0.2 rounded-full bg-amber-200 text-amber-900 font-semibold">
                            {Math.round(errorSuggestedParty.score * 100)}% Match
                          </span>
                        </div>
                        <div className="text-xs text-slate-800 mt-1">
                          Switch to <strong className="text-emerald-800 font-bold text-sm">"{errorSuggestedParty.name}"</strong>
                          {errorSuggestedParty.parent && (
                            <span className="text-slate-500 text-[11px] ml-1.5 font-medium">({errorSuggestedParty.parent})</span>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={isPosting}
                        onClick={() => handleSwitchAndPost(errorSuggestedParty.name)}
                        className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 active:bg-emerald-900 text-white rounded-xl text-xs font-bold shrink-0 shadow-md shadow-emerald-700/20 flex items-center justify-center gap-1.5 cursor-pointer transition"
                      >
                        {isPosting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ArrowRight className="w-3.5 h-3.5" />}
                        <span>Switch & Post to Tally</span>
                      </button>
                    </div>
                  )}

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 text-slate-600">
                    <span>
                      Or create new ledger <strong>'{missingLedgerName}'</strong> in Tally:
                    </span>
                    <button
                      type="button"
                      disabled={isCreatingLedger}
                      onClick={() => handleCreateMissingLedger(missingLedgerName)}
                      className="px-3.5 py-1.5 bg-white border border-slate-300 text-slate-700 hover:border-emerald-500 hover:text-emerald-700 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 shadow-xs disabled:opacity-50 cursor-pointer"
                    >
                      {isCreatingLedger ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Creating in Tally...
                        </>
                      ) : (
                        <>
                          <UserPlus className="w-3.5 h-3.5" />
                          Create Ledger in Tally & Post
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-end gap-2.5 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-200 cursor-pointer"
          >
            Close
          </button>

          {!postResult && (
            <button
              type="button"
              disabled={isPosting}
              onClick={handleApproveAndPost}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 shadow-md shadow-emerald-600/20 disabled:opacity-50 cursor-pointer"
            >
              {isPosting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Posting to TallyPrime...
                </>
              ) : (
                <>
                  Approve and Create in Tally
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
