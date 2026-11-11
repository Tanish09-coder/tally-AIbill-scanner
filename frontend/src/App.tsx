import React, { useState, useEffect } from 'react';
import { Navbar } from './components/common/Navbar';
import { StatCards } from './components/dashboard/StatCards';
import { UploadSection } from './components/upload/UploadSection';
import { BillList } from './components/bills/BillList';
import { VoucherPreviewModal } from './components/voucher/VoucherPreviewModal';
import { api } from './services/api';
import { Bill, DashboardStats, TallyStatus, VoucherPreview, TallyMastersData } from './types';
import { CheckCircle, AlertTriangle, X } from 'lucide-react';

export const App: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [tallyStatus, setTallyStatus] = useState<TallyStatus | null>(null);
  const [bills, setBills] = useState<Bill[]>([]);
  const [filter, setFilter] = useState<string>('');
  const [activeTab, setActiveTab] = useState<string>('dashboard');

  // Modals & Active state
  const [activeVoucher, setActiveVoucher] = useState<VoucherPreview | null>(null);
  const [scanningId, setScanningId] = useState<number | null>(null);

  // Masters State
  const [masters, setMasters] = useState<TallyMastersData | null>(null);
  const [isSyncingMasters, setIsSyncingMasters] = useState(false);
  const [syncNotice, setSyncNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Load initial data
  useEffect(() => {
    loadData();
    const interval = setInterval(loadTallyStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    await Promise.all([loadStats(), loadTallyStatus(), loadBills(), loadMasters()]);
  };

  const loadMasters = async () => {
    try {
      const data = await api.getTallyMasters();
      setMasters(data);
    } catch (err) {
      console.warn('Could not load masters:', err);
    }
  };

  const handleSyncMasters = async () => {
    setIsSyncingMasters(true);
    setSyncNotice(null);
    try {
      const res = await api.syncTallyMasters();
      if (res.success) {
        setSyncNotice({
          type: 'success',
          message: res.message || `Successfully synced ${res.ledgers_synced} ledgers & ${res.stock_items_synced} stock items from Tally!`,
        });
        await Promise.all([loadMasters(), loadTallyStatus()]);
      } else {
        setSyncNotice({
          type: 'error',
          message: res.message || 'Tally sync could not be completed.',
        });
      }
    } catch (err: any) {
      setSyncNotice({
        type: 'error',
        message: err?.response?.data?.detail || 'Cannot connect to TallyPrime. Ensure company is open on port 9000.',
      });
    } finally {
      setIsSyncingMasters(false);
      setTimeout(() => setSyncNotice(null), 6000);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getStats();
      setStats(data);
    } catch (err) {
      console.warn('Could not load stats:', err);
    }
  };

  const loadTallyStatus = async () => {
    try {
      const data = await api.getTallyStatus();
      setTallyStatus(data);
    } catch (err) {
      setTallyStatus({
        is_connected: false,
        status: 'DISCONNECTED',
        endpoint: 'http://localhost:9000',
        company_name: null,
        message: 'Cannot reach Tally HTTP server',
      });
    }
  };

  const loadBills = async () => {
    try {
      const res = await api.getBills();
      setBills(res.bills);
    } catch (err) {
      console.warn('Could not load bills:', err);
    }
  };

  const handleScan = async (id: number) => {
    setScanningId(id);
    try {
      const updated = await api.scanBill(id);
      setBills((prev) => prev.map((b) => (b.id === id ? updated : b)));
      loadStats();

      // If clarifications needed, open clarification modal
      if (updated.status === 'READY_FOR_APPROVAL' || updated.status === 'CLARIFICATION_REQUIRED') {
        handleOpenVoucher(updated);
      }
    } catch (err) {
      console.error('Scan failed:', err);
    } finally {
      setScanningId(null);
    }
  };

  const handleOpenClarification = async (bill: Bill) => {
    // Redirect clarify to voucher preview and post
    handleOpenVoucher(bill);
  };

  const handleOpenVoucher = async (bill: Bill) => {
    try {
      const preview = await api.getVoucherPreview(bill.id);
      setActiveVoucher(preview);
    } catch (err) {
      console.error('Failed to load voucher preview:', err);
    }
  };

  const handleDeleteBill = async (id: number) => {
    try {
      await api.deleteBill(id);
      setBills((prev) => prev.filter((b) => b.id !== id));
      loadStats();
    } catch (err) {
      console.error('Failed to delete bill:', err);
    }
  };

  const handleCleanFailedBills = async () => {
    try {
      await api.deleteFailedBills();
      setBills((prev) => prev.filter((b) => b.status !== 'FAILED'));
      loadStats();
    } catch (err) {
      console.error('Failed to clean failed bills:', err);
    }
  };



  return (
    <div className="min-h-screen bg-slate-50 pb-12 text-slate-800">
      {/* Top Navigation */}
      <Navbar
        tallyStatus={tallyStatus}
        onRefreshTally={loadTallyStatus}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onSyncMasters={handleSyncMasters}
        isSyncingMasters={isSyncingMasters}
        mastersCount={{
          ledgers: masters?.total_ledgers ?? 0,
          stockItems: masters?.total_stock_items ?? 0,
        }}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        {/* Sync Toast Notification */}
        {syncNotice && (
          <div
            className={`mb-4 p-3.5 rounded-xl text-xs sm:text-sm font-medium flex items-center justify-between shadow-xs border transition ${
              syncNotice.type === 'success'
                ? 'bg-emerald-50 text-emerald-900 border-emerald-300'
                : 'bg-amber-50 text-amber-900 border-amber-300'
            }`}
          >
            <div className="flex items-center gap-2">
              {syncNotice.type === 'success' ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              )}
              <span>{syncNotice.message}</span>
            </div>
            <button
              onClick={() => setSyncNotice(null)}
              className="text-slate-400 hover:text-slate-700 p-1 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Dashboard Metrics */}
        <StatCards
          stats={stats}
          onSelectFilter={(f) => {
            setFilter(f);
            setActiveTab('bills');
          }}
        />

        {/* Upload Dropzone & Camera Section */}
        <UploadSection
          onUploadSuccess={(newBills) => {
            loadBills();
            loadStats();
            if (newBills.length > 0) {
              handleScan(newBills[0].id);
            }
          }}
        />

        {/* Bills Listing */}
        <BillList
          bills={filter ? bills.filter((b) => b.status === filter || b.bill_type === filter) : bills}
          onScan={handleScan}
          onOpenClarification={handleOpenClarification}
          onOpenVoucher={handleOpenVoucher}
          onDelete={handleDeleteBill}
          onCleanFailed={handleCleanFailedBills}
          scanningId={scanningId}
        />
      </main>

      {/* Voucher Preview & Approval Modal */}
      {activeVoucher && (
        <VoucherPreviewModal
          voucher={activeVoucher}
          onClose={() => setActiveVoucher(null)}
          onSuccessPost={() => {
            loadBills();
            loadStats();
          }}
        />
      )}

    </div>
  );
};

