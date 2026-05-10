#!/usr/bin/env bash
# Bash completion for epubgen
# Install with: cp completions/epubgen.bash ~/.local/share/bash-completion/completions/epubgen

_epubgen_completions() {
    local cur prev words cword
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    words=("${COMP_WORDS[@]}")
    cword="${COMP_CWORD}"

    # Main commands
    local commands="generate wizard styles amend doctor resume"

    # Generate flags
    local generate_flags="--style --out --workdir --chapters --words --model --concurrency --ereader --no-ereader --no-cover --no-diagrams --no-images --cover-prompt --source --author --refine --force --dry-run --verbose --log --log-file --help"

    # Styles
    local styles="apress cheatsheet for-dummies manning nostarch pocket-reference pragprog oreilly academic penguin-classics"

    # Amend subcommands
    local amend_commands="rebuild recover retitle remove reorder edit revise"

    # Check if we're in a subcommand
    if [[ $cword -gt 1 ]]; then
        local cmd="${words[1]}"

        case "$cmd" in
            generate)
                case "$prev" in
                    --style)
                        COMPREPLY=( $(compgen -W "$styles" -- "$cur") )
                        return 0
                        ;;
                    --model)
                        # Model suggestions
                        local models="anthropic/claude-opus-4-1 anthropic/claude-sonnet-4-6 anthropic/claude-haiku-4-5 openai/gpt-4 google/gemini-pro deepseek/deepseek-chat"
                        COMPREPLY=( $(compgen -W "$models" -- "$cur") )
                        return 0
                        ;;
                esac
                # Flags for generate
                if [[ "$cur" == -* ]]; then
                    COMPREPLY=( $(compgen -W "$generate_flags" -- "$cur") )
                    return 0
                fi
                ;;
            amend)
                # Amend subcommands
                if [[ $cword -eq 2 ]]; then
                    COMPREPLY=( $(compgen -W "$amend_commands" -- "$cur") )
                    return 0
                fi
                ;;
            styles)
                # Styles subcommands
                if [[ $cword -eq 2 ]]; then
                    COMPREPLY=( $(compgen -W "list show" -- "$cur") )
                    return 0
                fi
                ;;
        esac
    fi

    # Main command completion
    if [[ "$cur" == -* ]]; then
        # Global flags
        COMPREPLY=( $(compgen -W "--help --install-completion --show-completion" -- "$cur") )
        return 0
    fi

    # Command completion
    COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
}

complete -o bashdefault -o default -o nospace -F _epubgen_completions epubgen
