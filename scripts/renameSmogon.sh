#!/bin/bash
# Usage: $0 <generationID>
# If not submitted, generationID will be 6

regex="^([0-9]+)_?([0-9]+)?([sbfg]+)?.png$"

ensureCommands(){
    local commands="jq"
    for commandToCheck in $commands; do
        if ! command -v $commandToCheck &> /dev/null; then
            echo "$commandToCheck is required"
            exit
        fi
    done
}

removeLeadingZero(){
    local id="$1"
    id=${id/#0/}
    id=${id/#0/}
    echo "$id"
}

convert(){
    local id
    local form
    local isFemale
    local isShiny
    local isBack
    local isGmax
    local destination
    local speciesName
    local pokemonID
    local pokemonName
    local inputGeneration="${1:-6}"
    local files="../smogon/gen$inputGeneration/"
    local formDS
    formDS=$(jq . forms.json)
    # echo "$formDS" | jq -r '.["885"]'

    cd "$files" || exit

    local destinationRoot='../../sprites/pokemon'

    for smogonName in *.png; do
        id=""
        form=""
        isFemale=""
        isShiny=""
        isBack=""
        isGmax=""
        speciesName=""
        pokemonID=""
        pokemonName=""
        destination="$destinationRoot"
        if [[ $smogonName =~ $regex ]]; then
            #id=$(echo "${BASH_REMATCH[1]}" | sed 's/^0*//') # Extremely slow
            id=$(removeLeadingZero "${BASH_REMATCH[1]}") # Slow if function
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
            if [ "$isGmax" ]; then
                speciesName=$(curl -sS "https://pokeapi.co/api/v2/pokemon-species/$id/" | jq -r '.name')
                pokemonID=$(curl -sS "https://pokeapi.co/api/v2/pokemon/$speciesName-$isGmax/" | jq -r '.id' 2>/dev/null)
                if [ $? -ne 0 ]; then
                    echo "[-] Pkmn $speciesName-$isGmax wasn't found in PokeAPI"
                else
                    echo "[+] Copying GMax $smogonName to $destination/$pokemonID.png"
                    cp "$smogonName" "$destination/$pokemonID.png"
                fi
            fi
            if [ "$form" ]; then
                pokemonName=$(echo "$formDS" | jq -r ".[\"${id}_${form}\"]")
                if [ $? -ne 0 ] || [ "$pokemonName" == 'null' ]; then
                    echo "[-] Form ${id}_${form} wasn't found in the JSON mapping"
                else
                    pokemonID=$(curl -sS "https://pokeapi.co/api/v2/pokemon/$pokemonName/" | jq -r '.id' 2>/dev/null)
                    if [ $? -ne 0 ]; then
                        echo "[-] Pkmn $pokemonName wasn't found in PokeAPI"
                    else
                        echo "[+] Copying Form $smogonName to $destination/$pokemonID.png"
                        cp "$smogonName" "$destination/$pokemonID.png"
                    fi
                fi
            fi
            if [ ! "$form" ] && [ ! "$isGmax" ]; then
                echo "[+] Copying Pkmn $smogonName $destination/$id.png"
                mkdir -p "$destination"
                cp "$smogonName" "$destination/$id.png"
            fi
        fi
    done

    cd - || exit
}

ensureCommands
convert "$1"
