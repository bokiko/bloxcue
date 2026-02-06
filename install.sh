#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
AUTO_MODE=0
SCOPE_ARG=""
STRUCTURE_ARG=""
while [ $# -gt 0 ]; do
    case "$1" in
        --uninstall)
            echo -e "${YELLOW}Uninstalling bloxcue...${NC}"
            echo ""
            if [ -f "$HOME/.claude/hooks/memory-retrieve.sh" ]; then
                rm -f "$HOME/.claude/hooks/memory-retrieve.sh"
                echo "  Removed: ~/.claude/hooks/memory-retrieve.sh"
            fi
            echo ""
            echo -e "${YELLOW}Note: Your memory files are preserved.${NC}"
            echo "  To fully remove, delete these manually:"
            echo "    rm -rf ~/.claude-memory"
            echo "    rm -rf ./claude-memory"
            echo ""
            echo "  Also remove the hook from ~/.claude/settings.json"
            echo ""
            exit 0
            ;;
        --auto)
            AUTO_MODE=1
            ;;
        --scope)
            shift
            SCOPE_ARG="$1"
            ;;
        --structure)
            shift
            STRUCTURE_ARG="$1"
            ;;
    esac
    shift
done

# Also check env vars as fallbacks for --auto mode
if [ -n "$BLOXCUE_SCOPE" ] && [ -z "$SCOPE_ARG" ]; then
    SCOPE_ARG="$BLOXCUE_SCOPE"
fi
if [ -n "$BLOXCUE_STRUCTURE" ] && [ -z "$STRUCTURE_ARG" ]; then
    STRUCTURE_ARG="$BLOXCUE_STRUCTURE"
fi

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                    BloxCue Installer                      ║"
echo "║         Context blocks for Claude Code                    ║"
echo "║         Save 90% of your tokens                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    echo ""
    echo "Install Python 3:"
    echo "  macOS:        brew install python3"
    echo "  Ubuntu/Debian: sudo apt install python3"
    echo "  Fedora:       sudo dnf install python3"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Python 3 found${NC}"
echo ""

# ============================================
# STEP 1: Installation Scope
# ============================================
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 1/3: Where to install?${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  1) Global (~/.claude-memory)"
echo "     Your personal knowledge base - accessible from any project"
echo "     Best for: general docs, references, personal notes"
echo ""
echo "  2) Project-specific (./claude-memory)"
echo "     Lives in your current project folder"
echo "     Best for: project docs, team sharing via git"
echo ""
echo "  3) Both (recommended)"
echo "     Global for personal stuff + project for project stuff"
echo ""
if [ "$AUTO_MODE" = "1" ]; then
    SCOPE_CHOICE=${SCOPE_ARG:-3}
else
    read -p "Choose [1/2/3] (default: 3): " SCOPE_CHOICE
    SCOPE_CHOICE=${SCOPE_CHOICE:-3}
fi

case $SCOPE_CHOICE in
    1) INSTALL_PATHS=("$HOME/.claude-memory") ;;
    2) INSTALL_PATHS=("$(pwd)/claude-memory") ;;
    3) INSTALL_PATHS=("$HOME/.claude-memory" "$(pwd)/claude-memory") ;;
    *) INSTALL_PATHS=("$HOME/.claude-memory") ;;
esac

echo ""

# ============================================
# STEP 2: Directory Structure
# ============================================
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 2/3: How to organize your blocks?${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  1) By Subject (recommended for most users)"
echo "     guides/ references/ projects/ configs/ notes/"
echo ""
echo "  2) By Project (for freelancers/agencies)"
echo "     client-a/ client-b/ shared/"
echo ""
echo "  3) Developer Setup"
echo "     apis/ databases/ deployment/ frontend/ backend/"
echo ""
echo "  4) DevOps/SysAdmin"
echo "     servers/ networking/ monitoring/ security/ runbooks/"
echo ""
echo "  5) Minimal"
echo "     docs/ notes/"
echo ""
echo "  6) Custom (you specify)"
echo ""
if [ "$AUTO_MODE" = "1" ]; then
    STRUCTURE_CHOICE=${STRUCTURE_ARG:-1}
else
    read -p "Choose [1-6] (default: 1): " STRUCTURE_CHOICE
    STRUCTURE_CHOICE=${STRUCTURE_CHOICE:-1}
fi

