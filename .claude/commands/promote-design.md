Promote a strategy design report to permanent storage in `docs/ideas/strategies/`, then compact `docs/ideas/tmp/<strategy_name>/` (keeping substantive files, removing noise).

**Usage:** `/promote-design <strategy_name>`

**User input:** $ARGUMENTS

---

## Instructions

1. Extract `<strategy_name>` from `$ARGUMENTS` (snake_case name, e.g. `ichimoku_h4_tk_cross_btc_long`).

2. Verify the design report exists in the new location:
   ```bash
   ls engine/strategies/designs/<strategy_name>_design.md
   ```

   Backward compatibility: if missing, check legacy tmp location:
   ```bash
   ls docs/ideas/tmp/<strategy_name>/<strategy_name>_design.md
   ```

   If neither exists, print:
   `Error: <strategy_name>_design.md not found in engine/strategies/designs/ or docs/ideas/tmp/<strategy_name>/.`
   and stop.

3. Promote the design report:
   ```bash
   mkdir -p docs/ideas/strategies
   if [ -f engine/strategies/designs/<strategy_name>_design.md ]; then
     mv engine/strategies/designs/<strategy_name>_design.md docs/ideas/strategies/
   else
     mv docs/ideas/tmp/<strategy_name>/<strategy_name>_design.md docs/ideas/strategies/
   fi
   ```

4. Compact the tmp folder (if it exists) — remove known-noise files while preserving substantive analysis files:
   ```bash
   if [ -d docs/ideas/tmp/<strategy_name> ]; then
       (
          cd docs/ideas/tmp/<strategy_name> && \
          rm -f README_*.md *_INDEX.md *_COMPLETE.md \
                   *_summary.md *_executive_summary.md *_pm_summary.md \
                   *_testing_guide.md *_implementation_guide.md \
                   DELIVERY_SUMMARY.txt *_DELIVERABLES.md
       )
   fi
   ```

5. List what remains in tmp (if folder exists):
   ```bash
   if [ -d docs/ideas/tmp/<strategy_name> ]; then
     ls docs/ideas/tmp/<strategy_name>/
   fi
   ```

6. Print:
   ```
   Promoted: docs/ideas/strategies/<strategy_name>_design.md
   Source: engine/strategies/designs/<strategy_name>_design.md (or legacy docs/ideas/tmp fallback)
   Compacted: docs/ideas/tmp/<strategy_name>/ — substantive files preserved for future LLM continuation
   ```
