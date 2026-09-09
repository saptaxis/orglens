#!/bin/bash
set -euo pipefail

# orglens demo — walks through the full flow: install, config, CLI, snapshot, skills
# Usage: DOCS_ROOT=/path/to/docs ./demo.sh [step-number]

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEP="${1:-all}"
VENV="${ORGLENS_VENV:-$HERE/.venv}"

# No default is possible here: this is your documents tree, not a path this
# script can guess. It used to default to a container path from the machine
# it was written on, which meant the demo silently found nothing anywhere else.
DOCS_ROOT="${DOCS_ROOT:-}"
if [ -z "$DOCS_ROOT" ]; then
    echo "Set DOCS_ROOT to your documents tree, e.g.:" >&2
    echo "    DOCS_ROOT=~/Documents/notes ./demo.sh" >&2
    exit 1
fi

print_header() {
    echo ""
    echo "=== Step $1: $2 ==="
    echo ""
}

wait_for_user() {
    if [ "$STEP" != "all" ]; then return; fi
    echo ""
    read -rp "Press Enter to continue (Ctrl+C to stop)... "
    echo ""
}

# --- Step 1: Install ---
if [ "$STEP" = "all" ] || [ "$STEP" = "1" ]; then
    print_header 1 "Install orglens"

    if [ ! -d "$VENV" ]; then
        echo "Creating virtualenv at $VENV..."
        python3 -m venv "$VENV"
    fi

    echo "Installing orglens in editable mode..."
    "$VENV/bin/pip" install -e . --quiet
    echo "Installed: $("$VENV/bin/orglens" --help | head -1)"

    wait_for_user
fi

# --- Step 2: Config ---
if [ "$STEP" = "all" ] || [ "$STEP" = "2" ]; then
    print_header 2 "Configure"

    CONFIG_DIR="$HOME/.config/orglens"
    CONFIG_FILE="$CONFIG_DIR/config.yaml"

    if [ -f "$CONFIG_FILE" ]; then
        echo "Config already exists:"
        cat "$CONFIG_FILE"
    else
        mkdir -p "$CONFIG_DIR"
        echo "docs_root: $DOCS_ROOT" > "$CONFIG_FILE"
        echo "Created config at $CONFIG_FILE:"
        cat "$CONFIG_FILE"
    fi

    wait_for_user
fi

# --- Step 3: CLI commands ---
if [ "$STEP" = "all" ] || [ "$STEP" = "3" ]; then
    print_header 3 "CLI commands"

    echo "--- orglens list ---"
    "$VENV/bin/orglens" list
    echo ""

    echo "--- orglens status ---"
    "$VENV/bin/orglens" status
    echo ""

    echo "--- orglens find plan (first 10) ---"
    "$VENV/bin/orglens" find plan | head -10 || true
    echo ""

    echo "--- orglens find spec orglens ---"
    "$VENV/bin/orglens" find spec orglens
    echo ""

    wait_for_user
fi

# --- Step 4: Snapshot ---
if [ "$STEP" = "all" ] || [ "$STEP" = "4" ]; then
    print_header 4 "Snapshot"

    echo "--- orglens snapshot --stdout (first 40 lines) ---"
    "$VENV/bin/orglens" snapshot --stdout | head -40 || true
    echo "..."
    echo ""

    echo "--- Writing snapshot to cache ---"
    "$VENV/bin/orglens" snapshot
    echo ""

    wait_for_user
fi

# --- Step 5: Skills ---
if [ "$STEP" = "all" ] || [ "$STEP" = "5" ]; then
    print_header 5 "Skills"

    echo "Skills this repo ships (not installed by this step):"
    npx --yes skills@latest add . -l --full-depth 2>/dev/null | grep -E "^│    [a-z]" || \
        echo "  (needs node; skills live in skills/ and capabilities/decks/*/skills/)"
    echo ""

    echo "Skill file:"
    head -10 skills/orglens/SKILL.md
    echo "..."
    echo ""

    echo "Skill frontmatter validates:"
    python3 -c "
import yaml
fm = open('skills/orglens/SKILL.md').read().split('---')
data = yaml.safe_load(fm[1])
print(f'  name: {data[\"name\"]}')
print(f'  description: {data[\"description\"][:80]}...')
"
    echo ""

    echo "References:"
    ls -la skills/orglens/references/
    echo ""

    echo "To install into every detected agent:"
    echo "  npx skills add $(pwd) -g -a '*' -y --full-depth"
    echo ""
fi

# --- Step 6: Test suite ---
if [ "$STEP" = "all" ] || [ "$STEP" = "6" ]; then
    print_header 6 "Test suite"

    "$VENV/bin/pip" install pytest --quiet
    "$VENV/bin/python" -m pytest tests/ -v --tb=short
    echo ""
fi

echo ""
echo "=== Demo complete ==="
echo ""
echo "Next steps:"
echo "  1. Install skills: npx skills add $(pwd) -g -a '*' -y --full-depth"
echo "  2. Ask: 'what projects exist?' — orglens skill should fire"
echo "  3. Ask: 'where does a design doc go?' — should read the generated reference"
echo ""
