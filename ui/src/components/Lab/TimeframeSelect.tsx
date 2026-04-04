export const ALL_TIMEFRAMES = ["M1", "M5", "M10", "M15", "M30", "H1", "H4", "D1", "W1"] as const;

interface Props {
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function TimeframeSelect({ selected, onChange }: Props) {
  const selectedSet = new Set(selected);

  function toggle(tf: string) {
    if (selectedSet.has(tf)) {
      onChange(selected.filter((s) => s !== tf));
    } else {
      onChange([...selected, tf]);
    }
  }

  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
        Timeframes
      </label>
      <div className="flex flex-wrap gap-1.5">
        {ALL_TIMEFRAMES.map((tf) => {
          const active = selectedSet.has(tf);
          return (
            <button
              key={tf}
              type="button"
              onClick={() => toggle(tf)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors border ${
                active
                  ? "bg-blue-500 border-blue-500 text-white"
                  : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {tf}
            </button>
          );
        })}
      </div>
    </div>
  );
}
