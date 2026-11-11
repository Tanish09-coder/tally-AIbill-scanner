import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Search, ChevronDown, Check, Plus, X } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
  group?: string;
  subLabel?: string;
}

interface SearchableSelectProps {
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  allowCustom?: boolean;
  disabled?: boolean;
  className?: string;
  compact?: boolean;
}

export const SearchableSelect: React.FC<SearchableSelectProps> = ({
  options,
  value,
  onChange,
  placeholder = 'Search & select...',
  label,
  allowCustom = true,
  disabled = false,
  className = '',
  compact = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Focus search input when opening
  useEffect(() => {
    if (isOpen) {
      setSearch('');
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const filteredOptions = useMemo(() => {
    if (!search.trim()) return options;
    const query = search.toLowerCase();
    return options.filter(
      (opt) =>
        opt.label.toLowerCase().includes(query) ||
        (opt.group && opt.group.toLowerCase().includes(query)) ||
        (opt.subLabel && opt.subLabel.toLowerCase().includes(query))
    );
  }, [options, search]);

  const exactMatchExists = useMemo(() => {
    const q = search.trim().toLowerCase();
    return options.some((opt) => opt.value.toLowerCase() === q || opt.label.toLowerCase() === q);
  }, [options, search]);

  const selectedOption = useMemo(() => {
    return options.find((opt) => opt.value.toLowerCase() === value.toLowerCase()) || {
      value,
      label: value,
      group: 'Custom',
    };
  }, [options, value]);

  const handleSelect = (val: string) => {
    onChange(val);
    setIsOpen(false);
  };

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      {label && (
        <label className="block text-xs font-semibold text-slate-600 mb-1">
          {label}
        </label>
      )}

      {/* Trigger Button / Display */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`w-full text-left bg-white border rounded-xl flex items-center justify-between transition shadow-2xs hover:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 ${
          isOpen ? 'border-emerald-500 ring-2 ring-emerald-500/20' : 'border-slate-300'
        } ${compact ? 'px-2.5 py-1 text-xs' : 'px-3 py-2 text-sm'} ${
          disabled ? 'opacity-60 cursor-not-allowed bg-slate-100' : 'cursor-pointer'
        }`}
      >
        <div className="flex items-center gap-2 overflow-hidden truncate">
          <span className="font-semibold text-slate-900 truncate">
            {selectedOption.label || placeholder}
          </span>
          {selectedOption.group && selectedOption.group !== 'Custom' && (
            <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200">
              {selectedOption.group}
            </span>
          )}
        </div>
        <ChevronDown className={`shrink-0 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''} ${compact ? 'w-3.5 h-3.5' : 'w-4 h-4'}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute z-50 left-0 right-0 mt-1.5 bg-white border border-slate-200 rounded-xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-100 min-w-[260px] max-w-lg">
          {/* Search Input Box */}
          <div className="p-2 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or group..."
              className="w-full bg-transparent text-xs sm:text-sm text-slate-800 placeholder-slate-400 outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  setIsOpen(false);
                } else if (e.key === 'Enter') {
                  e.preventDefault();
                  if (filteredOptions.length > 0) {
                    handleSelect(filteredOptions[0].value);
                  } else if (allowCustom && search.trim()) {
                    handleSelect(search.trim());
                  }
                }
              }}
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="text-slate-400 hover:text-slate-600 p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Options List */}
          <div className="max-h-56 overflow-y-auto divide-y divide-slate-50 p-1">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((opt) => {
                const isSelected = opt.value.toLowerCase() === value.toLowerCase();
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => handleSelect(opt.value)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs sm:text-sm flex items-center justify-between group transition ${
                      isSelected
                        ? 'bg-emerald-50 text-emerald-900 font-semibold'
                        : 'text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex flex-col gap-0.5 truncate pr-2">
                      <span className="truncate">{opt.label}</span>
                      {opt.subLabel && (
                        <span className="text-[10px] text-slate-400">{opt.subLabel}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {opt.group && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 group-hover:bg-white text-slate-500 border border-slate-200">
                          {opt.group}
                        </span>
                      )}
                      {isSelected && <Check className="w-4 h-4 text-emerald-600" />}
                    </div>
                  </button>
                );
              })
            ) : (
              <div className="p-3 text-center text-xs text-slate-500">
                No matching accounts or items found.
              </div>
            )}

            {/* Custom Option if allowed and not matching exactly */}
            {allowCustom && search.trim() && !exactMatchExists && (
              <button
                type="button"
                onClick={() => handleSelect(search.trim())}
                className="w-full text-left px-3 py-2 text-xs text-emerald-700 hover:bg-emerald-50 font-medium flex items-center gap-2 rounded-lg mt-1 border-t border-slate-100"
              >
                <Plus className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span className="truncate">Use custom: "<strong>{search.trim()}</strong>"</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

