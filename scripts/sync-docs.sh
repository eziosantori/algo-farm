#!/usr/bin/env bash
# sync-docs.sh — Sync gitignored MD files from algo-farm to cBot/docs + exports
# Usage: ./scripts/sync-docs.sh [--dry-run]
set -euo pipefail

# --- Configuration ---
ALGO_FARM_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CBOT_ROOT="${HOME}/git/personal/cBot"
CBOT_DOCS="${CBOT_ROOT}/docs/algo-farm"
CBOT_EXPORTS="${CBOT_ROOT}/02_Test_Optimization/AlgoFarm"
TRANSFORM_SCRIPT="${ALGO_FARM_ROOT}/scripts/transform_design.py"

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "[DRY RUN] No files will be modified."
fi

# --- Validate paths ---
if [[ ! -d "$ALGO_FARM_ROOT/docs/ideas" ]]; then
    echo "ERROR: $ALGO_FARM_ROOT/docs/ideas not found" >&2
    exit 1
fi

if [[ ! -d "$CBOT_DOCS" ]]; then
    echo "ERROR: $CBOT_DOCS not found. Is the cBot repo cloned?" >&2
    exit 1
fi

# --- Helper: extract status from design MD Run Log ---
extract_status() {
    local file="$1"
    # Find last data row in Run Log table, extract Outcome column
    local last_row
    last_row=$(awk '/^## Run Log/,0 { if (/^\| *[0-9]/) last=$0 } END { print last }' "$file")
    if [[ -z "$last_row" ]]; then
        echo "draft"
        return
    fi
    # Column 7 (Outcome) — split by | and strip backticks
    echo "$last_row" | awk -F'|' '{ gsub(/[` ]/, "", $8); print $8 }'
}

# --- Helper: classify strategy type by name keywords ---
classify_strategy() {
    local name="$1"
    local lower
    lower=$(echo "$name" | tr '[:upper:]' '[:lower:]')
    if [[ "$lower" == *supertrend* ]] || [[ "$lower" == *trend* ]] || [[ "$lower" == *ema* ]] || [[ "$lower" == *pullback* ]]; then
        echo "Trend"
    elif [[ "$lower" == *bollinger* ]] || [[ "$lower" == *"mean reversion"* ]] || [[ "$lower" == *washout* ]] || [[ "$lower" == *overnight* ]]; then
        echo "MeanReversion"
    elif [[ "$lower" == *scalp* ]] || [[ "$lower" == *daytrade* ]] || [[ "$lower" == *fakeout* ]] || [[ "$lower" == *breakout* ]]; then
        echo "DayTrade"
    elif [[ "$lower" == *ichimoku* ]]; then
        echo "Trend"
    else
        echo "Other"
    fi
}

# ============================================================
# 1. SYNC IDEAS
# ============================================================
echo "=== Syncing ideas ==="
rsync -av --delete --delete-excluded $DRY_RUN \
    --exclude='README.md' --include='*.md' --exclude='*' \
    "$ALGO_FARM_ROOT/docs/ideas/" \
    "$CBOT_DOCS/ideas/" \
    | grep -v '/$' || true

# ============================================================
# 2. SYNC DESIGNS (with MkDocs transformation)
# ============================================================
echo ""
echo "=== Syncing designs ==="
mkdir -p "$CBOT_DOCS/designs/"

if [[ -z "$DRY_RUN" ]]; then
    # Transform each design file for MkDocs presentation
    for src in "$ALGO_FARM_ROOT/engine/strategies/designs/"*.md; do
        [[ ! -f "$src" ]] && continue
        dest="$CBOT_DOCS/designs/$(basename "$src")"
        echo "  transform: $(basename "$src")"
        python3 "$TRANSFORM_SCRIPT" "$src" "$dest"
    done

    # Remove files in dest that no longer exist in source
    for dest_file in "$CBOT_DOCS/designs/"*.md; do
        [[ ! -f "$dest_file" ]] && continue
        base="$(basename "$dest_file")"
        [[ "$base" == "index.md" ]] && continue
        if [[ ! -f "$ALGO_FARM_ROOT/engine/strategies/designs/$base" ]]; then
            echo "  delete: $base"
            rm "$dest_file"
        fi
    done
