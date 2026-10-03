#compdef loofi loofi-fedora-tweaks

# Zsh completion script for loofi-fedora-tweaks CLI
# Install: Copy to a directory in your $fpath (e.g., ~/.zsh/completions/)
# Then run: autoload -Uz compinit && compinit

_loofi_fedora_tweaks() {
    local -a commands
    commands=(
        'info:Show Fedora, desktop, and deployment profile'
        'check:Run the explicit read-only System Check'
        'updates:Inspect update sources'
        'troubleshoot:List or run bounded symptom profiles'
        'changes:Inspect or complete saved plans'
        'activity:Inspect Activity and Recovery entries'
        'doctor:Check dependencies and authorization prerequisites'
        'support-bundle:Export a redacted diagnostic archive'
        'tweaks:List, read, set, and restore tweaks'
        'apps:List and install curated applications'
    )

    if (( CURRENT == 2 )); then
        _describe -t commands 'loofi command' commands
        return
    fi

    if (( CURRENT == 3 )); then
        case $words[2] in
            updates) _values 'action' check conflicts history ;;
            troubleshoot) _values 'action' profiles run show latest compare export ;;
            changes) _values 'action' list show apply verify ;;
            activity) _values 'action' list show related recover export ;;
            tweaks) _values 'action' list get set restore ;;
            apps) _values 'action' list install ;;
        esac
        return
    fi

    _arguments '--json[Output JSON]' '--yes[Confirm execution]' '--help[Show help]'
}

_loofi_fedora_tweaks "$@"
