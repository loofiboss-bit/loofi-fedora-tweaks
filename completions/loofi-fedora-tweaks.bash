# Bash completion script for loofi-fedora-tweaks CLI
# Source this file in your .bashrc: source /path/to/loofi-fedora-tweaks.bash

_loofi_fedora_tweaks() {
    local cur prev words cword
    _init_completion || return

    local commands="info check updates troubleshoot changes activity doctor support-bundle tweaks apps"

    local updates_actions="check conflicts history"
    local troubleshoot_actions="profiles run show latest compare export"
    local changes_actions="list show apply verify"
    local activity_actions="list show related recover export"
    local tweaks_actions="list get set restore"
    local apps_actions="list install"

    case "${cword}" in
        1)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            return 0
            ;;
        2)
            case "${prev}" in
                updates) COMPREPLY=($(compgen -W "${updates_actions}" -- "${cur}")) ;;
                troubleshoot) COMPREPLY=($(compgen -W "${troubleshoot_actions}" -- "${cur}")) ;;
                changes) COMPREPLY=($(compgen -W "${changes_actions}" -- "${cur}")) ;;
                activity) COMPREPLY=($(compgen -W "${activity_actions}" -- "${cur}")) ;;
                tweaks) COMPREPLY=($(compgen -W "${tweaks_actions}" -- "${cur}")) ;;
                apps) COMPREPLY=($(compgen -W "${apps_actions}" -- "${cur}")) ;;
            esac
            return 0
            ;;
    esac

    COMPREPLY=($(compgen -W "--json --yes --help" -- "${cur}"))
}

complete -F _loofi_fedora_tweaks loofi-fedora-tweaks
complete -F _loofi_fedora_tweaks loofi
