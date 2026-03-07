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
    # Folder where images downloaded from the Smogon spreadsheet are stored.
    local files="downloads/"
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
                    # Try to fetch the pokemon by the variety name extracted from forms.json
                    response=$(curl -sS "https://pokeapi.co/api/v2/pokemon/$pokemonName/" 2>/dev/null)
                    pokemonID=$(echo "$response" | jq -r '.id' 2>/dev/null)

                    if [ -n "$pokemonID" ] && [ "$pokemonID" != "null" ]; then
                        echo "[+] Found variety by name: Moving $smogonName to $destination/$pokemonID.png"
                        cp "$smogonName" "$destination/$pokemonID.png"
                    else
                        # Search all forms from Pokémon API
                        echo "[!] Variety '$pokemonName' not found directly. Searching in Pokémon forms..."

                        pokemonResponse=$(curl -sS "https://pokeapi.co/api/v2/pokemon/$id/" 2>/dev/null)

                        # Get all forms from the pokemon and find matching one
                        formSuffix=$(echo "$pokemonResponse" | jq -r \
                            --arg name "$pokemonName" \
                            '.forms[] | select(.name == $name) | .name | sub("^[^#-]+-"; "")' 2>/dev/null)

                        if [ -n "$formSuffix" ] && [ "$formSuffix" != "null" ] && [ "$formSuffix" != "$pokemonName" ]; then
                            destFile="${id}-${formSuffix}.png"
                            
                            echo "[+] Found in forms: Moving $smogonName to $destination/$destFile"
                            cp "$smogonName" "$destination/$destFile"
                        else
                            echo "[!] No matching form found for $pokemonName."
                        fi
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
