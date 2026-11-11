import React, { useState, useRef } from 'react';
import { Upload, Camera, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
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

  const handleFileChange = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const fileArray = Array.from(files);
    setSelectedFiles(fileArray);
    setError(null);

    // Generate previews
    const newPreviews = fileArray.map((file) => URL.createObjectURL(file));
    setPreviews(newPreviews);
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
          uploaded.map(async (b, idx) => {
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
        onChange={(e) => handleFileChange(e.target.files)}
        multiple
        accept=".jpg,.jpeg,.png,.pdf"
        className="hidden"
      />
      <input
        type="file"
        ref={cameraInputRef}
        onChange={(e) => handleFileChange(e.target.files)}
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
            handleFileChange(e.dataTransfer.files);
          }}
          className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-emerald-500 transition-colors bg-slate-50/50 flex flex-col items-center justify-center cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mb-3">
            <Upload className="w-6 h-6" />
          </div>
          <span className="text-sm font-semibold text-slate-800 mb-1">
            Drag & Drop bill here, or browse files
          </span>
          <span className="text-xs text-slate-500 mb-4">
            Supports computer-generated and handwritten sales/purchase invoices
          </span>

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
          {/* File previews */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
            {previews.map((src, idx) => (
              <div key={idx} className="relative rounded-xl overflow-hidden border border-slate-200 bg-slate-100 aspect-3/4">
                <img src={src} alt="Preview" className="w-full h-full object-cover" />
                <div className="absolute bottom-0 inset-x-0 bg-black/60 backdrop-blur-xs p-1.5 text-white text-[10px] truncate">
                  {selectedFiles[idx]?.name}
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={() => {
                setSelectedFiles([]);
                setPreviews([]);
              }}
              className="text-xs text-slate-500 hover:text-slate-800"
            >
              Clear Selection
            </button>

            <button
              type="button"
              disabled={isUploading}
              onClick={handleUploadAndScan}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 text-white font-semibold text-xs hover:bg-emerald-700 shadow-md shadow-emerald-600/20 disabled:opacity-50"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{scanStatusText || 'Scanning with Multilingual Vision AI...'}</span>
                </>
              ) : (
                <>
                  Upload & Scan with AI
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
