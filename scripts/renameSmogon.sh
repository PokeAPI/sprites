#!/bin/bash
# Usage: $0 <generationID>
# If not submitted, generationID will be 6

regex="^([0-9]+)_?([0-9]+)?([sbfg]+)?.png$"


convert(){
    local id
    local form
    local isFemale
    local isShiny
    local isBack
    local isGmax
    local destination
    local inputGeneration="${1:-6}"
    local files="../smogon/gen$inputGeneration/"

    cd "$files" || exit

    local destinationRoot='../../sprites/pokemon'

    for smogonName in *.png; do
        id=""
        form=""
        isFemale=""
        isShiny=""
        isBack=""
        isGmax=""
        destination="$destinationRoot"
        if [[ $smogonName =~ $regex ]]; then
            id="${BASH_REMATCH[1]}"
            form="${BASH_REMATCH[2]}"
            if [[ "${BASH_REMATCH[3]}" == *b*  ]]; then
                isBack="back"
                destination="$destination/back"
            fi
            if [[ "${BASH_REMATCH[3]}" == *s*  ]]; then
                isShiny="shiny"
                destination="$destination/shiny"
            fi
            if [[ "${BASH_REMATCH[3]}" == *f*  ]]; then
                isFemale="female"
                destination="$destination/female"
            fi
            if [[ "${BASH_REMATCH[3]}" == *g*  ]]; then
                isGmax="gmax"
            fi
            if [ ! "$form" ] && ! [ "$isGmax" ]; then
                echo "Copying $isBack $isFemale $isShiny $id $form" | tr -s " "
                mkdir -p "$destination"
                cp "$smogonName" "$destination/$id.png"
            fi
        fi
    done

    cd - || exit
}

convert "$1"
