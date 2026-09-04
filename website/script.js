// Sprite Finder - High-performance offline repository asset browser
// Decoupled from remote PokéAPI - consumes pre-categorized website/data/sprite_index.json

document.addEventListener('DOMContentLoaded', async () => {
    const searchInput = document.getElementById('searchInput');
    const displayBtn = document.getElementById('displayBtn');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    const resultsContainer = document.getElementById('results');
    const themeToggle = document.getElementById('themeToggle');
    const themeToggleIcon = document.getElementById('themeToggleIcon');
    const themeToggleText = document.getElementById('themeToggleText');
    const searchId = document.getElementById('searchId');

    let spriteIndex = null;
    let folderSets = {}; // folder -> Set of string IDs for O(1) existence checks

    // --- 1. Theme Management ---
    const updateThemeUI = (theme) => {
        const isDark = theme === 'dark';
        if (themeToggleIcon) themeToggleIcon.textContent = isDark ? '🌙' : '☀️';
        if (themeToggleText) themeToggleText.textContent = isDark ? 'Dark' : 'Light';
    };

    const applyTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        updateThemeUI(theme);
    };

    const toggleTheme = () => {
        const currentTheme = localStorage.getItem('theme') || 
            (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    };

    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    const savedTheme = localStorage.getItem('theme') || 
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(savedTheme);

    // --- 2. Load Local Repository Index ---
    const loadIndex = async () => {
        try {
            const resp = await fetch('data/sprite_index.json');
            if (!resp.ok) {
                throw new Error(`HTTP error ${resp.status}`);
            }
            spriteIndex = await resp.json();

            // Build fast O(1) Sets for folder presence checks
            folderSets = {};
            for (const [folder, items] of Object.entries(spriteIndex.folder_files || {})) {
                folderSets[folder] = new Set(items.map(String));
            }
        } catch (err) {
            console.error('Failed to load sprite index:', err);
            resultsContainer.innerHTML = `
                <div class="sprite-group">
                    <p style="color: var(--muted-text);">
                        Failed to load repository sprite index. Please ensure <code>python scripts/tracker/build_sprite_index.py</code> has been run.
                    </p>
                </div>`;
        }
    };

    // Helper: Get sprite URL (relative for local/dev, GitHub raw CDN when deployed to Pages)
    const getSpriteUrl = (path) => {
        const isLocal = window.location.hostname === 'localhost' || 
                        window.location.hostname === '127.0.0.1' || 
                        window.location.protocol === 'file:';
        if (isLocal) {
            return `../${path}`;
        }
        return `https://raw.githubusercontent.com/PokeAPI/sprites/master/${path}`;
    };

    const viewExt = (v) => (v && v.ext) ? v.ext : '.png';

    // --- 3. UI Construction Helpers ---
    const clearResults = () => {
        resultsContainer.innerHTML = '';
        if (searchId) searchId.textContent = '';
    };

    const createGroup = (parent, title, badge = null) => {
        const group = document.createElement('div');
        group.className = 'sprite-group';

        const header = document.createElement('div');
        header.className = 'group-header';

        const h2 = document.createElement('h2');
        h2.textContent = title;
        header.appendChild(h2);

        if (badge) {
            const badgeSpan = document.createElement('span');
            badgeSpan.className = 'badge-tag';
            badgeSpan.textContent = badge;
            header.appendChild(badgeSpan);
        }

        group.appendChild(header);
        parent.appendChild(group);
        return group;
    };

    const createSubgroup = (group, title, badge = null) => {
        const sub = document.createElement('div');
        sub.className = 'subgroup';

        const h3 = document.createElement('h3');
        h3.className = 'subgroup-title';
        h3.textContent = title;
        if (badge) {
            const tag = document.createElement('span');
            tag.className = 'badge-tag';
            tag.textContent = badge;
            h3.appendChild(tag);
        }
        sub.appendChild(h3);

        const grid = document.createElement('div');
        grid.className = 'sprite-grid';
        sub.appendChild(grid);

        group.appendChild(sub);
        return grid;
    };

    // Helper: Normalize subtext label (removes "Shiny", "Female" and redundant "Default")
    const cleanCardLabel = (raw) => {
        let t = String(raw || '')
            .replace(/\((?:Shiny|Female)\)/gi, '')
            .replace(/\bShiny\b/gi, '')
            .replace(/\bFemale\b/gi, '')
            .replace(/\s+/g, ' ')
            .trim();
        if (t === 'Front Default') return 'Front';
        if (t === 'Back Default') return 'Back';
        if (t.endsWith(' Default')) return t.replace(/ Default$/, '');
        return t || raw;
    };

    const renderCard = (grid, url, rawLabel, isPlaceholder = false, isHires = false, isShiny = null, isFemale = null) => {
        const card = document.createElement('div');
        card.className = `sprite-card${isHires ? ' hires' : ''}`;

        const labelLower = (rawLabel || '').toLowerCase();
        const urlLower = (url || '').toLowerCase();
        const shiny = (typeof isShiny === 'boolean') 
            ? isShiny 
            : (labelLower.includes('shiny') || urlLower.includes('shiny'));
        const female = (typeof isFemale === 'boolean') 
            ? isFemale 
            : (labelLower.includes('female') || urlLower.includes('female'));
        const cleanLabel = cleanCardLabel(rawLabel);

        // Top-right corner indicators (bare symbols, no badge background)
        if (shiny || female) {
            const indicators = document.createElement('div');
            indicators.className = 'sprite-indicators';

            if (shiny) {
                const shinyIcon = document.createElement('span');
                shinyIcon.className = 'indicator-shiny';
                shinyIcon.title = 'Shiny';
                shinyIcon.innerHTML = `
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                        <path d="M10 2L12.5 8L18 10L12.5 12L10 18L7.5 12L2 10L7.5 8Z"/>
                        <path d="M19 15L20.2 18L23 19L20.2 20L19 23L17.8 20L15 19L17.8 18Z"/>
                    </svg>`;
                indicators.appendChild(shinyIcon);
            }

            if (female) {
                const femaleIcon = document.createElement('span');
                femaleIcon.className = 'indicator-female';
                femaleIcon.title = 'Female';
                femaleIcon.innerHTML = `
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="9" r="6"/>
                        <line x1="12" y1="15" x2="12" y2="23"/>
                        <line x1="8" y1="19" x2="16" y2="19"/>
                    </svg>`;
                indicators.appendChild(femaleIcon);
            }

            card.appendChild(indicators);
        }

        // Centered sprite area
        const imgWrap = document.createElement('div');
        imgWrap.className = 'sprite-img-container';

        if (isPlaceholder || !url) {
            imgWrap.innerHTML = `<div class="placeholder">Not Available</div>`;
        } else {
            const img = document.createElement('img');
            img.src = url;
            img.alt = cleanLabel;
            img.loading = 'lazy';
            img.onerror = () => {
                imgWrap.innerHTML = `<div class="placeholder">Not Available</div>`;
            };
            imgWrap.appendChild(img);
        }
        card.appendChild(imgWrap);

        // Uniform baseline text label with plain text prefix for shiny/female
        const p = document.createElement('p');
        p.className = 'sprite-label';

        const labelInner = document.createElement('span');
        labelInner.className = 'label-inner';

        if (shiny || female) {
            const prefixGroup = document.createElement('span');
            prefixGroup.className = 'prefix-group';

            if (shiny) {
                const sSpan = document.createElement('span');
                sSpan.className = 'prefix-tag prefix-shiny';
                sSpan.title = 'Shiny';
                sSpan.textContent = '[S]';
                prefixGroup.appendChild(sSpan);
            }

            if (female) {
                const fSpan = document.createElement('span');
                fSpan.className = 'prefix-tag prefix-female';
                fSpan.title = 'Female';
                fSpan.textContent = '[F]';
                prefixGroup.appendChild(fSpan);
            }

            labelInner.appendChild(prefixGroup);
        }

        const labelText = document.createElement('span');
        labelText.className = 'label-text';
        labelText.textContent = cleanLabel;
        labelInner.appendChild(labelText);

        p.appendChild(labelInner);
        card.appendChild(p);

        grid.appendChild(card);
    };

    // --- 4. Autocomplete ---
    const closeAllLists = () => {
        const list = document.getElementById('autocomplete-list');
        if (list) list.innerHTML = '';
    };

    const setupAutocomplete = () => {
        const handleInput = function () {
            const val = this.value.trim().toLowerCase();
            closeAllLists();
            if (!val || !spriteIndex) return;

            const searchType = document.querySelector('input[name="searchType"]:checked').value;
            let matches = [];

            if (searchType === 'pokemon') {
                const list = spriteIndex.pokemon_list.filter(p => !p.is_form);
                matches = list.filter(p => p.name.includes(val) || String(p.id).startsWith(val)).slice(0, 20);
            } else if (searchType === 'pokemon-form') {
                const list = spriteIndex.pokemon_list.filter(p => p.is_form);
                matches = list.filter(p => p.name.includes(val) || String(p.id).startsWith(val)).slice(0, 20);
            } else if (searchType === 'item') {
                const items = Object.keys(spriteIndex.items_dict || {});
                matches = items.filter(i => i.includes(val)).slice(0, 20).map(i => ({ id: i, name: i }));
            } else if (searchType === 'type') {
                const standardTypes = ['normal', 'fire', 'water', 'grass', 'electric', 'ice', 'fighting', 'poison', 'ground', 'flying', 'psychic', 'bug', 'rock', 'ghost', 'dragon', 'steel', 'dark', 'fairy', 'stellar'];
                matches = standardTypes.filter(t => t.includes(val)).map(t => ({ id: t, name: t }));
            } else if (searchType === 'badge') {
                const badges = (spriteIndex.badges_list || []).map(b => ({ id: b, name: `Badge #${b}` }));
                matches = badges.filter(b => String(b.id).startsWith(val) || b.name.toLowerCase().includes(val)).slice(0, 20);
            }

            if (matches.length === 0) return;

            const container = document.getElementById('autocomplete-list');
            container.innerHTML = '';

            matches.forEach(item => {
                const div = document.createElement('div');
                div.innerHTML = `<span><strong>${item.name}</strong></span> <span style="color:var(--muted-text); font-family:monospace;">#${item.id}</span>`;
                div.addEventListener('click', () => {
                    searchInput.value = item.id;
                    closeAllLists();
                    handleSearch();
                });
                container.appendChild(div);
            });
        };

        searchInput.addEventListener('input', handleInput);
        document.addEventListener('click', (e) => {
            if (e.target !== searchInput) closeAllLists();
        });
    };

    // --- 5. Renderers ---

    // 5.1 Pokémon & Form Renderer (Declarative from Index Schema)
    const displayPokemon = (query, isForm = false) => {
        if (!spriteIndex) return;

        const q = String(query).toLowerCase().trim();
        const list = spriteIndex.pokemon_list || [];

        let entity = list.find(p => p.is_form === isForm && (String(p.id) === q || p.name === q));
        if (!entity && !isForm) {
            entity = list.find(p => String(p.id) === q || p.name === q);
        }

        if (!entity) {
            resultsContainer.innerHTML = `
                <div class="sprite-group">
                    <p style="color: var(--muted-text);">No entry found in index for "${query}".</p>
                </div>`;
            return;
        }

        const idStr = String(entity.id);
        searchId.textContent = `#${entity.id} - ${entity.name}`;

        // 1. Root Sprites (Default pixel art)
        const rootGroup = createGroup(resultsContainer, 'Root Sprites (Default)', 'sprites/pokemon/');
        const rootGrid = createSubgroup(rootGroup, 'Standard Gen 5 Pixel Art');

        (spriteIndex.root_views || []).forEach(view => {
            const hasSprite = folderSets[view.folder]?.has(idStr);
            // If Pokémon has no gender differences, only render female cards if an asset actually exists
            if (view.female && !entity.has_gender_diff && !hasSprite) {
                return;
            }
            const isShiny = view.label.includes('Shiny');
            if (hasSprite) {
                renderCard(rootGrid, getSpriteUrl(`${view.folder}/${idStr}${view.ext}`), view.label, false, false, isShiny, view.female);
            } else {
                renderCard(rootGrid, '', view.label, true, false, isShiny, view.female);
            }
        });

        // 2. Other Sprite Collections (Official Artwork, HOME 3D, Showdown GIFs, Dream World)
        let otherGroup = null;
        (spriteIndex.other_categories || []).forEach(cat => {
            const hasAnyInCat = (cat.views || []).some(v => folderSets[v.folder]?.has(idStr));
            if (hasAnyInCat) {
                if (!otherGroup) {
                    otherGroup = createGroup(resultsContainer, 'Other Sprite Collections', 'sprites/pokemon/other/');
                }
                const grid = createSubgroup(otherGroup, cat.name, cat.badge);
                (cat.views || []).forEach(v => {
                    const hasSprite = folderSets[v.folder]?.has(idStr);
                    const isFemale = v.female || v.label.includes('Female');
                    if (isFemale && !entity.has_gender_diff && !hasSprite) {
                        return;
                    }
                    const isShiny = v.label.includes('Shiny') || (v.folder && v.folder.includes('shiny'));
                    if (hasSprite) {
                        renderCard(grid, getSpriteUrl(`${v.folder}/${idStr}${viewExt(v)}`), v.label, false, cat.is_large, isShiny, isFemale);
                    } else {
                        renderCard(grid, '', v.label, true, cat.is_large, isShiny, isFemale);
                    }
                });
            }
        });

        // 3. Version Sprites - Dynamically discovered and pre-categorized by Generation & Game Groups
        (spriteIndex.generations || []).forEach(gen => {
            const activeGames = [];
            (gen.games || []).forEach(game => {
                const hasAnyInGame = (game.views || []).some(v => folderSets[v.folder]?.has(idStr));
                if (hasAnyInGame) {
                    activeGames.push(game);
                }
            });

            const activeIcons = (gen.icons || []).filter(icon => folderSets[icon.folder]?.has(idStr));

            // Skip generation if no assets exist for this Pokémon
            if (activeGames.length === 0 && activeIcons.length === 0) {
                return;
            }

            const genGroup = createGroup(resultsContainer, gen.title, gen.id);

            // Render game groups (flat if only 1 subcategory, subcategorized if multiple)
            activeGames.forEach(game => {
                // Group views by subcategory (Default, Gray, Transparent, Animated, etc.)
                const subcatMap = new Map();
                (game.views || []).forEach(v => {
                    const isFemale = v.female || v.label.includes('Female') || (v.subpath && v.subpath.includes('female'));
                    const hasSprite = folderSets[v.folder]?.has(idStr);
                    // Omit female view if species has no gender difference AND sprite does not exist
                    if (isFemale && !entity.has_gender_diff && !hasSprite) {
                        return;
                    }
                    const subName = v.subcategory || 'Default';
                    if (!subcatMap.has(subName)) subcatMap.set(subName, []);
                    subcatMap.get(subName).push({ ...v, hasSprite: !!hasSprite });
                });

                if (subcatMap.size <= 1) {
                    // Only one subcategory -> keep flat
                    const grid = createSubgroup(genGroup, game.name, game.folder);
                    const allViews = subcatMap.size === 1 ? Array.from(subcatMap.values())[0] : [];
                    allViews.forEach(v => {
                        const isShiny = v.label.includes('Shiny') || (v.subpath && v.subpath.includes('shiny'));
                        const isFemale = v.female || v.label.includes('Female') || (v.subpath && v.subpath.includes('female'));
                        if (v.hasSprite) {
                            renderCard(grid, getSpriteUrl(`${v.folder}/${idStr}${viewExt(v)}`), v.label, false, false, isShiny, isFemale);
                        } else {
                            renderCard(grid, '', v.label, true, false, isShiny, isFemale);
                        }
                    });
                } else {
                    // Multiple subcategories -> render structured 2-column grid sections
                    const gameSubgroup = document.createElement('div');
                    gameSubgroup.className = 'subgroup';

                    const h3 = document.createElement('h3');
                    h3.className = 'subgroup-title';
                    h3.textContent = game.name;
                    if (game.folder) {
                        const tag = document.createElement('span');
                        tag.className = 'badge-tag';
                        tag.textContent = game.folder;
                        h3.appendChild(tag);
                    }
                    gameSubgroup.appendChild(h3);

                    const subcatsGrid = document.createElement('div');
                    subcatsGrid.className = 'game-subcats-grid';

                    subcatMap.forEach((views, subName) => {
                        const section = document.createElement('div');
                        section.className = 'game-subcat-section';

                        const header = document.createElement('div');
                        header.className = 'game-subcat-header';

                        const subH4 = document.createElement('h4');
                        subH4.className = 'game-subcat-title';
                        subH4.textContent = subName;
                        header.appendChild(subH4);

                        const availableCount = views.filter(v => v.hasSprite).length;
                        const count = document.createElement('span');
                        count.className = 'game-subcat-count';
                        count.textContent = `${availableCount}/${views.length} available`;
                        header.appendChild(count);

                        section.appendChild(header);

                        const grid = document.createElement('div');
                        grid.className = 'sprite-grid';
                        views.forEach(v => {
                            const isShiny = v.label.includes('Shiny') || (v.subpath && v.subpath.includes('shiny'));
                            const isFemale = v.female || v.label.includes('Female') || (v.subpath && v.subpath.includes('female'));
                            if (v.hasSprite) {
                                renderCard(grid, getSpriteUrl(`${v.folder}/${idStr}${viewExt(v)}`), v.label, false, false, isShiny, isFemale);
                            } else {
                                renderCard(grid, '', v.label, true, false, isShiny, isFemale);
                            }
                        });
                        section.appendChild(grid);

                        subcatsGrid.appendChild(section);
                    });

                    gameSubgroup.appendChild(subcatsGrid);
                    genGroup.appendChild(gameSubgroup);
                }
            });

            // Render generation menu icons
            if (activeIcons.length > 0) {
                const grid = createSubgroup(genGroup, '🏷️ Box & Party Icons', `versions/${gen.id}/icons`);
                activeIcons.forEach(icon => {
                    const isFemale = icon.female || icon.label.includes('Female') || (icon.subpath && icon.subpath.includes('female'));
                    renderCard(grid, getSpriteUrl(`${icon.folder}/${idStr}${viewExt(icon)}`), icon.label, false, false, false, isFemale);
                });
            }
        });
    };

    // 5.2 Badges Renderer
    const displayBadges = (query) => {
        if (!spriteIndex || !spriteIndex.badges_list) return;

        const q = query ? parseInt(query, 10) : null;
        let badgesToShow = spriteIndex.badges_list;

        if (q && !isNaN(q)) {
            badgesToShow = badgesToShow.filter(b => b === q);
            searchId.textContent = `Badge #${q}`;
        } else {
            searchId.textContent = `All Badges (${badgesToShow.length})`;
        }

        if (badgesToShow.length === 0) {
            resultsContainer.innerHTML = `<div class="sprite-group"><p style="color:var(--muted-text);">No badge found matching "${query}".</p></div>`;
            return;
        }

        const group = createGroup(resultsContainer, 'Gym Badges', 'sprites/badges/');
        const grid = createSubgroup(group, 'Official Gym Badges (Gens 1-8)');

        badgesToShow.forEach(badgeId => {
            renderCard(grid, getSpriteUrl(`sprites/badges/${badgeId}.png`), `Badge #${badgeId}`);
        });
    };

    // 5.3 Items Renderer
    const displayItem = (query) => {
        if (!spriteIndex || !spriteIndex.items_dict) return;

        const q = String(query).toLowerCase().trim();
        const items = spriteIndex.items_dict;

        let matchKey = Object.keys(items).find(k => k === q) || Object.keys(items).find(k => k.includes(q));

        if (!matchKey) {
            resultsContainer.innerHTML = `<div class="sprite-group"><p style="color:var(--muted-text);">Item "${query}" not found in repository index.</p></div>`;
            return;
        }

        searchId.textContent = `Item: ${matchKey}`;
        const group = createGroup(resultsContainer, `Item: ${matchKey}`, 'sprites/items/');
        const grid = createSubgroup(group, 'Item Variants');

        items[matchKey].forEach(relPath => {
            const folderPart = relPath.includes('/') ? relPath.substring(0, relPath.lastIndexOf('/')) : 'default';
            renderCard(grid, getSpriteUrl(`sprites/items/${relPath}`), folderPart);
        });
    };

    // 5.4 Types Renderer
    const displayType = (query) => {
        if (!spriteIndex || !spriteIndex.types_dict) return;

        const q = String(query).toLowerCase().trim();
        searchId.textContent = `Type: ${q}`;

        const group = createGroup(resultsContainer, `Type Sprites: ${q}`, 'sprites/types/');
        let renderedCount = 0;

        for (const [gen, games] of Object.entries(spriteIndex.types_dict)) {
            for (const [game, files] of Object.entries(games)) {
                const matchFile = files.find(f => f.toLowerCase().includes(q));
                if (matchFile) {
                    renderedCount++;
                    const grid = createSubgroup(group, `${gen} / ${game}`);
                    renderCard(grid, getSpriteUrl(`sprites/types/${gen}/${game}/${matchFile}`), matchFile);
                }
            }
        }

        if (renderedCount === 0) {
            resultsContainer.innerHTML = `<div class="sprite-group"><p style="color:var(--muted-text);">No type icon found for "${query}".</p></div>`;
        }
    };

    // --- 6. Search Dispatcher ---
    const handleSearch = () => {
        const query = searchInput.value.toLowerCase().trim();
        const searchType = document.querySelector('input[name="searchType"]:checked').value;
        if (query || searchType === 'badge') {
            window.location.hash = `/${searchType}/${query}`;
        }
    };

    displayBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keyup', (event) => {
        if (event.key === 'Enter') handleSearch();
    });

    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearSearchBtn.style.display = 'none';
            searchInput.focus();
        });

        searchInput.addEventListener('input', () => {
            clearSearchBtn.style.display = searchInput.value ? 'block' : 'none';
        });
    }

    // Radio change: clear search input & close autocomplete
    document.querySelectorAll('input[name="searchType"]').forEach(radio => {
        radio.addEventListener('change', () => {
            searchInput.value = '';
            if (clearSearchBtn) clearSearchBtn.style.display = 'none';
            closeAllLists();
            if (radio.value === 'badge') {
                searchInput.placeholder = 'Enter badge number (1-77) or leave empty for all...';
            } else if (radio.value === 'item') {
                searchInput.placeholder = 'Enter item name (e.g. poke-ball, master-ball)...';
            } else if (radio.value === 'type') {
                searchInput.placeholder = 'Enter type name (e.g. grass, fire, water)...';
            } else {
                searchInput.placeholder = 'Search by name (e.g. pikachu) or ID (#25)...';
            }
        });
    });

    // --- 7. Hash Routing ---
    const handleHash = () => {
        const parts = window.location.hash.substring(1).split('/').filter(Boolean);
        if (parts.length >= 1) {
            const type = parts[0];
            const query = parts[1] || '';

            const radio = document.querySelector(`input[value="${type}"]`);
            if (radio) radio.checked = true;
            searchInput.value = query;

            clearResults();

            if (type === 'pokemon') {
                displayPokemon(query, false);
            } else if (type === 'pokemon-form') {
                displayPokemon(query, true);
            } else if (type === 'badge') {
                displayBadges(query);
            } else if (type === 'item') {
                displayItem(query);
            } else if (type === 'type') {
                displayType(query);
            }
        }
    };

    window.addEventListener('hashchange', handleHash);

    // --- 8. Initialization ---
    await loadIndex();
    setupAutocomplete();
    if (window.location.hash) {
        handleHash();
    } else {
        // Default show Bulbasaur (#1)
        window.location.hash = '/pokemon/1';
    }
});