case $STRUCTURE_CHOICE in
    1)
        FOLDERS=("guides" "references" "projects" "configs" "notes")
        ;;
    2)
        echo ""
        if [ "$AUTO_MODE" = "1" ]; then
            PROJECTS="project-a,project-b"
        else
            read -p "Enter project/client names (comma-separated): " PROJECTS
            if [ -z "$PROJECTS" ]; then
                PROJECTS="project-a,project-b"
            fi
        fi
        IFS=',' read -ra PROJECT_ARRAY <<< "$PROJECTS"
        FOLDERS=()
        for proj in "${PROJECT_ARRAY[@]}"; do
            FOLDERS+=("$(echo "$proj" | xargs)")  # trim whitespace
        done
        FOLDERS+=("shared")
        ;;
    3)
        FOLDERS=("apis" "databases" "deployment" "frontend" "backend" "notes")
        ;;
    4)
        FOLDERS=("servers" "networking" "monitoring" "security" "runbooks")
        ;;
    5)
        FOLDERS=("docs" "notes")
        ;;
    6)
        echo ""
        if [ "$AUTO_MODE" = "1" ]; then
            CUSTOM_FOLDERS="docs,notes"
        else
            echo "Examples: guides, projects, apis, clients, notes"
            read -p "Enter folder names (comma-separated): " CUSTOM_FOLDERS
        fi
        if [ -z "$CUSTOM_FOLDERS" ]; then
            CUSTOM_FOLDERS="docs,notes"
        fi
        IFS=',' read -ra FOLDERS <<< "$CUSTOM_FOLDERS"
        ;;
esac

echo ""

# ============================================
# STEP 3: Confirm
# ============================================
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 3/3: Confirm${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Ready to install:"
echo ""
echo -e "  ${GREEN}Locations:${NC}"
for path in "${INSTALL_PATHS[@]}"; do
    echo "    → $path"
done
echo ""
echo -e "  ${GREEN}Folders:${NC}"
for folder in "${FOLDERS[@]}"; do
    echo "    → $folder/"
done
echo ""
echo -e "  ${GREEN}Auto-retrieval:${NC} Enabled (hooks will be installed)"
echo ""
if [ "$AUTO_MODE" = "1" ]; then
    CONFIRM="Y"
else
    read -p "Proceed? [Y/n]: " CONFIRM
    CONFIRM=${CONFIRM:-Y}
fi

if [ "$CONFIRM" != "Y" ] && [ "$CONFIRM" != "y" ]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}Installing...${NC}"
echo ""

# ============================================
# CREATE DIRECTORIES
# ============================================
for INSTALL_PATH in "${INSTALL_PATHS[@]}"; do
    echo -e "${GREEN}Creating $INSTALL_PATH${NC}"

    mkdir -p "$INSTALL_PATH"

    # Create folder structure
    for folder in "${FOLDERS[@]}"; do
        folder_clean=$(echo "$folder" | xargs)  # trim whitespace
        # L-4 fix: Validate folder names to prevent path traversal
        if [[ "$folder_clean" == *"/"* ]] || [[ "$folder_clean" == ".."* ]] || [[ "$folder_clean" == "."* ]] || [[ -z "$folder_clean" ]]; then
            echo -e "  ${RED}✗ Skipped invalid folder name: $folder_clean${NC}"
            continue
        fi
        mkdir -p "$INSTALL_PATH/$folder_clean"
        echo "  ✓ $folder_clean/"
    done

    # Create scripts directory
    mkdir -p "$INSTALL_PATH/scripts"

    # Copy indexer
    cp "$SCRIPT_DIR/scripts/indexer.py" "$INSTALL_PATH/scripts/"
    echo "  ✓ scripts/indexer.py"

    # Create getting started guide
    FIRST_FOLDER=$(echo "${FOLDERS[0]}" | xargs)
    cat > "$INSTALL_PATH/$FIRST_FOLDER/getting-started.md" << 'EXAMPLE'
---
title: Getting Started with bloxcue
category: guides
tags: [bloxcue, tutorial, getting-started]
---

# Getting Started with bloxcue

Welcome! This is your first context block. Here's how to use bloxcue:

## Creating Blocks

Each block is a markdown file with:

1. **Frontmatter** (the YAML at the top)
   - `title`: What this block is about
   - `category`: Folder it belongs to
   - `tags`: Keywords for better search

2. **Content** (everything after the frontmatter)
   - Keep it focused on one topic
   - Use headers to organize
   - Include code snippets, commands, links

## Example Block

```markdown
---
title: My API Reference
category: apis
tags: [api, rest, authentication]
---

# My API Reference

Base URL: https://api.example.com

## Authentication
Use Bearer token in headers...
```

## Tips

- **One topic per file** - Better search precision
- **Descriptive tags** - `[deployment, aws, production]` not just `[deploy]`
- **Re-index after adding** - Run the indexer to update search

## Commands

