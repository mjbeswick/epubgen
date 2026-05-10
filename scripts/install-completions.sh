#!/bin/bash
# Install shell completions for epubgen
# Finds the completions directory relative to this script and installs them

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COMPLETIONS_DIR="$SCRIPT_DIR/../completions"

if [ ! -d "$COMPLETIONS_DIR" ]; then
    echo "Error: completions directory not found at $COMPLETIONS_DIR"
    exit 1
fi

SHELL_NAME=$(basename "$SHELL")

case "$SHELL_NAME" in
  bash)
    echo "Installing bash completions..."
    COMPLETION_DIR="${BASH_COMPLETION_USER_DIR:=${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions}"
    mkdir -p "$COMPLETION_DIR"
    cp "$COMPLETIONS_DIR/epubgen.bash" "$COMPLETION_DIR/epubgen"
    echo "✓ Bash completions installed to $COMPLETION_DIR/epubgen"
    echo "  Completions will be available after you restart your shell or run:"
    echo "    source $COMPLETION_DIR/epubgen"
    ;;
  zsh)
    echo "Installing zsh completions..."
    # Try to detect fpath, fall back to oh-my-zsh if available
    if command -v zsh &> /dev/null; then
      COMPLETION_DIR=$(zsh -c 'echo $fpath[1]' 2>/dev/null) || true
    fi
    if [ -z "$COMPLETION_DIR" ] || [ "$COMPLETION_DIR" = "zsh" ]; then
      COMPLETION_DIR="${ZSH_CUSTOM:-${ZSH:-$HOME/.oh-my-zsh}/custom}/completions"
    fi
    mkdir -p "$COMPLETION_DIR"
    cp "$COMPLETIONS_DIR/_epubgen" "$COMPLETION_DIR/_epubgen"
    echo "✓ Zsh completions installed to $COMPLETION_DIR/_epubgen"
    echo "  Completions will be available after you restart your shell"
    ;;
  fish)
    echo "Installing fish completions..."
    COMPLETION_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fish/vendor_completions.d"
    mkdir -p "$COMPLETION_DIR"
    cp "$COMPLETIONS_DIR/epubgen.fish" "$COMPLETION_DIR/epubgen.fish"
    echo "✓ Fish completions installed to $COMPLETION_DIR/epubgen.fish"
    echo "  Completions will be available after you restart your shell"
    ;;
  *)
    echo "Error: Unsupported shell: $SHELL_NAME"
    echo "Supported shells: bash, zsh, fish"
    echo ""
    echo "To install completions manually for your shell, copy the appropriate file:"
    echo "  Bash: cp $COMPLETIONS_DIR/epubgen.bash ~/.local/share/bash-completion/completions/epubgen"
    echo "  Zsh:  cp $COMPLETIONS_DIR/_epubgen ~/.oh-my-zsh/custom/completions/"
    echo "  Fish: cp $COMPLETIONS_DIR/epubgen.fish ~/.local/share/fish/vendor_completions.d/"
    exit 1
    ;;
esac

echo ""
echo "Shell completions installed! 🎉"
