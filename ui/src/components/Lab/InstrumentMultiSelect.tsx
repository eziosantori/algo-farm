import { useState, useRef, useEffect, useMemo } from "react";

// ---------------------------------------------------------------------------
// Static instrument data
// ---------------------------------------------------------------------------

export const INSTRUMENT_GROUPS = [
  { label: "Forex", items: ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDNZD", "EURAUD"] },
  { label: "Metals", items: ["XAUUSD", "XAGUSD"] },
  { label: "Commodities", items: ["BCOUSD", "WTIUSD", "NATGASUSD", "XCUUSD"] },
  { label: "Indices", items: ["US500", "NAS100", "GER40", "UK100", "JPN225", "AUS200"] },
  { label: "Stocks", items: ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "NFLX", "AMD", "INTC"] },
] as const;

interface Props {
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function InstrumentMultiSelect({ selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("keydown", handleKey);
      return () => document.removeEventListener("keydown", handleKey);
    }
  }, [open]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const lowerSearch = search.toLowerCase();

  const filteredGroups = useMemo(() => {
    if (!lowerSearch) return INSTRUMENT_GROUPS;
    return INSTRUMENT_GROUPS
      .map((g) => ({
        ...g,
        items: g.items.filter((i) => i.toLowerCase().includes(lowerSearch)),
      }))
      .filter((g) => g.items.length > 0);
  }, [lowerSearch]);

  function toggle(instrument: string) {
    if (selectedSet.has(instrument)) {
      onChange(selected.filter((s) => s !== instrument));
    } else {
      onChange([...selected, instrument]);
    }
  }

  function toggleGroup(items: readonly string[]) {
    const allSelected = items.every((i) => selectedSet.has(i));
    if (allSelected) {
      onChange(selected.filter((s) => !items.includes(s)));
    } else {
      const toAdd = items.filter((i) => !selectedSet.has(i));
      onChange([...selected, ...toAdd]);
    }
  }

  function remove(instrument: string) {
    onChange(selected.filter((s) => s !== instrument));
  }

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
        Instruments
      </label>

      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1.5">
          {selected.map((inst) => (
            <span
              key={inst}
              className="inline-flex items-center gap-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:text-blue-300"
            >
              {inst}
              <button
                type="button"
                onClick={() => remove(inst)}
                className="ml-0.5 text-blue-400 hover:text-blue-600 dark:hover:text-blue-200"
              >
                &times;
              </button>
            </span>
          ))}
          {selected.length > 3 && (
            <button
              type="button"
              onClick={() => onChange([])}
              className="text-[10px] text-gray-400 hover:text-red-500 underline"
            >
              clear all
            </button>
          )}
        </div>
      )}

      {/* Search input */}
      <input
        ref={inputRef}
        type="text"
        placeholder={selected.length ? `${selected.length} selected — type to filter…` : "Search instruments…"}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        onFocus={() => setOpen(true)}
        className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-xs text-gray-700 dark:text-gray-300 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-72 overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg">
          {filteredGroups.length === 0 && (
            <div className="px-3 py-2 text-xs text-gray-400">No matches</div>
          )}
          {filteredGroups.map((group) => {
            const allSelected = group.items.every((i) => selectedSet.has(i));
            const someSelected = group.items.some((i) => selectedSet.has(i));
            return (
              <div key={group.label}>
                {/* Group header */}
                <button
                  type="button"
                  onClick={() => toggleGroup(group.items)}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-100 dark:border-gray-800"
                >
                  <span
                    className={`w-3 h-3 rounded-sm border flex items-center justify-center text-[8px] ${
                      allSelected
                        ? "bg-blue-500 border-blue-500 text-white"
                        : someSelected
                          ? "bg-blue-200 dark:bg-blue-800 border-blue-400"
                          : "border-gray-300 dark:border-gray-600"
                    }`}
                  >
                    {allSelected ? "\u2713" : someSelected ? "\u2013" : ""}
                  </span>
                  {group.label}
                  <span className="text-gray-400 font-normal">({group.items.length})</span>
                </button>

                {/* Items */}
                {group.items.map((instrument) => {
                  const isSelected = selectedSet.has(instrument);
                  return (
                    <button
                      key={instrument}
                      type="button"
                      onClick={() => toggle(instrument)}
                      className={`w-full flex items-center gap-2 px-3 py-1 text-xs hover:bg-gray-50 dark:hover:bg-gray-800 ${
                        isSelected ? "text-blue-600 dark:text-blue-400" : "text-gray-700 dark:text-gray-300"
                      }`}
                    >
                      <span
                        className={`w-3 h-3 rounded-sm border flex items-center justify-center text-[8px] ${
                          isSelected
                            ? "bg-blue-500 border-blue-500 text-white"
                            : "border-gray-300 dark:border-gray-600"
                        }`}
                      >
                        {isSelected ? "\u2713" : ""}
                      </span>
                      {instrument}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
