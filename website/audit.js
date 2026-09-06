/**
 * PokéAPI Sprites Repository Audit Dashboard Client Logic
 * Handles interactive filtering, sorting, pagination, and visualizations
 * for both Modern/Artwork collections and Game Version sprites.
 */

// Global data bootstrap (inlined in standalone mode or fetched dynamically)
let AUDIT_DATA = window.AUDIT_DATA;
const CATEGORIES_DATA = window.CATEGORIES_DATA || {};
const VERSION_STATS = window.VERSION_STATS || {};
let VERSION_ISSUES = window.VERSION_ISSUES;

// State for Modern & Artwork Collections
let selectedCategory = 'ALL';
let selectedIssue = 'ALL';
let selectedEntity = 'ALL';
let selectedGender = 'ALL';
let selectedSort = 'id_asc';
let searchQuery = '';
let currentPageNum = 1;
let pageSize = 50;

// State for Game Version Sprites
let selectedVersionGen = 'ALL';
let selectedVersionGame = 'ALL';
let selectedVersionAnim = 'ALL';
let selectedVersionGender = 'ALL';
let selectedVersionSort = 'id_asc';
let versionSearchQuery = '';
let versionCurrentPageNum = 1;
let versionPageSize = 50;

// ==================== SHARED UTILITIES ====================

function toggleActivePills(pills, activeVal, dataAttr = 'cat') {
    pills.forEach(b => {
        const isActive = (b.dataset[dataAttr] === activeVal);
        b.classList.toggle('bg-zinc-900', isActive);
        b.classList.toggle('text-white', isActive);
        b.classList.toggle('dark:bg-zinc-100', isActive);
        b.classList.toggle('dark:text-zinc-900', isActive);
        b.classList.toggle('border-zinc-900', isActive);
        b.classList.toggle('dark:border-zinc-100', isActive);
        b.classList.toggle('bg-white', !isActive);
        b.classList.toggle('dark:bg-zinc-900', !isActive);
        b.classList.toggle('text-slate-700', !isActive);
        b.classList.toggle('dark:text-zinc-300', !isActive);
        b.classList.toggle('border-slate-300', !isActive);
        b.classList.toggle('dark:border-zinc-700', !isActive);
    });
}

function createCommonCells(item, queryParam) {
    const isForm = Boolean(item.is_form);
    const pId = item.pokemon_id;
    const fId = item.form_id;

    const pokemonApiUrl = `https://pokeapi.co/api/v2/pokemon/${pId}`;
    let idHtml = `<a href="${pokemonApiUrl}" target="_blank" rel="noopener noreferrer" class="text-slate-900 dark:text-zinc-100 hover:underline font-mono font-semibold" title="View Pokémon API JSON">#${pId}</a>`;
    if (isForm && fId) {
        const formApiUrl = `https://pokeapi.co/api/v2/pokemon-form/${fId}`;
        idHtml += ` <a href="${formApiUrl}" target="_blank" rel="noopener noreferrer" class="text-slate-400 dark:text-zinc-500 hover:text-purple-600 dark:hover:text-purple-400 hover:underline font-mono text-[11px]" title="View Form API JSON">(form: ${fId})</a>`;
    }

    const formBadge = isForm
        ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-sans font-medium bg-purple-100 text-purple-800 border border-purple-300 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800/70">Form</span>`
        : `<span class="px-1.5 py-0.5 rounded text-[10px] font-sans font-medium bg-zinc-100 text-zinc-800 border border-zinc-300 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700">Pokemon</span>`;

    const subRoute = (isForm && fId) ? `#/pokemon-form/${fId}` : `#/pokemon/${pId}`;
    const finderUrl = `index.html${queryParam}${subRoute}`;
    const finderLink = `<a href="${finderUrl}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center space-x-1 text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 font-sans text-xs transition" title="Open in Sprite Finder"><span class="underline underline-offset-2">Finder</span><svg class="w-3 h-3 ml-0.5 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg></a>`;

    return { idHtml, formBadge, finderLink };
}

function getPaginationEl(prefix, name) {
    if (!prefix) {
        const lower = name.charAt(0).toLowerCase() + name.slice(1);
        return document.getElementById(lower) || document.getElementById(name);
    }
    return document.getElementById(`${prefix}${name}`) || document.getElementById(`${prefix}${name.charAt(0).toLowerCase() + name.slice(1)}`);
}

function applyPagination(prefix, totalItems, curPageSize, pageNum) {
    const limit = curPageSize === 'ALL' ? (totalItems || 1) : Number(curPageSize);
    const totalPages = Math.ceil(totalItems / limit) || 1;
    const page = Math.min(Math.max(1, pageNum), totalPages);

    const firstBtn = getPaginationEl(prefix, 'FirstBtn');
    const prevBtn = getPaginationEl(prefix, 'PrevBtn');
    const nextBtn = getPaginationEl(prefix, 'NextBtn');
    const lastBtn = getPaginationEl(prefix, 'LastBtn');
    const curSpan = getPaginationEl(prefix, 'CurrentPage');
    const totSpan = getPaginationEl(prefix, 'TotalPages');
    const infoSpan = getPaginationEl(prefix, 'PaginationInfo');

    if (curSpan) curSpan.textContent = page;
    if (totSpan) totSpan.textContent = totalPages;
    if (infoSpan) infoSpan.textContent = `Showing page ${page} of ${totalPages} (${totalItems.toLocaleString()} total)`;

    if (firstBtn) firstBtn.disabled = page <= 1;
    if (prevBtn) prevBtn.disabled = page <= 1;
    if (nextBtn) nextBtn.disabled = page >= totalPages;
    if (lastBtn) lastBtn.disabled = page >= totalPages;

    const startIndex = (page - 1) * limit;
    return { page, totalPages, limit, startIndex, endIndex: startIndex + limit };
}

