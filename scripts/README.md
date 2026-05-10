# Scripts

Utility scripts for epubgen development and setup.

## Shell Completions

### Auto-install (Recommended)

```bash
./scripts/install-completions.sh
```

This script automatically detects your shell and installs completions in the appropriate location:
- **Bash**: `~/.local/share/bash-completion/completions/epubgen`
- **Zsh**: `~/.oh-my-zsh/custom/completions/_epubgen` (or `$fpath[1]/_epubgen`)
- **Fish**: `~/.local/share/fish/vendor_completions.d/epubgen.fish`

After installation, restart your shell to use the completions.

### Manual Install

If you prefer to install manually or use a different location:

```bash
# Bash - user directory
mkdir -p ~/.local/share/bash-completion/completions
cp completions/epubgen.bash ~/.local/share/bash-completion/completions/epubgen

# Bash - system-wide (requires sudo)
sudo cp completions/epubgen.bash /etc/bash_completion.d/epubgen

# Zsh - with oh-my-zsh
mkdir -p ~/.oh-my-zsh/custom/completions
cp completions/_epubgen ~/.oh-my-zsh/custom/completions/_epubgen

# Zsh - other locations
cp completions/_epubgen /usr/local/share/zsh/site-functions/_epubgen

# Fish
mkdir -p ~/.local/share/fish/vendor_completions.d
cp completions/epubgen.fish ~/.local/share/fish/vendor_completions.d/
```

### Test Completions

After installation, start a new shell and test:

```bash
# Bash/Zsh: press TAB after typing partial command
epubgen <TAB>

# See available styles
epubgen generate "Topic" --style <TAB>
```

### Features

Shell completions provide:
- **Command completion**: `generate`, `wizard`, `styles`, `amend`, `doctor`, `resume`
- **Subcommand completion**: `styles list`, `styles show`, `amend recover`, etc.
- **Flag completion**: All `--flag` options with descriptions
- **Argument completion**: 
  - Style choices for `--style`
  - Amend operations (`recover`, `rebuild`, `retitle`, etc.)
  - File/directory paths for positional arguments

### Example Usage

```bash
# Tab to see all commands
epubgen <TAB>

# Get flags for generate
epubgen generate <TAB>

# Filter by style
epubgen generate "Python" --style <TAB>
# Shows: apress, cheatsheet, for-dummies, manning, nostarch, pocket-reference, pragprog, etc.

# Amend operations
epubgen amend <TAB>
# Shows: rebuild, recover, retitle, remove, reorder, edit, revise

# Existing book paths (file/directory completion)
epubgen amend recover <TAB>
```
