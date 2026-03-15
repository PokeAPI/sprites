#!/bin/bash
# Usage: $0 <generationID>
# If not submitted, generationID will be 6

regex="^([0-9]+)_?([0-9]+)?([sbfg]+)?\.(png|gif)$"

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
    local formDSAnimated
    formDS=$(jq . forms.json)
    formDSAnimated="$formDS"  # default to same as formDS
    if [ -f forms-animated.json ]; then
        # Merge forms-animated.json into forms.json (animated overrides original)
        formDSAnimated=$(jq -n --argjson base "$formDS" --argjson animated "$(jq . forms-animated.json)" '$base * $animated')
    fi
    # echo "$formDS" | jq -r '.["885"]'

    cd "$files" || exit

    local destinationRoot='../../sprites/pokemon'
    local bwDestinationRoot="$destinationRoot/versions/generation-v/black-white"

    for smogonName in *.png *.gif; do
        id=""
        form=""
        isFemale=""
        isShiny=""
        isBack=""
        isGmax=""
        speciesName=""
        pokemonID=""
        pokemonName=""
        fileExt=""
        destination="$destinationRoot"
        bwDestination="$bwDestinationRoot"

        if [[ $smogonName =~ $regex ]]; then
            #id=$(echo "${BASH_REMATCH[1]}" | sed 's/^0*//') # Extremely slow
            id=$(removeLeadingZero "${BASH_REMATCH[1]}") # Slow if function
            form="${BASH_REMATCH[2]}"
            fileExt="${BASH_REMATCH[4]}"
            
            # For .gif files, use animated directory
            if [ "$fileExt" == "gif" ]; then
                bwDestination="$bwDestination/animated"
            fi
            
            if [[ "${BASH_REMATCH[3]}" == *b*  ]]; then
                isBack="back"
                destination="$destination/back"
                bwDestination="$bwDestination/back"
            fi
            if [[ "${BASH_REMATCH[3]}" == *s*  ]]; then
                isShiny="shiny"
                destination="$destination/shiny"
                bwDestination="$bwDestination/shiny"
            fi
            if [[ "${BASH_REMATCH[3]}" == *f*  ]]; then
                isFemale="female"
                destination="$destination/female"
                bwDestination="$bwDestination/female"
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
                    echo "[+] Copying GMax $smogonName to $bwDestination/$pokemonID.$fileExt"
                    if [ "$fileExt" == "png" ]; then
                        mv "$smogonName" "$destination/$pokemonID.$fileExt"
                    fi
                    mv "$smogonName" "$bwDestination/$pokemonID.$fileExt"
                fi
            fi
            if [ "$form" ]; then
                # Use animated forms for .gif, regular forms for .png
                if [ "$fileExt" == "gif" ]; then
                    pokemonName=$(echo "$formDSAnimated" | jq -r ".[\"${id}_${form}\"]")
                else
                    pokemonName=$(echo "$formDS" | jq -r ".[\"${id}_${form}\"]")
                fi

                if [ $? -ne 0 ] || [ "$pokemonName" == 'null' ]; then
                    echo "[-] Form ${id}_${form} wasn't found in the JSON mapping"
                else
                    # Try to fetch the pokemon by the variety name extracted from forms.json
                    response=$(curl -sS "https://pokeapi.co/api/v2/pokemon/$pokemonName/" 2>/dev/null)
                    pokemonID=$(echo "$response" | jq -r '.id' 2>/dev/null)

                    if [ -n "$pokemonID" ] && [ "$pokemonID" != "null" ]; then
                        echo "[+] Found variety by name: Moving $smogonName to $bwDestination/$pokemonID.$fileExt"
                        if [ "$fileExt" == "png" ]; then
                            mv "$smogonName" "$destination/$pokemonID.$fileExt"
                        fi
                        mv "$smogonName" "$bwDestination/$pokemonID.$fileExt"
                    else
                        # Search all forms from Pokémon API
                        echo "[!] Variety '$pokemonName' not found directly. Searching in Pokémon forms..."

                        pokemonResponse=$(curl -sS "https://pokeapi.co/api/v2/pokemon/$id/" 2>/dev/null)

                        # Get all forms from the pokemon and find matching one
                        formSuffix=$(echo "$pokemonResponse" | jq -r \
                            --arg name "$pokemonName" \
                            '.forms[] | select(.name == $name) | .name | sub("^[^#-]+-"; "")' 2>/dev/null)

                        if [ -n "$formSuffix" ] && [ "$formSuffix" != "null" ] && [ "$formSuffix" != "$pokemonName" ]; then
                            destFile="${id}-${formSuffix}.$fileExt"
                            mkdir -p "$destination"
                            mkdir -p "$bwDestination"

                            echo "[+] Found in forms: Moving $smogonName to $bwDestination/$destFile"
                            if [ "$fileExt" == "png" ]; then
                                mv "$smogonName" "$destination/$destFile"
                            fi
                            mv "$smogonName" "$bwDestination/$destFile"
                        else
                            echo "[!] No matching form found for $pokemonName."
                        fi
                    fi
                fi
            fi
            if [ ! "$form" ] && [ ! "$isGmax" ]; then
                echo "[+] Copying Pkmn $smogonName to $bwDestination/$id.$fileExt"
                mkdir -p "$destination"
                mkdir -p "$bwDestination"
                if [ "$fileExt" == "png" ]; then
                    mv "$smogonName" "$destination/$id.$fileExt"
                fi
                mv "$smogonName" "$bwDestination/$id.$fileExt"
            fi
        fi
    done

    cd - || exit
}

ensureCommands
convert "$1"