function bindPaginationEvents(prefix, getPage, setPage, getTotalPages, onChange) {
    getPaginationEl(prefix, 'FirstBtn')?.addEventListener('click', () => { setPage(1); onChange(); });
    getPaginationEl(prefix, 'PrevBtn')?.addEventListener('click', () => { setPage(Math.max(1, getPage() - 1)); onChange(); });
    getPaginationEl(prefix, 'NextBtn')?.addEventListener('click', () => { setPage(Math.min(getTotalPages(), getPage() + 1)); onChange(); });
    getPaginationEl(prefix, 'LastBtn')?.addEventListener('click', () => { setPage(getTotalPages()); onChange(); });
}

// ==================== ASYNCHRONOUS DATA LOADER ====================

async function loadExternalDataIfNeeded() {
    if (AUDIT_DATA && VERSION_ISSUES) return;

    try {
        const fetchPromises = [];
        if (!AUDIT_DATA) {
            fetchPromises.push(
                fetch('data/audit_data.json')
                    .then(res => res.json())
                    .then(data => { AUDIT_DATA = data; })
                    .catch(err => {
                        console.error('[AUDIT] Failed to load audit_data.json:', err);
                        AUDIT_DATA = [];
                    })
            );
        }
        if (!VERSION_ISSUES) {
            fetchPromises.push(
                fetch('data/version_audit_data.json')
                    .then(res => res.json())
                    .then(data => { VERSION_ISSUES = data; })
                    .catch(err => {
                        console.error('[AUDIT] Failed to load version_audit_data.json:', err);
                        VERSION_ISSUES = [];
                    })
            );
        }

        await Promise.all(fetchPromises);
    } finally {
        renderCategoryCards();
        renderTable();
        renderVersionGameCards();
        renderVersionTable();
    }
}

// ==================== TAB SWITCHER ====================

function switchTab(tab) {
    const isVersions = (tab === 'versions');
    const artworkBtn = document.getElementById('tabBtnArtwork');
    const versionsBtn = document.getElementById('tabBtnVersions');
    const artworkContent = document.getElementById('tabContentArtwork');
    const versionsContent = document.getElementById('tabContentVersions');
    const downloadCsvBtn = document.getElementById('downloadCsvBtn');

    if (!artworkBtn || !versionsBtn) return;

    if (isVersions) {
        artworkBtn.className = 'tab-main-btn px-4 py-2 rounded-md transition text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 flex items-center space-x-2';
        versionsBtn.className = 'tab-main-btn px-4 py-2 rounded-md transition shadow-sm bg-white dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 font-semibold flex items-center space-x-2';
        artworkContent.classList.add('hidden');
        versionsContent.classList.remove('hidden');

        downloadCsvBtn.href = 'audit_report_versions.csv';
        downloadCsvBtn.download = 'sprite_audit_versions.csv';
    } else {
        versionsBtn.className = 'tab-main-btn px-4 py-2 rounded-md transition text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 flex items-center space-x-2';
        artworkBtn.className = 'tab-main-btn px-4 py-2 rounded-md transition shadow-sm bg-white dark:bg-zinc-800 text-slate-900 dark:text-zinc-100 font-semibold flex items-center space-x-2';
        versionsContent.classList.add('hidden');
        artworkContent.classList.remove('hidden');

        downloadCsvBtn.href = 'audit_report.csv';
        downloadCsvBtn.download = 'sprite_audit_report.csv';
    }
    syncUrlState();
}

// ==================== ARTWORK TAB LOGIC ====================