else
    echo "  [DRY RUN] Would transform $(ls "$ALGO_FARM_ROOT/engine/strategies/designs/"*.md 2>/dev/null | wc -l | tr -d ' ') design files"
fi

# ============================================================
# 3. SYNC VALIDATED EXPORTS (.cs, .cbotset) → cBot
# ============================================================
echo ""
echo "=== Syncing validated exports ==="
mkdir -p "$CBOT_EXPORTS"

for exports_dir in "$ALGO_FARM_ROOT/engine/strategies/validated/"*_exports; do
    [[ ! -d "$exports_dir" ]] && continue
    strategy_name="$(basename "$exports_dir" _exports)"
    type_folder=$(classify_strategy "$strategy_name")
    # Sanitize folder name (keep readable but filesystem-safe)
    folder_name="${strategy_name// /_}"
    dest="$CBOT_EXPORTS/$type_folder/$folder_name"

    if [[ -z "$DRY_RUN" ]]; then
        mkdir -p "$dest"
    fi

    echo "  $type_folder/$folder_name/"
    rsync -av $DRY_RUN \
        --include='*.cs' --include='*.cbotset' --exclude='*' \
        "$exports_dir/" "$dest/" \
        | grep -v '/$' || true
done

# ============================================================
# 4. REGENERATE INDEX FILES
# ============================================================
if [[ -z "$DRY_RUN" ]]; then
    echo ""
    echo "=== Regenerating index files ==="

    # --- Ideas index ---
    {
        echo "# Strategy Ideas & Research"
        echo ""
        echo "Strategy brainstorms, market analysis, and indicator studies from the Algo Farm research pipeline."
        echo ""
        echo '!!! note "Auto-synced"'
        echo "    This section is populated by \`sync-docs.sh\` from the algo-farm repository. Do not edit files here directly."
        echo ""
        echo "## Documents"
        echo ""
        for f in "$CBOT_DOCS/ideas/"*.md; do
            [[ "$(basename "$f")" == "index.md" ]] && continue
            [[ ! -f "$f" ]] && continue
            name="$(basename "$f" .md)"
            title=$(head -5 "$f" | grep '^# ' | head -1 | sed 's/^# //' || echo "$name")
            echo "- [${title}]($(basename "$f"))"
        done
    } > "$CBOT_DOCS/ideas/index.md"

    # --- Designs index (with status badges) ---
    {
        echo "# Strategy Designs"
        echo ""
        echo "Formal multi-agent design reports: indicator specifications, entry/exit logic, market regime analysis, and risk assessment."
        echo ""
        echo '!!! note "Auto-synced"'
        echo "    This section is populated by \`sync-docs.sh\` from the algo-farm repository. Do not edit files here directly."
        echo ""
        echo "## Documents"
        echo ""
        for f in "$CBOT_DOCS/designs/"*.md; do
            [[ "$(basename "$f")" == "index.md" ]] && continue
            [[ ! -f "$f" ]] && continue
            name="$(basename "$f" .md)"
            title=$(head -5 "$f" | grep '^# ' | head -1 | sed 's/^# //' || echo "$name")
            # Extract status from the SOURCE file (not transformed)
            src_file="$ALGO_FARM_ROOT/engine/strategies/designs/$(basename "$f")"
            if [[ -f "$src_file" ]]; then
                status=$(extract_status "$src_file")
            else
                status="draft"
            fi
            echo "- [${title}]($(basename "$f")) \`${status}\`"
        done
    } > "$CBOT_DOCS/designs/index.md"

    echo "Index files regenerated."
fi

echo ""
echo "=== Sync complete ==="
