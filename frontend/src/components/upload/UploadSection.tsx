import React, { useState, useRef } from 'react';
import { Upload, Camera, ArrowRight, Loader2, AlertCircle, Plus, X } from 'lucide-react';
import { api } from '../../services/api';
import { Bill } from '../../types';

interface UploadSectionProps {
  onUploadSuccess: (bills: Bill[]) => void;
}

export const UploadSection: React.FC<UploadSectionProps> = ({ onUploadSuccess }) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [billTypeHint, setBillTypeHint] = useState<string>('SALES');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [scanStatusText, setScanStatusText] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (files: FileList | null, append: boolean = false) => {
    if (!files || files.length === 0) return;
    const fileArray = Array.from(files);

    if (append && selectedFiles.length > 0) {
      const existingSignatures = new Set(selectedFiles.map((f) => `${f.name}_${f.size}`));
      const newFiles = fileArray.filter((f) => !existingSignatures.has(`${f.name}_${f.size}`));
      const combined = [...selectedFiles, ...newFiles];
      setSelectedFiles(combined);
      setPreviews(combined.map((f) => URL.createObjectURL(f)));
    } else {
      setSelectedFiles(fileArray);
      setPreviews(fileArray.map((f) => URL.createObjectURL(f)));
    }
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleRemoveFile = (indexToRemove: number) => {
    const updatedFiles = selectedFiles.filter((_, idx) => idx !== indexToRemove);
    setSelectedFiles(updatedFiles);
    setPreviews(updatedFiles.map((f) => URL.createObjectURL(f)));
  };

  const handleUploadAndScan = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select or capture at least one bill.');
      return;
    }

    setIsUploading(true);
    setError(null);
    try {
      const count = selectedFiles.length;
      setScanStatusText(`Uploading ${count} bill${count > 1 ? 's' : ''}...`);
      const uploaded = await api.uploadBills(selectedFiles, billTypeHint);

      if (uploaded.length > 0) {
        setScanStatusText(`AI scanning ${uploaded.length} bill${uploaded.length > 1 ? 's' : ''} in parallel...`);
        // Scan all uploaded bills concurrently using rotating API keys
        await Promise.allSettled(
          uploaded.map(async (b) => {
            try {
              return await api.scanBill(b.id);
            } catch (scanErr) {
              console.warn(`Scan warning for bill #${b.id}:`, scanErr);
              return null;
            }
          })
        );
      }

      setSelectedFiles([]);
      setPreviews([]);
      setScanStatusText('');
      onUploadSuccess(uploaded);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to upload and scan bills.');
    } finally {
      setIsUploading(false);
      setScanStatusText('');
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 max-w-3xl mx-auto my-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Upload or Capture Bill</h2>
          <p className="text-xs text-slate-500">
            Supports Hindi, Marathi, and English handwriting (JPG, PNG, PDF)
          </p>
        </div>

        {/* Bill Type Selector */}
        <div className="flex bg-slate-100 p-1 rounded-xl text-xs font-semibold">
          <button
            type="button"
            onClick={() => setBillTypeHint('SALES')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              billTypeHint === 'SALES' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-600'
            }`}
          >
            Sales Bill
          </button>
          <button
            type="button"
            onClick={() => setBillTypeHint('PURCHASE')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              billTypeHint === 'PURCHASE' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600'
            }`}
          >
            Purchase Bill
          </button>
        </div>
      </div>

      {/* Hidden File Inputs */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => handleFileChange(e.target.files, selectedFiles.length > 0)}
        multiple
        accept=".jpg,.jpeg,.png,.pdf"
        className="hidden"
      />
      <input
        type="file"
        ref={cameraInputRef}
        onChange={(e) => handleFileChange(e.target.files, selectedFiles.length > 0)}
        accept="image/*"
        capture="environment"
        className="hidden"
      />

      {/* Dropzone & Camera buttons */}
      {selectedFiles.length === 0 ? (
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFileChange(e.dataTransfer.files, false);
          }}
          className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-emerald-500 transition-colors bg-slate-50/50 flex flex-col items-center justify-center cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mb-3">
            <Upload className="w-6 h-6" />
          </div>
          <span className="text-sm font-semibold text-slate-800 mb-1">
            Drag & Drop bills here, or browse files
          </span>
          <span className="text-xs text-slate-500 mb-3">
            Supports computer-generated and handwritten sales/purchase invoices (JPG, PNG, PDF)
          </span>

          <div className="mb-4 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 font-medium flex items-center gap-1.5 shadow-2xs">
            <span>💡</span>
            <span><strong>Multi-select:</strong> In the file window, press <strong>Ctrl + A</strong> to select all bills, or hold <strong>Ctrl</strong> and click each photo!</span>
          </div>

          {/* Mobile Camera Option */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              cameraInputRef.current?.click();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-100 shadow-xs"
          >
            <Camera className="w-4 h-4 text-emerald-600" />
            Capture with Camera (Mobile)
          </button>
        </div>
      ) : (
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-800">
              {selectedFiles.length} bill{selectedFiles.length > 1 ? 's' : ''} selected
            </span>
            <span className="text-[11px] text-slate-500">
              Click "+ Add More" or use the button below to scan all
            </span>
          </div>

          {/* File previews with individual remove and Add More button */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            {previews.map((src, idx) => (
              <div key={idx} className="relative rounded-xl overflow-hidden border border-slate-200 bg-slate-100 aspect-3/4 group shadow-2xs">
                <img src={src} alt="Preview" className="w-full h-full object-cover" />
                <button
                  type="button"
                  onClick={() => handleRemoveFile(idx)}
                  className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/70 hover:bg-rose-600 text-white flex items-center justify-center transition shadow-sm cursor-pointer"
                  title="Remove this photo"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
                <div className="absolute bottom-0 inset-x-0 bg-black/60 backdrop-blur-xs p-1.5 text-white text-[10px] truncate">
                  {selectedFiles[idx]?.name}
                </div>
              </div>
            ))}

            {/* Add More Photos Card */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="rounded-xl border-2 border-dashed border-slate-300 hover:border-emerald-500 hover:bg-emerald-50/50 flex flex-col items-center justify-center p-3 text-center transition aspect-3/4 cursor-pointer text-slate-500 hover:text-emerald-700"
            >
              <div className="w-9 h-9 rounded-full bg-slate-100 group-hover:bg-emerald-100 flex items-center justify-center mb-1.5">
                <Plus className="w-5 h-5 text-emerald-600" />
              </div>
              <span className="text-xs font-bold">+ Add More</span>
              <span className="text-[10px] text-slate-400">Bills / Photos</span>
            </button>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={() => {
                setSelectedFiles([]);
                setPreviews([]);
              }}
              className="text-xs text-slate-500 hover:text-rose-600 cursor-pointer transition"
            >
              Clear All ({selectedFiles.length})
            </button>

            <button
              type="button"
              disabled={isUploading}
              onClick={handleUploadAndScan}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 text-white font-semibold text-xs hover:bg-emerald-700 shadow-md shadow-emerald-600/20 disabled:opacity-50 cursor-pointer"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{scanStatusText || 'Scanning with Multilingual Vision AI...'}</span>
                </>
              ) : (
                <>
                  Upload & Scan {selectedFiles.length > 1 ? `All ${selectedFiles.length} Bills` : 'with AI'}
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