```bash
# Index all blocks
python3 ~/.claude-memory/scripts/indexer.py

# Search blocks
python3 ~/.claude-memory/scripts/indexer.py --search "keyword"

# List all blocks
python3 ~/.claude-memory/scripts/indexer.py --list
```

## Next Steps

1. Delete this file (or keep it as reference)
2. Create your first real block
3. Ask Claude about a topic you documented

Claude will automatically retrieve relevant blocks!
EXAMPLE
    echo "  ✓ $FIRST_FOLDER/getting-started.md"

    echo ""
done

# ============================================
# INSTALL HOOKS
# ============================================
echo -e "${GREEN}Installing auto-retrieval hooks...${NC}"

HOOKS_DIR="$HOME/.claude/hooks"
mkdir -p "$HOOKS_DIR"

# Copy hook files
cp "$SCRIPT_DIR/hooks/memory-retrieve.sh" "$HOOKS_DIR/"
chmod +x "$HOOKS_DIR/memory-retrieve.sh"
echo "  ✓ memory-retrieve.sh"

# Update the hook to use correct path
MEMORY_PATH="${INSTALL_PATHS[0]}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|MEMORY_PATH=.*|MEMORY_PATH=\"$MEMORY_PATH\"|" "$HOOKS_DIR/memory-retrieve.sh"
else
    sed -i "s|MEMORY_PATH=.*|MEMORY_PATH=\"$MEMORY_PATH\"|" "$HOOKS_DIR/memory-retrieve.sh"
fi

# Handle settings.json
SETTINGS_FILE="$HOME/.claude/settings.json"
HOOK_ENTRY='"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "~/.claude/hooks/memory-retrieve.sh"}]}]'

if [ -f "$SETTINGS_FILE" ]; then
    # Create backup before any modification
    BACKUP_FILE="$HOME/.claude/settings.json.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$SETTINGS_FILE" "$BACKUP_FILE"
    echo "  ✓ Backup created: $BACKUP_FILE"
    # Check if hooks section already contains our hook
    if grep -q "memory-retrieve.sh" "$SETTINGS_FILE" 2>/dev/null; then
        echo "  ✓ Hook already in settings.json"
    else
        echo ""
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}Action needed: Add hook to settings.json${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo "Your ~/.claude/settings.json exists. Add this to the hooks section:"
        echo ""
        echo -e "${CYAN}\"UserPromptSubmit\": [{${NC}"
        echo -e "${CYAN}  \"hooks\": [{${NC}"
        echo -e "${CYAN}    \"type\": \"command\",${NC}"
        echo -e "${CYAN}    \"command\": \"~/.claude/hooks/memory-retrieve.sh\"${NC}"
        echo -e "${CYAN}  }]${NC}"
        echo -e "${CYAN}}]${NC}"
        echo ""
        echo "Or ask Claude to add it for you!"
        echo ""
    fi
else
    # Create settings.json with hook
    mkdir -p "$HOME/.claude"
    cat > "$SETTINGS_FILE" << 'SETTINGS'
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "~/.claude/hooks/memory-retrieve.sh"
      }]
    }]
  }
}
SETTINGS
    echo "  ✓ Created ~/.claude/settings.json with hooks"
fi

# ============================================
# RUN INITIAL INDEX
# ============================================
echo ""
echo -e "${GREEN}Running initial index...${NC}"
for INSTALL_PATH in "${INSTALL_PATHS[@]}"; do
    if python3 "$INSTALL_PATH/scripts/indexer.py" 2>/dev/null; then
        :
    else
        echo "  Index will update when you add more files"
    fi
done

# ============================================
# DONE
# ============================================
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   ✓ BloxCue installed!                    ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Your context blocks are ready at:${NC}"
for INSTALL_PATH in "${INSTALL_PATHS[@]}"; do
    echo "  → $INSTALL_PATH"
done
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Quick start:${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  1. Restart Claude Code (to load the hook)"
echo ""
echo "  2. Ask Claude to help you create blocks:"
echo ""
echo -e "     ${GREEN}\"Help me create a block for [topic]. Read the${NC}"
echo -e "     ${GREEN} getting-started guide at ~/.claude-memory/\"${NC}"
echo ""
echo "  3. That's it! Claude retrieves context automatically."
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Commands:"
echo "  Index:   python3 ${INSTALL_PATHS[0]}/scripts/indexer.py"
echo "  Search:  python3 ${INSTALL_PATHS[0]}/scripts/indexer.py --search \"keyword\""
echo "  List:    python3 ${INSTALL_PATHS[0]}/scripts/indexer.py --list"
echo ""
echo -e "${GREEN}Enjoy 90% token savings!${NC}"
echo ""
