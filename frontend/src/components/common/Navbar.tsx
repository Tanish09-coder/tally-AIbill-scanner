import React from 'react';
import { TallyStatus } from '../../types';
import { RefreshCw, AlertCircle, ShieldCheck } from 'lucide-react';

interface NavbarProps {
  tallyStatus: TallyStatus | null;
  onRefreshTally: () => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onSyncMasters?: () => void;
  isSyncingMasters?: boolean;
  mastersCount?: { ledgers: number; stockItems: number };
}

export const Navbar: React.FC<NavbarProps> = ({
  tallyStatus,
  onRefreshTally,
  activeTab,
  setActiveTab,
  onSyncMasters,
  isSyncingMasters = false,
  mastersCount,
}) => {
  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <span className="text-lg font-bold text-slate-900 tracking-tight">
                Tally<span className="text-emerald-600">AI</span> Scanner
              </span>
              <span className="hidden sm:inline-block ml-2 px-2 py-0.5 text-[10px] font-semibold tracking-wider uppercase rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                Non-GST + Voice
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex space-x-1">
            {[
              { id: 'dashboard', label: 'Overview' },
              { id: 'upload', label: 'Upload Bill' },
              { id: 'bills', label: 'All Bills' },
              { id: 'clarifications', label: 'Clarifications' },
              { id: 'audit', label: 'Audit History' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-emerald-50 text-emerald-700 font-semibold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>

          {/* TallyPrime Status Pill & Sync Actions */}
          <div className="flex items-center gap-2 sm:gap-3">
            {onSyncMasters && (
              <button
                type="button"
                onClick={onSyncMasters}
                disabled={isSyncingMasters}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 font-semibold text-xs transition shadow-sm disabled:opacity-50 cursor-pointer"
                title="Fetch latest Ledgers, Accounts and Stock Items from TallyPrime"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isSyncingMasters ? 'animate-spin' : ''}`} />
                <span>{isSyncingMasters ? 'Syncing...' : 'Sync Masters'}</span>
                {mastersCount && mastersCount.ledgers > 0 && (
                  <span className="hidden lg:inline-block px-1.5 py-0.2 rounded-md bg-emerald-700/80 text-[10px] text-emerald-100 font-mono">
                    {mastersCount.ledgers}
                  </span>
                )}
              </button>
            )}

            <div
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${
                tallyStatus?.is_connected
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                  : 'bg-amber-50 text-amber-800 border-amber-300'
              }`}
            >
              {tallyStatus?.is_connected ? (
                <>
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  <span className="font-semibold">
                    Tally: {tallyStatus.company_name || 'Connected'}
                  </span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                  <span>Tally Disconnected (:9000)</span>
                </>
              )}
            </div>

            <button
              onClick={onRefreshTally}
              title="Ping TallyPrime"
              className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
