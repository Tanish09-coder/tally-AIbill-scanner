import React from 'react';
import { DashboardStats } from '../../types';
import { FileText, ShoppingBag, MessageSquareText, CheckCircle2, Send } from 'lucide-react';

interface StatCardsProps {
  stats: DashboardStats | null;
  onSelectFilter: (filter: string) => void;
}

export const StatCards: React.FC<StatCardsProps> = ({ stats, onSelectFilter }) => {
  const cards = [
    {
      title: 'Total Invoices',
      value: stats?.total_bills ?? 0,
      icon: FileText,
      color: 'text-blue-600 bg-blue-50 border-blue-200',
      filter: '',
    },
    {
      title: 'Sales Bills',
      value: stats?.sales_bills ?? 0,
      icon: ShoppingBag,
      color: 'text-emerald-600 bg-emerald-50 border-emerald-200',
      filter: 'SALES',
    },
    {
      title: 'Purchase Bills',
      value: stats?.purchase_bills ?? 0,
      icon: ShoppingBag,
      color: 'text-indigo-600 bg-indigo-50 border-indigo-200',
      filter: 'PURCHASE',
    },
    {
      title: 'Pending Clarification',
      value: stats?.pending_clarifications ?? 0,
      icon: MessageSquareText,
      color: 'text-amber-600 bg-amber-50 border-amber-200',
      filter: 'CLARIFICATION_REQUIRED',
    },
    {
      title: 'Ready for Approval',
      value: stats?.ready_for_approval ?? 0,
      icon: CheckCircle2,
      color: 'text-teal-600 bg-teal-50 border-teal-200',
      filter: 'READY_FOR_APPROVAL',
    },
    {
      title: 'Posted to Tally',
      value: stats?.posted_to_tally ?? 0,
      icon: Send,
      color: 'text-emerald-700 bg-emerald-100 border-emerald-300 font-bold',
      filter: 'POSTED',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5 my-6">
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <div
            key={c.title}
            onClick={() => onSelectFilter(c.filter)}
            className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs hover:shadow-md transition-all cursor-pointer flex flex-col justify-between"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-slate-500 truncate">{c.title}</span>
              <div className={`p-1.5 rounded-lg border ${c.color}`}>
                <Icon className="w-4 h-4" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-800">{c.value}</div>
          </div>
        );
      })}
    </div>
  );
};