function renderCategoryCards() {
    const cardsContainer = document.getElementById('category-cards');
    const tabsContainer = document.getElementById('categoryTabs');
    if (!cardsContainer || !tabsContainer) return;

    cardsContainer.innerHTML = '';
    const activeData = AUDIT_DATA || [];

    for (const [key, stats] of Object.entries(CATEGORIES_DATA)) {
        const pct = stats.total_targets > 0 ? ((stats.passed_targets / stats.total_targets) * 100).toFixed(1) : '100';
        const catIssues = activeData.filter(i => i.category === key);
        const missingCount = stats.missing_targets ?? catIssues.reduce((acc, i) => acc + (i.missing_sprites?.length || 0), 0);
        const wrongSizeCount = stats.wrong_size_targets ?? catIssues.reduce((acc, i) => acc + (i.wrong_size_sprites?.length || 0), 0);
        const corruptCount = stats.corrupt_targets ?? catIssues.reduce((acc, i) => acc + (i.corrupt_sprites?.length || 0), 0);

        const isSelected = (selectedCategory === key);
        const card = document.createElement('div');
        card.className = `cursor-pointer bg-slate-50 dark:bg-zinc-950 border ${isSelected ? 'border-zinc-900 dark:border-zinc-100 ring-1 ring-zinc-900 dark:ring-zinc-100' : 'border-slate-200 dark:border-zinc-800 hover:border-slate-400 dark:hover:border-zinc-600'} rounded-md p-3 sm:p-4 flex flex-col justify-between shadow-sm transition`;
        card.innerHTML = `
            <div>
                <div class="flex items-center justify-between">
                    <span class="font-semibold text-xs text-slate-800 dark:text-zinc-200 uppercase tracking-wider">${stats.name}</span>
                    <span class="text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded font-mono font-semibold ${stats.affected_entries === 0 ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800' : 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-800'}">
                        ${pct}%
                    </span>
                </div>
                <p class="text-[10px] sm:text-[11px] text-slate-500 dark:text-zinc-400 mt-1">${stats.description || ''}</p>
            </div>
            <div class="mt-3 sm:mt-4">
                <div class="w-full bg-slate-200 dark:bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                    <div class="bg-zinc-800 dark:bg-zinc-200 h-full rounded-full transition-all" style="width: ${pct}%"></div>
                </div>
                <div class="flex justify-between text-[10px] sm:text-[11px] text-slate-500 dark:text-zinc-400 mt-2 font-mono">
                    <span>Passed: ${stats.passed_targets.toLocaleString()}</span>
                    <span>Flawed: ${stats.flawed_targets.toLocaleString()}</span>
                    <span>Total: ${stats.total_targets.toLocaleString()}</span>
                </div>
                <div class="grid grid-cols-3 gap-1 sm:gap-1.5 mt-2 sm:mt-2.5 pt-2 border-t border-slate-200 dark:border-zinc-800/80 text-[9px] sm:text-[10px] font-mono text-center">
                    <div class="px-1 py-0.5 sm:px-1.5 sm:py-1 rounded ${missingCount > 0 ? 'bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-900/60 font-medium' : 'text-slate-400 dark:text-zinc-600 bg-slate-100/50 dark:bg-zinc-900/40'}">
                        Missing: ${missingCount.toLocaleString()}
                    </div>
                    <div class="px-1 py-0.5 sm:px-1.5 sm:py-1 rounded ${wrongSizeCount > 0 ? 'bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-900/60 font-medium' : 'text-slate-400 dark:text-zinc-600 bg-slate-100/50 dark:bg-zinc-900/40'}">
                        Wrong Size: ${wrongSizeCount.toLocaleString()}
                    </div>
                    <div class="px-1 py-0.5 sm:px-1.5 sm:py-1 rounded ${corruptCount > 0 ? 'bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-900/60 font-medium' : 'text-slate-400 dark:text-zinc-600 bg-slate-100/50 dark:bg-zinc-900/40'}">
                        Corrupt: ${corruptCount.toLocaleString()}
                    </div>
                </div>
            </div>
        `;

        card.onclick = () => {
            selectedCategory = (selectedCategory === key) ? 'ALL' : key;
            toggleActivePills(document.querySelectorAll('.cat-tab'), selectedCategory, 'cat');
            currentPageNum = 1;
            renderCategoryCards();
            renderTable();
            syncUrlState();
        };

        cardsContainer.appendChild(card);

        if (!tabsContainer.querySelector(`[data-cat="${key}"]`)) {
            const tab = document.createElement('button');
            tab.className = 'cat-tab px-2.5 sm:px-3 py-1 rounded-md text-[11px] sm:text-xs font-medium bg-white dark:bg-zinc-900 text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 hover:text-slate-900 dark:hover:text-white border border-slate-300 dark:border-zinc-700 transition';
            tab.dataset.cat = key;
            tab.textContent = stats.name;
            tab.onclick = () => {
                selectedCategory = key;
                toggleActivePills(document.querySelectorAll('.cat-tab'), key, 'cat');
                currentPageNum = 1;
                renderCategoryCards();
                renderTable();
                syncUrlState();
            };
            tabsContainer.appendChild(tab);
        }
    }

    const allTab = tabsContainer.querySelector('[data-cat="ALL"]');
    if (allTab) {
        allTab.onclick = () => {
            selectedCategory = 'ALL';
            toggleActivePills(document.querySelectorAll('.cat-tab'), 'ALL', 'cat');
            currentPageNum = 1;
            renderCategoryCards();
            renderTable();
            syncUrlState();
        };
    }

    toggleActivePills(tabsContainer.querySelectorAll('.cat-tab'), selectedCategory, 'cat');
}

function getFilteredData() {
    if (!AUDIT_DATA) return [];

    let result = AUDIT_DATA.filter(item => {
        if (selectedCategory !== 'ALL' && item.category !== selectedCategory) return false;
        if (selectedIssue === 'missing' && (!item.missing_sprites || item.missing_sprites.length === 0)) return false;
        if (selectedIssue === 'wrong_size' && (!item.wrong_size_sprites || item.wrong_size_sprites.length === 0)) return false;
        if (selectedIssue === 'corrupt' && (!item.corrupt_sprites || item.corrupt_sprites.length === 0)) return false;
        if (selectedIssue === 'multiple' && (item.issues_count < 2)) return false;

        if (selectedEntity === 'pokemon' && item.is_form !== 0) return false;
        if (selectedEntity === 'form' && item.is_form !== 1) return false;

        if (selectedGender === 'dimorphic' && (!item.has_gender_differences || item.has_gender_differences === 0)) return false;
        if (selectedGender === 'standard' && item.has_gender_differences === 1) return false;

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            const matchName = item.identifier && item.identifier.toLowerCase().includes(q);
            const matchId = String(item.pokemon_id).includes(q) || (item.form_id && String(item.form_id).includes(q)) || (item.species_id && String(item.species_id).includes(q));
            const matchSummary = item.issue_summary && item.issue_summary.toLowerCase().includes(q);
            const matchCategory = item.category_name && item.category_name.toLowerCase().includes(q);
            if (!matchName && !matchId && !matchSummary && !matchCategory) return false;
        }

        return true;
    });

    result.sort((a, b) => {
        const idA = a.is_form && a.form_id ? Number(a.form_id) : Number(a.pokemon_id);
        const idB = b.is_form && b.form_id ? Number(b.form_id) : Number(b.pokemon_id);
        if (selectedSort === 'id_asc') return idA - idB;
        if (selectedSort === 'id_desc') return idB - idA;
        if (selectedSort === 'name_asc') return a.identifier.localeCompare(b.identifier);
        if (selectedSort === 'name_desc') return b.identifier.localeCompare(a.identifier);
        if (selectedSort === 'issues_desc') return b.issues_count - a.issues_count;
        return 0;
    });

    return result;
}

