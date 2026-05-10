#!/usr/bin/env fish
# Fish completion for epubgen
# Install with: cp completions/epubgen.fish ~/.local/share/fish/vendor_completions.d/

# Main commands
set -l commands \
  'generate:Generate an EPUB book from a topic and style' \
  'wizard:Interactive prompt-driven workflow' \
  'styles:Inspect available style presets' \
  'amend:Modify an existing book' \
  'doctor:Check dependencies and configuration' \
  'resume:Resume an interrupted generation'

# Styles
set -l styles \
  'apress' 'cheatsheet' 'for-dummies' 'manning' 'nostarch' \
  'pocket-reference' 'pragprog' 'oreilly' 'academic' 'penguin-classics'

# Models
set -l models \
  'anthropic/claude-opus-4-1' \
  'anthropic/claude-sonnet-4-6' \
  'anthropic/claude-haiku-4-5' \
  'openai/gpt-4' \
  'google/gemini-pro' \
  'deepseek/deepseek-chat'

# Amend operations
set -l amend_ops \
  'rebuild:Re-render figures and reassemble EPUB' \
  'recover:Regenerate the cover' \
  'retitle:Update title and/or subtitle' \
  'remove:Remove a chapter' \
  'reorder:Reorder chapters' \
  'edit:Edit a chapter in $EDITOR' \
  'revise:Have the model revise a chapter'

# Main command completion
complete -c epubgen -n '__fish_seen_subcommand_from' -f
complete -c epubgen -n '__fish_use_subcommand' -a 'generate' -d 'Generate an EPUB book from a topic and style'
complete -c epubgen -n '__fish_use_subcommand' -a 'wizard' -d 'Interactive prompt-driven workflow'
complete -c epubgen -n '__fish_use_subcommand' -a 'styles' -d 'Inspect available style presets'
complete -c epubgen -n '__fish_use_subcommand' -a 'amend' -d 'Modify an existing book'
complete -c epubgen -n '__fish_use_subcommand' -a 'doctor' -d 'Check dependencies and configuration'
complete -c epubgen -n '__fish_use_subcommand' -a 'resume' -d 'Resume an interrupted generation'

# Global flags
complete -c epubgen -l help -d 'Show help message'
complete -c epubgen -l install-completion -d 'Install completion for current shell'
complete -c epubgen -l show-completion -d 'Show completion for current shell'

# Generate command completions
complete -c epubgen -n '__fish_seen_subcommand_from generate' -s s -l style -d 'Style preset' -xa "$styles"
complete -c epubgen -n '__fish_seen_subcommand_from generate' -s o -l out -d 'Output EPUB path' -f
complete -c epubgen -n '__fish_seen_subcommand_from generate' -s w -l workdir -d 'Work directory' -f
complete -c epubgen -n '__fish_seen_subcommand_from generate' -s c -l chapters -d 'Target chapter count' -xa '6 10 12 16'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -s W -l words -d 'Target words per chapter' -xa '2500 3000 3500'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -s m -l model -d 'Model ID' -xa "$models"
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l concurrency -d 'Parallel chapters' -xa '1 2 3 4 5'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l ereader -d 'Tune for e-readers (default)'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l no-ereader -d 'Tune for tablet/desktop'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l no-cover -d 'Skip cover generation'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l no-diagrams -d 'Skip all figures'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l no-images -d 'Skip only generated images'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l cover-prompt -d 'Custom cover prompt'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l source -d 'Reference source' -f
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l author -d 'Author name'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l refine -d 'Interactively refine title/subtitle'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l force -d 'Override options.json mismatch'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l dry-run -d 'Print resolved options and exit'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -s v -l verbose -d 'Debug logging to stderr'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l log -d 'Write log file'
complete -c epubgen -n '__fish_seen_subcommand_from generate' -l log-file -d 'Log file path' -f

# Amend command completions
complete -c epubgen -n '__fish_seen_subcommand_from amend' -a 'rebuild' -d 'Re-render figures and reassemble EPUB'
complete -c epubgen -n '__fish_seen_subcommand_from amend' -a 'recover' -d 'Regenerate the cover'
complete -c epubgen -n '__fish_seen_subcommand_from amend' -a 'retitle' -d 'Update title and/or subtitle'
complete -c epubgen -n '__fish_seen_subcommand_from amend' -a 'remove' -d 'Remove a chapter'
complete -c epubgen -n '__fish_seen_subcommand_from amend' -a 'reorder' -d 'Reorder chapters'
complete -c epubgen -n '__fish_seen_subcommand_from amend' -a 'edit' -d 'Edit a chapter in $EDITOR'
complete -c epubgen -n '__fish_seen_subcommand_from amend' -a 'revise' -d 'Have the model revise a chapter'

# Styles command completions
complete -c epubgen -n '__fish_seen_subcommand_from styles' -a 'list' -d 'List all styles'
complete -c epubgen -n '__fish_seen_subcommand_from styles' -a 'show' -d 'Show a specific style'
