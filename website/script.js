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

        // If hosted on a GitHub Pages fork (e.g. <username>.github.io/<repo>)
        if (window.location.hostname.endsWith('github.io')) {
            const user = window.location.hostname.split('.')[0];
            const repo = window.location.pathname.split('/')[1] || 'sprites';
            // Primary source: check user's fork/branch first, fallback to upstream PokeAPI
            if (user.toLowerCase() !== 'pokeapi') {
                return `https://raw.githubusercontent.com/${user}/${repo}/gen2-transparent/${path}`;
            }
        }

        return `https://raw.githubusercontent.com/PokeAPI/sprites/master/${path}`;
    };

    const viewExt = (v) => (v && v.ext) ? v.ext : '.png';

    // --- 3. UI Construction Helpers & Deep Linking ---
    const showToast = (message) => {
        let toast = document.getElementById('globalToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'globalToast';
            toast.className = 'global-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add('show');
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {
            toast.classList.remove('show');
        }, 2200);
    };

    const copyAnchorLink = async (anchorId, btn) => {
        const cleanHash = window.location.hash ? window.location.hash.split('?')[0] : '';
        let linkParam = '';
        if (anchorId.startsWith('game-')) {
            linkParam = `?game=${encodeURIComponent(anchorId.replace(/^game-/, ''))}`;
        } else if (anchorId.startsWith('category-')) {
            linkParam = `?cat=${encodeURIComponent(anchorId.replace(/^category-/, ''))}`;
        } else {
            linkParam = `?target=${encodeURIComponent(anchorId)}`;
        }

        const url = `${window.location.origin}${window.location.pathname}${linkParam}${cleanHash}`;
        
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(url);
                showToast('Link copied to clipboard!');
            } else {
                const ta = document.createElement('textarea');
                ta.value = url;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showToast('Link copied to clipboard!');
            }
        } catch {
            showToast(`Anchor: ${linkParam}`);
        }

        if (window.history && window.history.replaceState) {
            window.history.replaceState(null, '', url);
        }

        if (btn) {
            const origHtml = btn.innerHTML;
            btn.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
            btn.classList.add('copied');
            setTimeout(() => {
                btn.innerHTML = origHtml;
                btn.classList.remove('copied');
            }, 1800);
        }
    };

    const createAnchorBtn = (anchorId) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'anchor-link-btn';
        btn.title = 'Copy link to this section';
        btn.setAttribute('aria-label', 'Copy link to section');
        btn.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>`;
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            copyAnchorLink(anchorId, btn);
        });
        return btn;
    };

    const getDeepLinkTarget = () => {
        const params = new URLSearchParams(window.location.search);
        const qIdx = window.location.hash.indexOf('?');
        if (qIdx !== -1) {
            new URLSearchParams(window.location.hash.substring(qIdx)).forEach((val, key) => {
                if (!params.has(key)) params.set(key, val);
            });
        }

        const game = params.get('game');
        if (game) return `game-${game}`;
        const cat = params.get('cat');
        if (cat) return `category-${cat}`;
        const target = params.get('target') || params.get('anchor');
        return target ? target.replace(/^#/, '') : null;
    };

    const scrollToTarget = (targetId) => {
        if (!targetId) return;

        requestAnimationFrame(() => {
            setTimeout(() => {
                const pureId = targetId.replace(/^(game|category)-/, '');
                const el = document.getElementById(targetId) || 
                           document.querySelector(`[data-game="${pureId}"]`) ||
                           document.querySelector(`[data-category="${pureId}"]`) ||
                           document.getElementById(pureId);

                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 100);
        });
    };

    const clearResults = () => {
        resultsContainer.innerHTML = '';
        if (searchId) searchId.textContent = '';
    };

    const createGroup = (parent, title, badge = null, elementId = null) => {
        const group = document.createElement('div');
        group.className = 'sprite-group';
        if (elementId) {
            group.id = elementId;
        }

        const header = document.createElement('div');
        header.className = 'group-header';

        const h2 = document.createElement('h2');
        const titleSpan = document.createElement('span');
        titleSpan.textContent = title;
        h2.appendChild(titleSpan);

        if (elementId) {
            h2.appendChild(createAnchorBtn(elementId));
        }
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

    const createSubgroup = (group, title, badge = null, elementId = null) => {
        const sub = document.createElement('div');
        sub.className = 'subgroup';
        if (elementId) {
            sub.id = elementId;
        }

        const h3 = document.createElement('h3');
        h3.className = 'subgroup-title';

        const titleSpan = document.createElement('span');
        titleSpan.textContent = title;
        h3.appendChild(titleSpan);

        if (elementId) {
            h3.appendChild(createAnchorBtn(elementId));
        }

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
        const labelLower = (rawLabel || '').toLowerCase();
        const urlLower = (url || '').toLowerCase();
        const shiny = (typeof isShiny === 'boolean') 
            ? isShiny 
            : (labelLower.includes('shiny') || urlLower.includes('shiny'));
        const female = (typeof isFemale === 'boolean') 
            ? isFemale 
            : (labelLower.includes('female') || urlLower.includes('female'));
        const cleanLabel = cleanCardLabel(rawLabel);

        const card = document.createElement('div');
        card.className = `sprite-card${isHires ? ' hires' : ''}`;

        const indicatorsHtml = (shiny || female) ? `
            <div class="sprite-indicators">
                ${shiny ? `<span class="indicator-shiny" title="Shiny"><svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M10 2L12.5 8L18 10L12.5 12L10 18L7.5 12L2 10L7.5 8Z"/><path d="M19 15L20.2 18L23 19L20.2 20L19 23L17.8 20L15 19L17.8 18Z"/></svg></span>` : ''}
                ${female ? `<span class="indicator-female" title="Female"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="9" r="6"/><line x1="12" y1="15" x2="12" y2="23"/><line x1="8" y1="19" x2="16" y2="19"/></svg></span>` : ''}
            </div>` : '';

        const imgHtml = (isPlaceholder || !url)
            ? `<div class="placeholder">Not Available</div>`
            : `<img src="${url}" alt="${cleanLabel}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'placeholder\\'>Not Available</div>'">`;

        const prefixHtml = (shiny || female) ? `
            <span class="prefix-group">
                ${shiny ? '<span class="prefix-tag prefix-shiny" title="Shiny">[S]</span>' : ''}
                ${female ? '<span class="prefix-tag prefix-female" title="Female">[F]</span>' : ''}
            </span>` : '';

        card.innerHTML = `
            ${indicatorsHtml}
            <div class="sprite-img-container">${imgHtml}</div>
            <p class="sprite-label">
                <span class="label-inner">${prefixHtml}<span class="label-text">${cleanLabel}</span></span>
            </p>
        `;

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
                matches = list.filter(p => p.name.includes(val) || String(p.id).startsWith(val) || (p.pokemon_id && String(p.pokemon_id).startsWith(val))).slice(0, 20);
            } else if (searchType === 'item') {
                const items = Object.keys(spriteIndex.items_dict || {});
                matches = items.filter(i => i.includes(val)).slice(0, 20).map(i => ({ id: i, name: i }));
            } else if (searchType === 'type') {
                const types = spriteIndex.types_list || [];
                matches = types.filter(t => t.name.toLowerCase().includes(val) || String(t.id) === val).slice(0, 20);
            } else if (searchType === 'badge') {
                const badges = (spriteIndex.badges_list || []).map(b => ({ id: b, name: `Badge #${b}` }));
                matches = badges.filter(b => String(b.id).startsWith(val) || b.name.toLowerCase().includes(val)).slice(0, 20);
            }

            if (matches.length === 0) return;

            const container = document.getElementById('autocomplete-list');
            container.innerHTML = '';

            matches.forEach(item => {
                const div = document.createElement('div');
                const tag = item.is_form ? `#${item.pokemon_id} (form: ${item.id})` : `#${item.id}`;
                div.innerHTML = `<span><strong>${item.name}</strong></span> <span style="color:var(--muted-text); font-family:monospace;">${tag}</span>`;
                div.addEventListener('click', () => {
                    searchInput.value = (searchType === 'type') ? item.name : item.id;
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

        let entity = list.find(p => p.is_form === isForm && (String(p.id) === q || p.name === q || (p.form_id && String(p.form_id) === q)));
        if (!entity && !isForm) {
            entity = list.find(p => String(p.id) === q || p.name === q);
        }
        if (!entity && isForm) {
            entity = list.find(p => p.is_form && (p.name === q || String(p.form_id) === q || String(p.id) === q));
        }

        if (!entity) {
            resultsContainer.innerHTML = `
                <div class="sprite-group">
                    <p style="color: var(--muted-text);">No entry found in index for "${query}".</p>
                </div>`;
            return;
        }

        const candidateStems = entity.candidate_stems || [String(entity.id)];
        const getMatchingStem = (folder) => {
            const set = folderSets[folder];
            if (!set) return null;
            for (const s of candidateStems) {
                if (set.has(String(s))) return String(s);
            }
            return null;
        };
        const defaultStem = candidateStems[0] || String(entity.id);

        if (entity.is_form) {
            const formNum = entity.form_id || entity.id;
            searchId.textContent = `#${entity.pokemon_id} - ${entity.name} (Form #${formNum})`;
        } else {
            searchId.textContent = `#${entity.id} - ${entity.name}`;
        }

        // Shared helper to render a list of sprite views
        const renderViews = (grid, views, isLarge = false) => {
            views.forEach(v => {
                const stem = v.stem || getMatchingStem(v.folder);
                const hasSprite = (v.hasSprite !== undefined) ? v.hasSprite : (stem !== null);
                const isFemale = v.female || v.label.includes('Female') || (v.subpath && v.subpath.includes('female'));
                if (isFemale && !entity.has_gender_diff && !hasSprite) return;
                const isShiny = v.label.includes('Shiny') || (v.folder && v.folder.includes('shiny')) || (v.subpath && v.subpath.includes('shiny'));
                const url = hasSprite ? getSpriteUrl(`${v.folder}/${stem || defaultStem}${viewExt(v)}`) : '';
                renderCard(grid, url, v.label, !hasSprite, isLarge, isShiny, isFemale);
            });
        };

        const appendCount = (headerEl, passed, total, extraStyle = false) => {
            if (!headerEl) return;
            const count = document.createElement('span');
            count.className = 'game-subcat-count';
            if (extraStyle) count.style.marginLeft = 'auto';
            count.textContent = `${passed}/${total} available`;
            headerEl.appendChild(count);
        };

        // 1. Root Sprites (Default pixel art)
        const rootGroup = createGroup(resultsContainer, 'Root Sprites (Default)', 'sprites/pokemon/', 'category-default');
        rootGroup.dataset.category = 'default';
        const rootGrid = createSubgroup(rootGroup, 'Standard Gen 5 Pixel Art');
        renderViews(rootGrid, spriteIndex.root_views || []);

        // 2. Other Sprite Collections (Official Artwork, HOME 3D, Showdown GIFs, Dream World)
        let otherGroup = null;
        (spriteIndex.other_categories || []).forEach(cat => {
            const hasAnyInCat = (cat.views || []).some(v => getMatchingStem(v.folder) !== null);
            if (hasAnyInCat) {
                if (!otherGroup) {
                    otherGroup = createGroup(resultsContainer, 'Other Sprite Collections', 'sprites/pokemon/other/', 'category-other');
                    otherGroup.dataset.category = 'other';
                }
                const catId = `category-${cat.badge}`;
                const grid = createSubgroup(otherGroup, cat.name, cat.badge, catId);
                grid.parentElement.dataset.category = cat.badge;
                renderViews(grid, cat.views || [], cat.is_large);
            }
        });

        const introGen = entity.generation_id || 1;

        // 3. Version Sprites - Pre-categorized by Generation & Game Groups
        (spriteIndex.generations || []).forEach(gen => {
            const genNum = gen.gen_num || 1;
            const isDebuted = genNum >= introGen;

            const activeGames = (gen.games || []).filter(game => 
                isDebuted || (game.views || []).some(v => getMatchingStem(v.folder) !== null)
            );

            const activeIcons = isDebuted 
                ? (gen.icons || []) 
                : (gen.icons || []).filter(icon => getMatchingStem(icon.folder) !== null);

            if (activeGames.length === 0 && activeIcons.length === 0) return;

            const genId = `generation-${gen.id}`;
            const genGroup = createGroup(resultsContainer, gen.title, gen.id, genId);
            genGroup.dataset.generation = gen.id;

            activeGames.forEach(game => {
                const gameKey = game.id || (game.folder ? game.folder.split('/').pop() : '');
                const gameSubgroupId = gameKey ? `game-${gameKey}` : null;

                const subcatMap = new Map();
                (game.views || []).forEach(v => {
                    const isFemale = v.female || v.label.includes('Female') || (v.subpath && v.subpath.includes('female'));
                    const stem = getMatchingStem(v.folder);
                    const hasSprite = stem !== null;
                    if (isFemale && !entity.has_gender_diff && !hasSprite) return;
                    const subName = v.subcategory || 'Default';
                    if (!subcatMap.has(subName)) subcatMap.set(subName, []);
                    subcatMap.get(subName).push({ ...v, hasSprite, stem: stem || defaultStem });
                });

                if (subcatMap.size <= 1) {
                    const grid = createSubgroup(genGroup, game.name, game.folder, gameSubgroupId);
                    if (gameKey) grid.parentElement.dataset.game = gameKey;
                    const allViews = subcatMap.size === 1 ? Array.from(subcatMap.values())[0] : [];
                    if (allViews.length > 0) {
                        appendCount(grid.previousElementSibling, allViews.filter(v => v.hasSprite).length, allViews.length, true);
                    }
                    renderViews(grid, allViews);
                } else {
                    const gameSubgroup = document.createElement('div');
                    gameSubgroup.className = 'subgroup';
                    if (gameSubgroupId) {
                        gameSubgroup.id = gameSubgroupId;
                        gameSubgroup.dataset.game = gameKey;
                    }

                    const h3 = document.createElement('h3');
                    h3.className = 'subgroup-title';
                    const titleSpan = document.createElement('span');
                    titleSpan.textContent = game.name;
                    h3.appendChild(titleSpan);
                    if (gameSubgroupId) h3.appendChild(createAnchorBtn(gameSubgroupId));
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
                        appendCount(header, views.filter(v => v.hasSprite).length, views.length);
                        section.appendChild(header);

                        const grid = document.createElement('div');
                        grid.className = 'sprite-grid';
                        renderViews(grid, views);
                        section.appendChild(grid);
                        subcatsGrid.appendChild(section);
                    });

                    gameSubgroup.appendChild(subcatsGrid);
                    genGroup.appendChild(gameSubgroup);
                }
            });

            if (activeIcons.length > 0) {
                const iconId = `game-${gen.id}-icons`;
                const grid = createSubgroup(genGroup, '🏷️ Box & Party Icons', `versions/${gen.id}/icons`, iconId);
                grid.parentElement.dataset.game = `${gen.id}-icons`;
                const availableCount = activeIcons.filter(icon => getMatchingStem(icon.folder) !== null).length;
                appendCount(grid.previousElementSibling, availableCount, activeIcons.length, true);
                renderViews(grid, activeIcons);
            }
        });

        // Auto-scroll to deep-linked anchor if specified in URL (?game= or ?cat= or ?target=)
        scrollToTarget(getDeepLinkTarget());
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

        const q = String(query || '').toLowerCase().trim();
        const typesList = spriteIndex.types_list || [];

        let matchedType = null;
        if (/^\d+$/.test(q)) {
            const numId = parseInt(q, 10);
            matchedType = typesList.find(t => t.id === numId);
        } else if (q) {
            matchedType = typesList.find(t => t.name.toLowerCase() === q) ||
                          typesList.find(t => t.name.toLowerCase().includes(q));
        }

        const typeIdStr = matchedType ? String(matchedType.id) : q;
        const typeDisplayName = matchedType 
            ? (matchedType.name.charAt(0).toUpperCase() + matchedType.name.slice(1)) 
            : (q ? (q.charAt(0).toUpperCase() + q.slice(1)) : '');
        const displayTitle = matchedType ? `${typeDisplayName} (#${typeIdStr})` : q;

        searchId.textContent = `Type: ${displayTitle}`;

        const group = createGroup(resultsContainer, `Type Sprites: ${displayTitle}`, 'sprites/types/');
        let renderedCount = 0;

        for (const [gen, games] of Object.entries(spriteIndex.types_dict)) {
            for (const [game, files] of Object.entries(games)) {
                const matchFile = files.find(f => {
                    const stem = f.substring(0, f.lastIndexOf('.')) || f;
                    return stem === typeIdStr || (q && f.toLowerCase().includes(q));
                });
                if (matchFile) {
                    renderedCount++;
                    const genTitle = (spriteIndex.generations || []).find(g => g.id === gen)?.title || gen;
                    const gameTitle = game.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                    const grid = createSubgroup(group, `${genTitle} • ${gameTitle}`);
                    renderCard(grid, getSpriteUrl(`sprites/types/${gen}/${game}/${matchFile}`), `${typeDisplayName}`);
                }
            }
        }

        if (renderedCount === 0) {
            resultsContainer.innerHTML = `<div class="sprite-group"><p style="color:var(--muted-text);">No type icon found for "${query}".</p></div>`;
        }
    };

    // Helper: Dynamic search placeholder
    const updatePlaceholder = (searchType) => {
        if (searchType === 'badge') {
            const maxBadge = (spriteIndex && spriteIndex.badges_list && spriteIndex.badges_list.length)
                ? Math.max(...spriteIndex.badges_list)
                : 77;
            searchInput.placeholder = `Enter badge number (1-${maxBadge}) or leave empty for all...`;
        } else if (searchType === 'item') {
            searchInput.placeholder = 'Enter item name (e.g. poke-ball, master-ball)...';
        } else if (searchType === 'type') {
            searchInput.placeholder = 'Enter type name (e.g. grass, fire, water)...';
        } else {
            searchInput.placeholder = 'Search by name (e.g. pikachu) or ID (#25)...';
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
            updatePlaceholder(radio.value);
        });
    });

    // --- 7. Hash Routing ---
    const handleHash = () => {
        let rawHash = window.location.hash.substring(1);
        const qIdx = rawHash.indexOf('?');
        if (qIdx !== -1) {
            rawHash = rawHash.substring(0, qIdx);
        }
        const parts = rawHash.split('/').filter(Boolean);
        if (parts.length >= 1) {
            const type = parts[0];
            const query = parts[1] || '';

            const radio = document.querySelector(`input[value="${type}"]`);
            if (radio) radio.checked = true;
            updatePlaceholder(type);
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