function renderTable() {
    const tbody = document.getElementById('issuesTableBody');
    if (!tbody) return;

    if (!AUDIT_DATA) {
        tbody.innerHTML = `<tr><td colspan="6" class="py-16 text-center text-slate-500 dark:text-zinc-500 font-sans text-xs">Loading artwork issues data...</td></tr>`;
        return;
    }

    const filtered = getFilteredData();
    const isFiltered = (selectedCategory !== 'ALL' || selectedIssue !== 'ALL' || selectedEntity !== 'ALL' || selectedGender !== 'ALL' || searchQuery !== '' || selectedSort !== 'id_asc');
    document.getElementById('activeFiltersBadge')?.classList.toggle('hidden', !isFiltered);

    let countLabel = `Showing ${filtered.length.toLocaleString()} affected entries`;
    if (selectedIssue === 'corrupt') {
        const totalFiles = filtered.reduce((acc, item) => acc + (item.corrupt_sprites?.length || 0), 0);
        countLabel += ` (${totalFiles.toLocaleString()} corrupt files)`;
    } else if (selectedIssue === 'missing') {
        const totalFiles = filtered.reduce((acc, item) => acc + (item.missing_sprites?.length || 0), 0);
        countLabel += ` (${totalFiles.toLocaleString()} missing files)`;
    } else if (selectedIssue === 'wrong_size') {
        const totalFiles = filtered.reduce((acc, item) => acc + (item.wrong_size_sprites?.length || 0), 0);
        countLabel += ` (${totalFiles.toLocaleString()} wrong size files)`;
    } else {
        const totalFiles = filtered.reduce((acc, item) => acc + (item.issues_count || 0), 0);
        countLabel += ` (${totalFiles.toLocaleString()} flawed files)`;
    }
    const resultsCountEl = document.getElementById('resultsCount');
    if (resultsCountEl) resultsCountEl.textContent = countLabel;

    const { page, startIndex, endIndex } = applyPagination('', filtered.length, pageSize, currentPageNum);
    currentPageNum = page;
    const pageData = filtered.slice(startIndex, endIndex);

    tbody.innerHTML = '';
    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="py-16 text-center text-slate-500 dark:text-zinc-500 font-sans text-xs">No issues found matching the selected filters.</td></tr>`;
        return;
    }

    pageData.forEach(item => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-100/60 dark:hover:bg-zinc-900/60 transition';

        let breakdownHtml = '<div class="flex flex-wrap gap-1.5 items-center">';
        if (item.missing_sprites?.length > 0) {
            breakdownHtml += `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-rose-100 text-rose-800 border border-rose-300 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/80">Missing (${item.missing_sprites.length}): ${item.missing_sprites.join(', ')}</span>`;
        }
        if (item.wrong_size_sprites?.length > 0) {
            breakdownHtml += `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/80">Wrong Size: ${item.wrong_size_sprites.join(', ')}</span>`;
        }
        if (item.corrupt_sprites?.length > 0) {
            breakdownHtml += `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-purple-100 text-purple-800 border border-purple-300 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800/80">Corrupt: ${item.corrupt_sprites.join(', ')}</span>`;
        }
        breakdownHtml += '</div>';

        const catParam = item.category ? `?cat=${encodeURIComponent(item.category)}` : '';
        const { idHtml, formBadge, finderLink } = createCommonCells(item, catParam);

        tr.innerHTML = `
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 font-sans font-medium text-slate-700 dark:text-zinc-300 text-[11px] sm:text-xs">${item.category_name}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 font-mono text-[11px] sm:text-xs">${idHtml}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 text-slate-900 dark:text-zinc-100 font-mono font-medium text-[11px] sm:text-xs">${item.identifier}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 text-center whitespace-nowrap">${formBadge}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 text-center whitespace-nowrap font-sans text-[11px] sm:text-xs">${finderLink}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 font-sans text-[11px] sm:text-xs">${breakdownHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ==================== VERSION SPRITES TAB LOGIC ====================

function populateVersionGameFilter() {
    const gameFilterSelect = document.getElementById('versionGameFilter');
    if (!gameFilterSelect) return;
    const currentVal = selectedVersionGame;
    gameFilterSelect.innerHTML = '<option value="ALL">All Games & Icons</option>';
    for (const [key, stats] of Object.entries(VERSION_STATS)) {
        if (selectedVersionGen !== 'ALL' && String(stats.gen_num) !== String(selectedVersionGen)) {
            continue;
        }
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = `[${stats.gen_name}] ${stats.game_name}`;
        gameFilterSelect.appendChild(opt);
    }
    if (Array.from(gameFilterSelect.options).some(o => o.value === currentVal)) {
        gameFilterSelect.value = currentVal;
    } else {
        selectedVersionGame = 'ALL';
        gameFilterSelect.value = 'ALL';
    }
}

function renderVersionGameCards() {
    const cardsContainer = document.getElementById('version-game-cards');
    const gameFilterSelect = document.getElementById('versionGameFilter');
    if (!cardsContainer) return;

    cardsContainer.innerHTML = '';
    if (gameFilterSelect && gameFilterSelect.value !== selectedVersionGame) {
        gameFilterSelect.value = selectedVersionGame;
    }

    for (const [key, stats] of Object.entries(VERSION_STATS)) {
        if (selectedVersionGen !== 'ALL' && String(stats.gen_num) !== String(selectedVersionGen)) {
            continue;
        }

        const pct = stats.completion_rate !== undefined ? stats.completion_rate.toFixed(1) : '0.0';
        const isSelected = (selectedVersionGame === key);
        const card = document.createElement('div');
        card.className = `cursor-pointer bg-slate-50 dark:bg-zinc-950 border ${isSelected ? 'border-zinc-900 dark:border-zinc-100 ring-1 ring-zinc-900 dark:ring-zinc-100' : 'border-slate-200 dark:border-zinc-800 hover:border-slate-400 dark:hover:border-zinc-600'} rounded-md p-3 sm:p-3.5 flex flex-col justify-between shadow-sm transition`;

        card.innerHTML = `
            <div>
                <div class="flex items-start justify-between gap-1.5 sm:gap-2">
                    <div class="min-w-0">
                        <span class="text-[9px] sm:text-[10px] uppercase tracking-wider font-semibold text-slate-500 dark:text-zinc-400 block truncate">${stats.gen_name}</span>
                        <h3 class="font-semibold text-xs text-slate-900 dark:text-zinc-100 tracking-tight mt-0.5 truncate">${stats.game_name}</h3>
                    </div>
                    <span class="text-[10px] sm:text-[11px] px-1.5 sm:px-2 py-0.5 rounded font-mono font-semibold shrink-0 ${stats.completion_rate >= 90 ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800' : stats.completion_rate > 0 ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800' : 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-800'}">
                        ${pct}%
                    </span>
                </div>
            </div>
            <div class="mt-2.5 sm:mt-3">
                <div class="w-full bg-slate-200 dark:bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                    <div class="bg-zinc-800 dark:bg-zinc-200 h-full rounded-full transition-all" style="width: ${pct}%"></div>
                </div>
                <div class="flex justify-between text-[10px] sm:text-[11px] text-slate-500 dark:text-zinc-400 mt-1.5 sm:mt-2 font-mono">
                    <span>Passed: ${stats.passed_targets.toLocaleString()}</span>
                    <span>Missing: ${stats.missing_targets.toLocaleString()}</span>
                </div>
                <div class="flex justify-between items-center text-[9px] sm:text-[10px] text-slate-400 dark:text-zinc-500 mt-1 font-mono pt-1.5 border-t border-slate-200/80 dark:border-zinc-800/80">
                    <span>Total: ${stats.total_targets.toLocaleString()}</span>
                    <span>Affected: ${stats.affected_entries.toLocaleString()}</span>
                </div>
            </div>
        `;

        card.onclick = () => {
            selectedVersionGame = (selectedVersionGame === key) ? 'ALL' : key;
            if (gameFilterSelect) gameFilterSelect.value = selectedVersionGame;
            versionCurrentPageNum = 1;
            renderVersionGameCards();
            renderVersionTable();
            syncUrlState();
        };

        cardsContainer.appendChild(card);
    }
}

function getFilteredVersionData() {
    if (!VERSION_ISSUES) return [];

    let result = [];
    for (const rawItem of VERSION_ISSUES) {
        if (selectedVersionGen !== 'ALL' && String(rawItem.gen_num) !== String(selectedVersionGen)) continue;
        if (selectedVersionGame !== 'ALL' && rawItem.game_id !== selectedVersionGame) continue;

        if (selectedVersionGender === 'dimorphic' && (!rawItem.has_gender_differences || rawItem.has_gender_differences === 0)) continue;
        if (selectedVersionGender === 'standard' && rawItem.has_gender_differences === 1) continue;

        let missingSprites = rawItem.missing_sprites || [];
        let missingCount = rawItem.missing_count || missingSprites.length;
        let missingStr = rawItem.missing_str || missingSprites.join(', ');

        if (selectedVersionAnim === 'exclude_animated') {
            missingSprites = missingSprites.filter(s => !s.toLowerCase().includes('anim'));
            if (missingSprites.length === 0) continue;
            missingCount = missingSprites.length;
            missingStr = missingSprites.join(', ');
        } else if (selectedVersionAnim === 'animated_only') {
            missingSprites = missingSprites.filter(s => s.toLowerCase().includes('anim'));
            if (missingSprites.length === 0) continue;
            missingCount = missingSprites.length;
            missingStr = missingSprites.join(', ');
        }

        if (versionSearchQuery) {
            const q = versionSearchQuery.toLowerCase();
            const matchName = rawItem.identifier && rawItem.identifier.toLowerCase().includes(q);
            const matchId = String(rawItem.pokemon_id).includes(q);
            const matchGame = rawItem.game_name && rawItem.game_name.toLowerCase().includes(q);
            const matchMissing = missingStr && missingStr.toLowerCase().includes(q);
            if (!matchName && !matchId && !matchGame && !matchMissing) continue;
        }

        result.push({
            ...rawItem,
            missing_sprites: missingSprites,
            missing_count: missingCount,
            missing_str: missingStr
        });
    }

    result.sort((a, b) => {
        if (selectedVersionSort === 'id_asc') return Number(a.pokemon_id) - Number(b.pokemon_id);
        if (selectedVersionSort === 'id_desc') return Number(b.pokemon_id) - Number(a.pokemon_id);
        if (selectedVersionSort === 'name_asc') return a.identifier.localeCompare(b.identifier);
        if (selectedVersionSort === 'name_desc') return b.identifier.localeCompare(a.identifier);
        if (selectedVersionSort === 'missing_desc') return b.missing_count - a.missing_count;
        return 0;
    });

    return result;
}

function renderVersionTable() {
    const tbody = document.getElementById('versionTableBody');
    if (!tbody) return;

    if (!VERSION_ISSUES) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-16 text-center text-slate-500 dark:text-zinc-500 font-sans text-xs">Loading version sprite data...</td></tr>`;
        return;
    }

    const filtered = getFilteredVersionData();
    const isFiltered = (selectedVersionGen !== 'ALL' || selectedVersionGame !== 'ALL' || selectedVersionAnim !== 'ALL' || selectedVersionGender !== 'ALL' || versionSearchQuery !== '' || selectedVersionSort !== 'id_asc');
    document.getElementById('activeVersionFiltersBadge')?.classList.toggle('hidden', !isFiltered);

    const totalMissingSprites = filtered.reduce((acc, item) => acc + (item.missing_count || 0), 0);
    const versionResultsCountEl = document.getElementById('versionResultsCount');
    if (versionResultsCountEl) {
        versionResultsCountEl.textContent = `Showing ${filtered.length.toLocaleString()} affected entries (${totalMissingSprites.toLocaleString()} missing sprites)`;
    }

    const { page, startIndex, endIndex } = applyPagination('version', filtered.length, versionPageSize, versionCurrentPageNum);
    versionCurrentPageNum = page;
    const pageData = filtered.slice(startIndex, endIndex);

    tbody.innerHTML = '';
    if (pageData.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-16 text-center text-slate-500 dark:text-zinc-500 font-sans text-xs">No version sprite issues matching the selected filters.</td></tr>`;
        return;
    }

    pageData.forEach(item => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-100/60 dark:hover:bg-zinc-900/60 transition';

        const breakdownHtml = `
            <div class="flex flex-wrap gap-1.5 items-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-rose-100 text-rose-800 border border-rose-300 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/80">
                    Missing (${item.missing_count}/${item.total_expected}): ${item.missing_str}
                </span>
            </div>
        `;

        const gameParam = item.game_id ? `?game=${encodeURIComponent(item.game_id)}` : '';
        const { idHtml, formBadge, finderLink } = createCommonCells(item, gameParam);

        tr.innerHTML = `
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 font-sans font-medium text-slate-500 dark:text-zinc-400 text-center whitespace-nowrap text-[11px] sm:text-xs">${item.gen_name}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 font-sans font-medium text-slate-800 dark:text-zinc-200 text-[11px] sm:text-xs">${item.game_name}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 font-mono text-[11px] sm:text-xs">${idHtml}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 text-slate-900 dark:text-zinc-100 font-mono font-medium text-[11px] sm:text-xs">${item.identifier}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 text-center whitespace-nowrap">${formBadge}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 text-center whitespace-nowrap font-sans text-[11px] sm:text-xs">${finderLink}</td>
            <td class="py-2 px-2.5 sm:py-2.5 sm:px-4 font-sans text-[11px] sm:text-xs">${breakdownHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ==================== EVENT LISTENERS SETUP ====================

function setupListeners() {
    // Tab Switcher Buttons
    document.getElementById('tabBtnArtwork')?.addEventListener('click', () => switchTab('artwork'));
    document.getElementById('tabBtnVersions')?.addEventListener('click', () => switchTab('versions'));

    // Artwork Filters
    document.getElementById('issueFilter')?.addEventListener('change', (e) => {
        selectedIssue = e.target.value;
        currentPageNum = 1;
        renderTable();
        syncUrlState();
    });

    const searchInput = document.getElementById('searchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    let debounceTimer;
    searchInput?.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            searchQuery = e.target.value.trim();
            clearSearchBtn?.classList.toggle('hidden', !searchQuery);
            currentPageNum = 1;
            renderTable();
            syncUrlState();
        }, 200);
    });

    clearSearchBtn?.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        searchQuery = '';
        clearSearchBtn.classList.add('hidden');
        currentPageNum = 1;
        renderTable();
        syncUrlState();
    });

    document.getElementById('entityFilter')?.addEventListener('change', (e) => {
        selectedEntity = e.target.value;
        currentPageNum = 1;
        renderTable();
        syncUrlState();
    });
    document.getElementById('genderFilter')?.addEventListener('change', (e) => {
        selectedGender = e.target.value;
        currentPageNum = 1;
        renderTable();
        syncUrlState();
    });
    document.getElementById('sortFilter')?.addEventListener('change', (e) => {
        selectedSort = e.target.value;
        currentPageNum = 1;
        renderTable();
        syncUrlState();
    });
    document.getElementById('pageSizeSelect')?.addEventListener('change', (e) => {
        pageSize = e.target.value === 'ALL' ? 'ALL' : Number(e.target.value);
        currentPageNum = 1;
        renderTable();
    });
    document.getElementById('resetFiltersBtn')?.addEventListener('click', () => {
        selectedCategory = 'ALL';
        selectedIssue = 'ALL';
        selectedEntity = 'ALL';
        selectedGender = 'ALL';
        selectedSort = 'id_asc';
        searchQuery = '';
        pageSize = 50;

        if (searchInput) searchInput.value = '';
        clearSearchBtn?.classList.add('hidden');
        const issueFilterEl = document.getElementById('issueFilter');
        if (issueFilterEl) issueFilterEl.value = 'ALL';
        document.getElementById('entityFilter').value = 'ALL';
        document.getElementById('genderFilter').value = 'ALL';
        document.getElementById('sortFilter').value = 'id_asc';
        document.getElementById('pageSizeSelect').value = '50';
        toggleActivePills(document.querySelectorAll('.cat-tab'), 'ALL', 'cat');

        currentPageNum = 1;
        renderCategoryCards();
        renderTable();
        syncUrlState();
    });

    bindPaginationEvents('', () => currentPageNum, (v) => { currentPageNum = v; },
        () => Math.ceil(getFilteredData().length / (pageSize === 'ALL' ? (getFilteredData().length || 1) : Number(pageSize))) || 1,
        renderTable
    );

    // Version Sprites Filters
    document.querySelectorAll('.v-gen-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            selectedVersionGen = btn.dataset.gen;
            toggleActivePills(document.querySelectorAll('.v-gen-pill'), selectedVersionGen, 'gen');
            populateVersionGameFilter();
            versionCurrentPageNum = 1;
            renderVersionGameCards();
            renderVersionTable();
            syncUrlState();
        });
    });

    const versionSearchInput = document.getElementById('versionSearchInput');
    const clearVersionSearchBtn = document.getElementById('clearVersionSearchBtn');
    let vDebounceTimer;
    versionSearchInput?.addEventListener('input', (e) => {
        clearTimeout(vDebounceTimer);
        vDebounceTimer = setTimeout(() => {
            versionSearchQuery = e.target.value.trim();
            clearVersionSearchBtn?.classList.toggle('hidden', !versionSearchQuery);
            versionCurrentPageNum = 1;
            renderVersionTable();
            syncUrlState();
        }, 200);
    });

    clearVersionSearchBtn?.addEventListener('click', () => {
        if (versionSearchInput) versionSearchInput.value = '';
        versionSearchQuery = '';
        clearVersionSearchBtn.classList.add('hidden');
        versionCurrentPageNum = 1;
        renderVersionTable();
        syncUrlState();
    });

    document.getElementById('versionGameFilter')?.addEventListener('change', (e) => {
        selectedVersionGame = e.target.value;
        versionCurrentPageNum = 1;
        renderVersionGameCards();
        renderVersionTable();
        syncUrlState();
    });
    document.getElementById('versionAnimFilter')?.addEventListener('change', (e) => {
        selectedVersionAnim = e.target.value;
        versionCurrentPageNum = 1;
        renderVersionTable();
        syncUrlState();
    });
    document.getElementById('versionGenderFilter')?.addEventListener('change', (e) => {
        selectedVersionGender = e.target.value;
        versionCurrentPageNum = 1;
        renderVersionTable();
        syncUrlState();
    });
    document.getElementById('versionSortFilter')?.addEventListener('change', (e) => {
        selectedVersionSort = e.target.value;
        versionCurrentPageNum = 1;
        renderVersionTable();
        syncUrlState();
    });
    document.getElementById('versionPageSizeSelect')?.addEventListener('change', (e) => {
        versionPageSize = e.target.value === 'ALL' ? 'ALL' : Number(e.target.value);
        versionCurrentPageNum = 1;
        renderVersionTable();
    });
    document.getElementById('resetVersionFiltersBtn')?.addEventListener('click', () => {
        selectedVersionGen = 'ALL';
        selectedVersionGame = 'ALL';
        selectedVersionAnim = 'ALL';
        selectedVersionGender = 'ALL';
        selectedVersionSort = 'id_asc';
        versionSearchQuery = '';
        versionPageSize = 50;

        if (versionSearchInput) versionSearchInput.value = '';
        clearVersionSearchBtn?.classList.add('hidden');
        document.getElementById('versionGameFilter').value = 'ALL';
        const vaf = document.getElementById('versionAnimFilter');
        if (vaf) vaf.value = 'ALL';
        document.getElementById('versionGenderFilter').value = 'ALL';
        document.getElementById('versionSortFilter').value = 'id_asc';
        document.getElementById('versionPageSizeSelect').value = '50';
        populateVersionGameFilter();
        toggleActivePills(document.querySelectorAll('.v-gen-pill'), 'ALL', 'gen');

        versionCurrentPageNum = 1;
        renderVersionGameCards();
        renderVersionTable();
        syncUrlState();
    });

    bindPaginationEvents('version', () => versionCurrentPageNum, (v) => { versionCurrentPageNum = v; },
        () => Math.ceil(getFilteredVersionData().length / (versionPageSize === 'ALL' ? (getFilteredVersionData().length || 1) : Number(versionPageSize))) || 1,
        renderVersionTable
    );

    // Theme Toggle
    const updateThemeUI = (isDark) => {
        const icon = document.getElementById('themeToggleIcon');
        const text = document.getElementById('themeToggleText');
        if (icon) icon.textContent = isDark ? '🌙' : '☀️';
        if (text) text.textContent = isDark ? 'Dark' : 'Light';
    };

    document.getElementById('themeToggleBtn')?.addEventListener('click', () => {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        updateThemeUI(isDark);
    });

    updateThemeUI(document.documentElement.classList.contains('dark'));
}

// ==================== URL STATE SYNCHRONIZATION ====================

function syncUrlState() {
    const params = new URLSearchParams();
    const isVersions = !document.getElementById('tabContentVersions')?.classList.contains('hidden');

    if (isVersions) {
        if (selectedVersionGen !== 'ALL') params.set('gen', selectedVersionGen);
        if (selectedVersionGame !== 'ALL') params.set('game', selectedVersionGame);
        if (selectedVersionAnim !== 'ALL') params.set('v_anim', selectedVersionAnim);
        if (selectedVersionGender !== 'ALL') params.set('v_gender', selectedVersionGender);
        if (selectedVersionSort !== 'id_asc') params.set('v_sort', selectedVersionSort);
        if (versionSearchQuery) params.set('q', versionSearchQuery);
    } else {
        if (selectedCategory !== 'ALL') params.set('cat', selectedCategory);
        if (selectedIssue !== 'ALL') params.set('issue', selectedIssue);
        if (selectedEntity !== 'ALL') params.set('entity', selectedEntity);
        if (selectedGender !== 'ALL') params.set('gender', selectedGender);
        if (selectedSort !== 'id_asc') params.set('sort', selectedSort);
        if (searchQuery) params.set('q', searchQuery);
    }

    const qs = params.toString() ? `?${params.toString()}` : '';
    const hash = isVersions ? '#/versions' : '#/artwork';
    const newUrl = `${window.location.pathname}${qs}${hash}`;
    window.history.replaceState(null, '', newUrl);
}

// Deep linking parameters & hash routes
function initRouting() {
    const params = new URLSearchParams(window.location.search);
    const gen = params.get('gen');
    const game = params.get('game');
    const anim = params.get('v_anim') || params.get('anim');
    const q = params.get('q');
    const cat = params.get('cat');
    const issue = params.get('issue');
    const entity = params.get('entity');
    const gender = params.get('gender') || params.get('v_gender');
    const sort = params.get('sort') || params.get('v_sort');

    const isVersionTab = window.location.hash.includes('version');

    if (anim) {
        selectedVersionAnim = anim;
        const vaf = document.getElementById('versionAnimFilter');
        if (vaf) vaf.value = anim;
    }

    if (cat) {
        selectedCategory = cat;
        toggleActivePills(document.querySelectorAll('.cat-tab'), cat, 'cat');
    }
    if (issue) {
        selectedIssue = issue;
        const ifEl = document.getElementById('issueFilter');
        if (ifEl) ifEl.value = issue;
    }
    if (entity) {
        selectedEntity = entity;
        const ef = document.getElementById('entityFilter');
        if (ef) ef.value = entity;
    }
    if (gender) {
        if (isVersionTab) {
            selectedVersionGender = gender;
            const vgf = document.getElementById('versionGenderFilter');
            if (vgf) vgf.value = gender;
        } else {
            selectedGender = gender;
            const gf = document.getElementById('genderFilter');
            if (gf) gf.value = gender;
        }
    }
    if (sort) {
        if (isVersionTab) {
            selectedVersionSort = sort;
            const vsf = document.getElementById('versionSortFilter');
            if (vsf) vsf.value = sort;
        } else {
            selectedSort = sort;
            const sf = document.getElementById('sortFilter');
            if (sf) sf.value = sort;
        }
    }

    if (gen) {
        selectedVersionGen = gen;
        toggleActivePills(document.querySelectorAll('.v-gen-pill'), gen, 'gen');
        populateVersionGameFilter();
    }
    if (game) {
        selectedVersionGame = game;
        const gf = document.getElementById('versionGameFilter');
        if (gf) gf.value = game;
    }
    if (q) {
        if (isVersionTab) {
            versionSearchQuery = q;
            const vi = document.getElementById('versionSearchInput');
            if (vi) vi.value = q;
            document.getElementById('clearVersionSearchBtn')?.classList.remove('hidden');
        } else {
            searchQuery = q;
            const si = document.getElementById('searchInput');
            if (si) si.value = q;
            document.getElementById('clearSearchBtn')?.classList.remove('hidden');
        }
    }

    const initHash = () => {
        const hash = window.location.hash;
        if (hash.includes('version')) {
            switchTab('versions');
        } else {
            switchTab('artwork');
        }
    };
    window.addEventListener('hashchange', initHash);
    initHash();
}

// Initialize on DOM ready
function initApp() {
    setupListeners();
    populateVersionGameFilter();
    initRouting();
    renderCategoryCards();
    renderTable();
    renderVersionGameCards();
    renderVersionTable();
    loadExternalDataIfNeeded();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
