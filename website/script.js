import { Pokedex } from "https://cdn.jsdelivr.net/gh/pokeapi/pokeapi-js-wrapper@2.0.2/src/index.js";

document.addEventListener('DOMContentLoaded', async () => {
    const P = await Pokedex.init({
        cache: true,
        cacheImages: true,
        limit: 100000,
    });

    const searchInput = document.getElementById('searchInput');
    const displayBtn = document.getElementById('displayBtn');
    const resultsContainer = document.getElementById('results');
    const themeToggle = document.getElementById('themeToggle');

    let pokemonList = [];
    let itemList = [];
    let pokemonFormList = [];
    let typeList = [];

    const applyTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    };

    const toggleTheme = () => {
        const currentTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    };

    themeToggle.addEventListener('click', toggleTheme);

    // Set initial theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        applyTheme(savedTheme);
    }

    const loadAllNames = async () => {
        try {
            const [pokemons, items, pokemonForms, types] = await Promise.all([
                P.getPokemonsList(),
                P.getItemsList(),
                P.getPokemonFormsList(),
                P.getTypesList()
            ]);
            pokemonList = pokemons.results.map(p => p.name);
            itemList = items.results.map(i => i.name);
            pokemonFormList = pokemonForms.results.map(f => f.name);
            typeList = types.results.map(t => t.name);
        } catch (error) {
            console.error("Failed to load initial data:", error);
        }
    };

    const autocomplete = (inp) => {
        let currentFocus;

        const handleInput = function(e) {
            const searchType = document.querySelector('input[name="searchType"]:checked').value;
            let arr;
            if (searchType === 'pokemon') {
                arr = pokemonList;
            } else if (searchType === 'item') {
                arr = itemList;
            } else if (searchType === 'pokemon-form') {
                arr = pokemonFormList;
            } else {
                arr = typeList;
            }
            let a, b, i, val = this.value;
            closeAllLists();
            if (!val) { return false;}
            currentFocus = -1;
            a = document.createElement("DIV");
            a.setAttribute("id", this.id + "autocomplete-list");
            a.setAttribute("class", "autocomplete-items");
            this.parentNode.appendChild(a);
            for (i = 0; i < arr.length; i++) {
                if (arr[i].substr(0, val.length).toUpperCase() == val.toUpperCase()) {
                    b = document.createElement("DIV");
                    b.innerHTML = "<strong>" + arr[i].substr(0, val.length) + "</strong>";
                    b.innerHTML += arr[i].substr(val.length);
                    b.innerHTML += "<input type='hidden' value='" + arr[i] + "'>";
                    b.addEventListener("click", function(e) {
                        inp.value = this.getElementsByTagName("input")[0].value;
                        closeAllLists();
                    });
                    a.appendChild(b);
                }
            }
        };

        const handleKeyDown = function(e) {
            let x = document.getElementById(this.id + "autocomplete-list");
            if (x) x = x.getElementsByTagName("div");
            if (e.keyCode == 40) {
                currentFocus++;
                addActive(x);
            } else if (e.keyCode == 38) {
                currentFocus--;
                addActive(x);
            } else if (e.keyCode == 13) {
                e.preventDefault();
                if (currentFocus > -1) {
                    if (x) x[currentFocus].click();
                }
            }
        };

        inp.addEventListener("input", handleInput);
        inp.addEventListener("keydown", handleKeyDown);

        function addActive(x) {
            if (!x) return false;
            removeActive(x);
            if (currentFocus >= x.length) currentFocus = 0;
            if (currentFocus < 0) currentFocus = (x.length - 1);
            x[currentFocus].classList.add("autocomplete-active");
        }

        function removeActive(x) {
            for (let i = 0; i < x.length; i++) {
                x[i].classList.remove("autocomplete-active");
            }
        }

        function closeAllLists(elmnt) {
            const x = document.getElementsByClassName("autocomplete-items");
            for (let i = 0; i < x.length; i++) {
                if (elmnt != x[i] && elmnt != inp) {
                    x[i].parentNode.removeChild(x[i]);
                }
            }
        }

        document.addEventListener("click", function (e) {
            closeAllLists(e.target);
        });
    };
    
    document.querySelectorAll('input[name="searchType"]').forEach(radio => {
        radio.addEventListener('change', () => {
            searchInput.value = '';
            closeAllLists();
        });
    });

    const closeAllLists = () => {
        const x = document.getElementsByClassName("autocomplete-items");
        for (let i = 0; i < x.length; i++) {
            x[i].parentNode.removeChild(x[i]);
        }
    };

    const clearResults = () => {
        resultsContainer.innerHTML = '';
    };

    const createGroup = (parent, title, level = 2) => {
        const group = document.createElement('div');
        if (level === 2) {
            group.className = 'sprite-group';
        }
        
        const heading = document.createElement(`h${level}`);
        heading.textContent = title;
        group.appendChild(heading);
        
        const grid = document.createElement('div');
        grid.className = 'sprite-grid';
        group.appendChild(grid);
        
        parent.appendChild(group);
        return grid;
    };

    const renderSpriteCard = (container, url, path) => {
        const card = document.createElement('div');
        card.className = 'sprite-card';
        const img = document.createElement('img');
        img.src = url;
        img.alt = path;
        img.onerror = () => {
            card.innerHTML = `<div class="placeholder">Not Available</div><p>${path}</p>`;
        };
        const title = document.createElement('p');
        title.textContent = path;
        card.appendChild(img);
        card.appendChild(title);
        container.appendChild(card);
    };

    const renderSpritesRecursive = (container, sprites, basePath = '') => {
        for (const key in sprites) {
            const path = basePath ? `${basePath}/${key}` : key;
            const value = sprites[key];
            if (value === null) {
                renderSpriteCard(container, '', path);
            } else if (typeof value === 'string') {
                renderSpriteCard(container, value, path);
            } else if (typeof value === 'object') {
                renderSpritesRecursive(container, value, path);
            }
        }
    };
    
    const romanToInt = (s) => {
        const map = { 'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000 };
        let result = 0;
        for (let i = 0; i < s.length; i++) {
            const current = map[s[i]];
            const next = map[s[i + 1]];
            if (next > current) {
                result -= current;
            } else {
                result += current;
            }
        }
        return result;
    };

    const sortGenerations = (versions) => {
        return Object.keys(versions).sort((a, b) => {
            const aNum = romanToInt(a.split('-')[1]);
            const bNum = romanToInt(b.split('-')[1]);
            return aNum - bNum;
        });
    };

    const searchId = document.getElementById('searchId');

    const displaySprites = async (query, searchType) => {
        if (!query) return;

        clearResults();
        searchId.textContent = '';
        try {
            let resource;
            if (searchType === 'pokemon') {
                resource = await P.getPokemonByName(query);
            } else if (searchType === 'item') {
                resource = await P.getItemByName(query);
            } else if (searchType === 'pokemon-form') {
                resource = await P.getPokemonFormByName(query);
            } else if (searchType === 'type') {
                resource = await P.getTypeByName(query);
            }
            
            if (isNaN(query)) {
                searchId.textContent = `ID: ${resource.id}`;
            } else {
                searchId.textContent = `Name: ${resource.name}`;
            }

            if (searchType === 'item') {
                if (resource.sprites) {
                    const itemGrid = createGroup(resultsContainer, 'Item Sprites');
                    renderSpritesRecursive(itemGrid, resource.sprites, '');
                } else {
                    resultsContainer.innerHTML = '<p>No sprites found for this item.</p>';
                }
                return;
            }

            if (searchType === 'type') {
                if (resource.sprites) {
                    Object.keys(resource.sprites).sort((a, b) => {
                        const aNum = romanToInt(a.split('-')[1]);
                        const bNum = romanToInt(b.split('-')[1]);
                        return aNum - bNum;
                    }).forEach(genKey => {
                        const genGrid = createGroup(resultsContainer, `Generation: ${genKey}`);
                        renderSpritesRecursive(genGrid, resource.sprites[genKey], '');
                    });
                } else {
                    resultsContainer.innerHTML = `<p>No sprites found for this ${searchType}.</p>`;
                }
                return;
            }

            if (searchType === 'pokemon-form') {
                if (resource.sprites && resource.sprites.versions) {
                    Object.keys(resource.sprites.versions).sort((a, b) => {
                        const aNum = romanToInt(a.split('-')[1]);
                        const bNum = romanToInt(b.split('-')[1]);
                        return aNum - bNum;
                    }).forEach(genKey => {
                        const genGrid = createGroup(resultsContainer, `Generation: ${genKey}`);
                        renderSpritesRecursive(genGrid, resource.sprites.versions[genKey], '');
                    });
                } else {
                    resultsContainer.innerHTML = `<p>No sprites found for this ${searchType}.</p>`;
                }
                return;
            }
            
            if (!resource.sprites) {
                resultsContainer.innerHTML = `<p>No sprites found for this ${searchType}.</p>`;
                return;
            }
            const { sprites } = resource;
            const defaultGrid = createGroup(resultsContainer, 'Default Sprites');
            ['front_default', 'back_default', 'front_shiny', 'back_shiny', 'front_female', 'back_female', 'front_shiny_female', 'back_shiny_female'].forEach(key => {
                if (sprites[key]) renderSpriteCard(defaultGrid, sprites[key], key);
            });
            if (sprites.other) {
                for (const otherKey in sprites.other) {
                    const otherGrid = createGroup(resultsContainer, `Other: ${otherKey}`);
                    renderSpritesRecursive(otherGrid, sprites.other[otherKey], '');
                }
            }
            if (sprites.versions) {
                sortGenerations(sprites.versions).forEach(genKey => {
                    const genGrid = createGroup(resultsContainer, `Versions: ${genKey}`);
                    renderSpritesRecursive(genGrid, sprites.versions[genKey], '');
                });
            }
        } catch (error) {
            resultsContainer.innerHTML = `<p>${searchType} not found.</p>`;
        }
    };

    const handleSearch = () => {
        const query = searchInput.value.toLowerCase().trim();
        const searchType = document.querySelector('input[name="searchType"]:checked').value;
        if (query) {
            window.location.hash = `/${searchType}/${query}`;
        }
    };
    
    displayBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') {
            handleSearch();
        }
    });

    const handleHash = () => {
        const path = window.location.hash.substring(1).split('/').filter(p => p);
        if (path.length === 2) {
            const [type, name] = path;
            if (type === 'pokemon' || type === 'item' || type === 'pokemon-form' || type === 'type') {
                searchInput.value = name;
                document.querySelector(`input[value="${type}"]`).checked = true;
                displaySprites(name, type);
            }
        }
    };

    window.addEventListener('hashchange', handleHash);

    await loadAllNames();
    autocomplete(searchInput);
    handleHash();
});