import React, { useState } from 'react';
import { Bill } from '../../types';
import { Sparkles, MessageSquare, CheckCircle, FileText, Loader2, Trash2, X, Eye } from 'lucide-react';

interface BillListProps {
  bills: Bill[];
  onScan: (id: number) => void;
  onOpenClarification: (bill: Bill) => void;
  onOpenVoucher: (bill: Bill) => void;
  onDelete?: (id: number) => void;
  onCleanFailed?: () => void;
  scanningId: number | null;
}

export const BillList: React.FC<BillListProps> = ({
  bills,
  onScan,
  onOpenClarification,
  onOpenVoucher,
  onDelete,
  onCleanFailed,
  scanningId,
}) => {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isCleaningFailed, setIsCleaningFailed] = useState(false);
  const [viewingImage, setViewingImage] = useState<{ url: string; title: string } | null>(null);

  const getPhotoUrl = (filePath?: string) => {
    if (!filePath) return '';
    const clean = filePath.replace(/\\/g, '/');
    const idx = clean.indexOf('uploads/');
    const rel = idx >= 0 ? clean.substring(idx) : clean;
    return `http://localhost:8000/${rel}`;
  };

  const handleDeleteClick = async (billId: number) => {
    if (!window.confirm(`Are you sure you want to delete this bill?`)) return;
    if (onDelete) {
      setDeletingId(billId);
      try {
        await onDelete(billId);
      } finally {
        setDeletingId(null);
      }
    }
  };

  const handleCleanFailedClick = async () => {
    if (!window.confirm('Delete all failed bills?')) return;
    if (onCleanFailed) {
      setIsCleaningFailed(true);
      try {
        await onCleanFailed();
      } finally {
        setIsCleaningFailed(false);
      }
    }
  };

  const failedCount = bills.filter((b) => b.status === 'FAILED').length;
  const getStatusBadge = (status: Bill['status'], isGst: boolean) => {
    if (isGst) {
      return (
        <span className="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-rose-50 text-rose-700 border border-rose-200">
          GST Detected (Blocked)
        </span>
      );
    }
    switch (status) {
      case 'UPLOADED':
        return (
          <span className="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            Uploaded
          </span>
        );
      case 'PROCESSING':
        return (
          <span className="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" /> Scanning AI
          </span>
        );
      case 'CLARIFICATION_REQUIRED':
        return (
          <span className="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-amber-50 text-amber-700 border border-amber-200">
            Pending Clarification
          </span>
        );
      case 'READY_FOR_APPROVAL':
        return (
          <span className="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-teal-50 text-teal-700 border border-teal-200">
            Ready for Approval
          </span>
        );
      case 'POSTED':
        return (
          <span className="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
            Posted in Tally
          </span>
        );
      case 'FAILED':
        return (
          <span className="px-2.5 py-1 text-[11px] font-semibold rounded-full bg-rose-50 text-rose-700 border border-rose-200">
            Failed
          </span>
        );
      default:
        return null;
    }
  };

  if (bills.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center max-w-4xl mx-auto my-6">
        <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
          <FileText className="w-6 h-6" />
        </div>
        <h3 className="text-base font-bold text-slate-800">No Bills Found</h3>
        <p className="text-xs text-slate-500 mt-1">
          Upload handwritten or printed invoices to begin automatic scanning and TallyPrime voucher creation.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-xs max-w-7xl mx-auto my-6 overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-bold text-slate-900">Processed Invoices & Bills</h3>
          <span className="text-xs text-slate-500">({bills.length} Total)</span>
        </div>
        {failedCount > 0 && onCleanFailed && (
          <button
            onClick={handleCleanFailedClick}
            disabled={isCleaningFailed}
            title="Remove all failed bills"
            className="px-2.5 py-1 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg flex items-center gap-1.5 transition disabled:opacity-50"
          >
            {isCleaningFailed ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Trash2 className="w-3.5 h-3.5 text-rose-600" />
            )}
            Clean Failed Bills ({failedCount})
          </button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
            <tr>
              <th className="py-3 px-4">Invoice / File</th>
              <th className="py-3 px-4">Type</th>
              <th className="py-3 px-4">Party / Customer</th>
              <th className="py-3 px-4">Date</th>
              <th className="py-3 px-4 text-right">Amount (₹)</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {bills.map((bill) => (
              <tr key={bill.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2.5">
                    <div
                      onClick={() =>
                        setViewingImage({
                          url: getPhotoUrl(bill.file_path),
                          title: bill.invoice_number || bill.original_filename,
                        })
                      }
                      className="w-10 h-10 rounded-lg bg-slate-100 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-emerald-500 hover:scale-105 transition shadow-2xs group relative"
                      title="Click to view original bill photo"
                    >
                      {bill.file_type.toLowerCase() === 'pdf' ? (
                        <FileText className="w-5 h-5 text-slate-500" />
                      ) : (
                        <>
                          <img
                            src={getPhotoUrl(bill.file_path)}
                            alt="Bill"
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white">
                            <Eye className="w-4 h-4" />
                          </div>
                        </>
                      )}
                    </div>
                    <div>
                      <span
                        onClick={() =>
                          setViewingImage({
                            url: getPhotoUrl(bill.file_path),
                            title: bill.invoice_number || bill.original_filename,
                          })
                        }
                        className="font-semibold text-slate-900 block truncate max-w-[150px] cursor-pointer hover:text-emerald-700 hover:underline"
                        title="Click to view original bill photo"
                      >
                        {bill.invoice_number || bill.original_filename}
                      </span>
                      <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                        {bill.file_type}
                      </span>
                    </div>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <span
                    className={`px-2 py-0.5 rounded-md text-[10px] font-semibold ${
                      bill.bill_type === 'SALES'
                        ? 'bg-emerald-50 text-emerald-700'
                        : bill.bill_type === 'PURCHASE'
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {bill.bill_type}
                  </span>
                </td>
                <td className="py-3 px-4 font-medium text-slate-800">
                  {bill.party_name || <span className="text-slate-400 italic">Not detected</span>}
                </td>
                <td className="py-3 px-4 text-slate-700 font-semibold">
                  {bill.invoice_date || <span className="text-slate-400 italic font-normal">-</span>}
                </td>
                <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                  {bill.final_amount > 0 ? `₹${bill.final_amount.toFixed(2)}` : '-'}
                </td>
                <td className="py-3 px-4">
                  {getStatusBadge(bill.status, bill.is_gst_detected)}
                </td>
                <td className="py-3 px-4 text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    {bill.status === 'UPLOADED' && (
                      <button
                        onClick={() => onScan(bill.id)}
                        disabled={scanningId === bill.id}
                        className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-medium hover:bg-emerald-700 text-xs flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {scanningId === bill.id ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Scanning...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3.5 h-3.5" /> Scan AI
                          </>
                        )}
                      </button>
                    )}

                    {bill.status === 'CLARIFICATION_REQUIRED' && (
                      <button
                        onClick={() => onOpenClarification(bill)}
                        className="px-3 py-1.5 rounded-lg bg-amber-600 text-white font-medium hover:bg-amber-700 text-xs flex items-center gap-1.5"
                      >
                        <MessageSquare className="w-3.5 h-3.5" /> Clarify
                      </button>
                    )}

                    {(bill.status === 'READY_FOR_APPROVAL' || bill.status === 'POSTED') && (
                      <button
                        onClick={() => onOpenVoucher(bill)}
                        className="px-3 py-1.5 rounded-lg bg-slate-900 text-white font-medium hover:bg-slate-800 text-xs flex items-center gap-1.5"
                      >
                        <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                        {bill.status === 'POSTED' ? 'View Voucher' : 'Preview & Post'}
                      </button>
                    )}

                    {onDelete && (
                      <button
                        type="button"
                        onClick={() => handleDeleteClick(bill.id)}
                        disabled={deletingId === bill.id}
                        title="Delete this bill"
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition border border-transparent hover:border-rose-200 disabled:opacity-40"
                      >
                        {deletingId === bill.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-600" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Bill Photo Lightbox Modal */}
      {viewingImage && (
        <div
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setViewingImage(null)}
        >
          <div
            className="bg-white rounded-2xl max-w-4xl max-h-[92vh] overflow-hidden flex flex-col shadow-2xl relative w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-3.5 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-sm">📷</span>
                <span className="text-xs font-bold truncate max-w-md">{viewingImage.title}</span>
              </div>
              <button
                type="button"
                onClick={() => setViewingImage(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 cursor-pointer transition"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-3 overflow-auto max-h-[82vh] flex items-center justify-center bg-slate-950">
              <img
                src={viewingImage.url}
                alt={viewingImage.title}
                className="max-w-full max-h-[78vh] object-contain rounded-lg shadow-lg"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
