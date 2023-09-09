#/usr/bin/env bash
# bash completion for nrrdbook

shopt -s progcomp
_nrrdbook() {
    local cur firstword complete_options
    
    cur=$2
    prev=$3
	firstword=$(__get_firstword)

	GLOBAL_OPTIONS="\
        config\
        delete\
        edit\
        export\
        info\
        list\
        modify\
        mutt\
        new\
        notes\
        query\
        search\
        shell\
        unset\
        version\
        --config\
        --help"

    CONFIG_OPTIONS="--help"
    DELETE_OPTIONS="--help --force"
    EDIT_OPTIONS="--help"
    EXPORT_OPTIONS="--help"
    INFO_OPTIONS="--help --page"
    LIST_OPTIONS="--help --page"
    MODIFY_OPTIONS="--help"
    MODIFY_OPTIONS_WA="\
        --anniversary\
        --assistant\
        --birthday\
        --calurl\
        --company\
        --display\
        --division\
        --fburl\
        --first\
        --gender\
        --language\
        --last\
        --manager\
        --new-alias\
        --nickname\
        --notes\
        --office\
        --photo\
        --spouse\
        --tags\
        --title\
        --add-address\
        --add-email\
        --add-messaging\
        --add-pgpkey\
        --add-phone\
        --add-website\
        --del-address\
        --del-email\
        --del-messaging\
        --del-pgpkey\
        --del-phone\
        --del-website"
    MUTT_OPTIONS="--help"
    NEW_OPTIONS="--help"
    NEW_OPTIONS_WA="\
        --address\
        --alias\
        --anniversary\
        --assistant\
        --birthday\
        --calurl\
        --company\
        --display\
        --division\
        --email\
        --fburl\
        --first\
        --gender\
        --language\
        --last\
        --manager\
        --messaging\
        --nickname\
        --notes\
        --office\
        --pgpkey\
        --phone\
        --photo\
        --spouse\
        --tags\
        --title\
        --website"
    NOTES_OPTIONS="--help"
    QUERY_OPTIONS="--help --json"
    QUERY_OPTIONS_WA="--limit"
    SEARCH_OPTIONS="--help --page"
    SHELL_OPTIONS="--help"
    UNSET_OPTIONS="--help"
    VERSION_OPTIONS="--help"

	case "${firstword}" in
	config)
		complete_options="$CONFIG_OPTIONS"
		complete_options_wa=""
		;;
	delete)
		complete_options="$DELETE_OPTIONS"
		complete_options_wa=""
		;;
	edit)
		complete_options="$EDIT_OPTIONS"
		complete_options_wa=""
		;;
	export)
		complete_options="$EXPORT_OPTIONS"
		complete_options_wa=""
		;;
	info)
		complete_options="$INFO_OPTIONS"
		complete_options_wa=""
		;;
	list)
		complete_options="$LIST_OPTIONS"
		complete_options_wa=""
		;;
	modify)
		complete_options="$MODIFY_OPTIONS"
		complete_options_wa="$MODIFY_OPTIONS_WA"
		;;
	mutt)
		complete_options="$MUTT_OPTIONS"
		complete_options_wa=""
		;;
	new)
		complete_options="$NEW_OPTIONS"
		complete_options_wa="$NEW_OPTIONS_WA"
		;;
	notes)
		complete_options="$NOTES_OPTIONS"
		complete_options_wa=""
		;;
	query)
		complete_options="$QUERY_OPTIONS"
		complete_options_wa="$QUERY_OPTIONS_WA"
		;;
	search)
		complete_options="$SEARCH_OPTIONS"
		complete_options_wa=""
		;;
 	shell)
		complete_options="$SHELL_OPTIONS"
		complete_options_wa=""
		;;
	unset)
		complete_options="$UNSET_OPTIONS"
		complete_options_wa=""
		;;
	version)
		complete_options="$VERSION_OPTIONS"
		complete_options_wa=""
		;;

	*)
        complete_options="$GLOBAL_OPTIONS"
        complete_options_wa=""
		;;
	esac


    for opt in "${complete_options_wa}"; do
        [[ $opt == $prev ]] && return 1 
    done

    all_options="$complete_options $complete_options_wa"
    COMPREPLY=( $( compgen -W "$all_options" -- $cur ))
	return 0
}

__get_firstword() {
	local firstword i
 
	firstword=
	for ((i = 1; i < ${#COMP_WORDS[@]}; ++i)); do
		if [[ ${COMP_WORDS[i]} != -* ]]; then
			firstword=${COMP_WORDS[i]}
			break
		fi
	done
 
	echo $firstword
}
 
complete -F _nrrdbook nrrdbook
