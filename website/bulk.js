const state = {
    index: null,
    folders: new Map(),
    selected: null,
    expanded: new Set(),
    filter: ''
};

const $ = (id) => document.getElementById(id);
const tree = $('fileTree');
const grid = $('bulkGrid');

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const dark = theme === 'dark';
    $('themeToggleIcon').textContent = dark ? '🌙' : '☀️';
    $('themeToggleText').textContent = dark ? 'Dark' : 'Light';
}

$('themeToggle').addEventListener('click', () => {
    const current = localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(current === 'dark' ? 'light' : 'dark');
});
applyTheme(localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

function numericSort(a, b) {
    const aMatch = /^(\d+)(?:-(.*))?$/.exec(a);
    const bMatch = /^(\d+)(?:-(.*))?$/.exec(b);
    const aNumber = aMatch ? Number(aMatch[1]) : Infinity;
    const bNumber = bMatch ? Number(bMatch[1]) : Infinity;
    const aHigh = aNumber >= 10000;
    const bHigh = bNumber >= 10000;
    if (aHigh !== bHigh) return aHigh ? 1 : -1;
    if (aNumber !== Infinity || bNumber !== Infinity) {
        if (aNumber !== bNumber) return aNumber - bNumber;
        const aForm = aMatch?.[2] || '';
        const bForm = bMatch?.[2] || '';
        if (aForm !== bForm) {
            if (!aForm) return -1;
            if (!bForm) return 1;
            return aForm.localeCompare(bForm, undefined, { numeric: true, sensitivity: 'base' });
        }
    }
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
}

function getExtension(folder) {
    return state.index.folder_exts?.[folder] || (folder.includes('official-artwork') ? '.svg' : '.png');
}

function spriteUrl(path) {
    const local = location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.protocol === 'file:';
    if (local) return `../${path}`;

    if (location.hostname.endsWith('github.io')) {
        const user = location.hostname.split('.')[0];
        const repo = location.pathname.split('/')[1] || 'sprites';
        const branch = new URLSearchParams(location.search).get('branch') || state.index.branch || 'master';
        if (user.toLowerCase() !== 'pokeapi') {
            return `https://raw.githubusercontent.com/${user}/${repo}/${branch}/${path}`;
        }
    }

    const branch = state.index.branch || 'master';
    return `https://raw.githubusercontent.com/PokeAPI/sprites/${branch}/${path}`;
}

function handleImageError(image, path) {
    if (!image.dataset.fallback && image.src.includes('raw.githubusercontent.com') && !image.src.includes('/PokeAPI/sprites/')) {
        image.dataset.fallback = '1';
        image.src = `https://raw.githubusercontent.com/PokeAPI/sprites/${state.index.branch || 'master'}/${path}`;
        return;
    }

    image.hidden = true;
    image.nextElementSibling.classList.add('is-visible');
}

function createFolderMap() {
    const folders = state.index.folder_files || {};
    Object.entries(folders).forEach(([path, files]) => {
        state.folders.set(path, { path, files: files.map(String).sort(numericSort) });
    });
    for (const path of ['sprites/badges', 'sprites/items', 'sprites/types']) {
        if (!state.folders.has(path)) state.folders.set(path, { path, files: [] });
    }
    state.index.badges_list?.forEach((id) => state.folders.get('sprites/badges')?.files.push(String(id)));
    Object.values(state.index.items_dict || {}).flat().forEach((path) => {
        const parts = `sprites/items/${path}`.split('/');
        const folder = parts.slice(0, -1).join('/');
        const file = parts.at(-1).replace(/\.[^.]+$/, '');
        if (!state.folders.has(folder)) state.folders.set(folder, { path: folder, files: [] });
        state.folders.get(folder).files.push(file);
    });
    Object.entries(state.index.types_dict || {}).forEach(([generation, games]) => {
        Object.entries(games).forEach(([game, files]) => {
            const folder = `sprites/types/${generation}/${game}`;
            state.folders.set(folder, { path: folder, files: files.map((path) => path.replace(/\.[^.]+$/, '')) });
        });
    });
    state.folders.forEach((folder) => folder.files = [...new Set(folder.files)].sort(numericSort));
}

function treeNodes() {
    const root = { name: 'sprites', path: 'sprites', children: new Map(), folder: null };
    state.folders.forEach((folder) => {
        const parts = folder.path.split('/').filter(Boolean);
        let node = root;
        parts.forEach((part, index) => {
            if (!node.children.has(part)) node.children.set(part, { name: part, path: parts.slice(0, index + 1).join('/'), children: new Map(), folder: null });
            node = node.children.get(part);
        });
        node.folder = folder;
    });
    return root;
}

function matches(node) {
    if (!state.filter) return true;
    const query = state.filter.toLowerCase();
    return node.path.toLowerCase().includes(query) || node.folder?.files.some((file) => file.toLowerCase().includes(query));
}

function renderTree() {
    tree.replaceChildren();
    const root = treeNodes();
    const renderNode = (node, parent, depth) => {
        const children = [...node.children.values()].filter(matches).sort((a, b) => numericSort(a.name, b.name));
        if (node !== root && !matches(node) && !children.length) return;
        const row = document.createElement('button');
        row.type = 'button';
        row.className = `tree-row${state.selected === node.path ? ' selected' : ''}`;
        row.style.setProperty('--depth', depth);
        const hasChildren = children.length > 0;
        const open = state.expanded.has(node.path) || Boolean(state.filter);
        row.innerHTML = `<span class="tree-chevron">${hasChildren ? (open ? '▾' : '▸') : ''}</span><span class="tree-folder">${node === root ? '▣' : '▱'}</span><span class="tree-name">${node.name}</span>${node.folder ? `<span class="tree-count">${node.folder.files.length}</span>` : ''}`;
        row.addEventListener('click', () => {
            if (hasChildren) {
                if (open) state.expanded.delete(node.path); else state.expanded.add(node.path);
                renderTree();
            }
            if (node.folder) selectFolder(node.folder);
        });
        parent.appendChild(row);
        if (open) children.forEach((child) => renderNode(child, parent, depth + 1));
    };
    renderNode(root, tree, 0);
    $('treeCount').textContent = `${state.folders.size} folders`;
}

function expandToFolder(folderPath) {
    const parts = folderPath.split('/');
    for (let index = 1; index <= parts.length; index += 1) {
        state.expanded.add(parts.slice(0, index).join('/'));
    }
}

function setFolderUrl(folderPath, replace = false) {
    const url = new URL(window.location.href);
    url.searchParams.set('folder', folderPath);
    const method = replace ? 'replaceState' : 'pushState';
    window.history[method]({ folder: folderPath }, '', url);
}

function selectFolder(folder, updateUrl = true) {
    state.selected = folder.path;
    expandToFolder(folder.path);
    if (updateUrl) setFolderUrl(folder.path);
    $('bulkState').hidden = true;
    $('bulkResults').hidden = false;
    $('selectedFolder').textContent = `${folder.path}/`;
    $('selectedCount').textContent = `${folder.files.length.toLocaleString()} files`;
    grid.replaceChildren();
    const fragment = document.createDocumentFragment();
    folder.files.forEach((stem) => {
        const card = document.createElement('a');
        const path = `${folder.path}/${stem}${getExtension(folder.path)}`;
        card.className = 'bulk-sprite-card';
        card.href = spriteUrl(path);
        card.target = '_blank';
        card.rel = 'noopener';
        card.title = `Open ${path}`;
        card.innerHTML = `<span class="bulk-image"><img src="${spriteUrl(path)}" alt="${stem}" loading="lazy"><span class="placeholder">Not Available</span></span><span class="bulk-file">${stem}</span>`;
        const image = card.querySelector('img');
        const placeholder = card.querySelector('.placeholder');
        image.addEventListener('error', () => handleImageError(image, path));
        fragment.appendChild(card);
    });
    grid.appendChild(fragment);
    renderTree();
}

window.addEventListener('popstate', () => {
    const folderPath = new URLSearchParams(window.location.search).get('folder');
    const folder = folderPath ? state.folders.get(folderPath) : null;
    if (folder) selectFolder(folder, false);
});

$('bulkSearch').addEventListener('input', (event) => {
    state.filter = event.target.value.trim();
    renderTree();
});
$('expandAll').addEventListener('click', () => {
    const expanding = $('expandAll').textContent === 'Expand tree';
    state.expanded = new Set();
    if (expanding) {
        state.expanded.add('sprites');
        state.folders.forEach((folder) => {
            const parts = folder.path.split('/');
            for (let index = 1; index <= parts.length; index += 1) {
                state.expanded.add(parts.slice(0, index).join('/'));
            }
        });
    }
    $('expandAll').textContent = expanding ? 'Collapse tree' : 'Expand tree';
    renderTree();
});

(async () => {
    try {
        const response = await fetch('data/sprite_index.json');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        state.index = await response.json();
        createFolderMap();
        renderTree();
        const folderPath = new URLSearchParams(window.location.search).get('folder');
        const folder = folderPath ? state.folders.get(folderPath) : null;
        if (folder) selectFolder(folder, false);
        else if (folderPath) window.history.replaceState({}, '', window.location.pathname);
    } catch (error) {
        console.error(error);
        $('treeCount').textContent = 'Unavailable';
        $('bulkState').innerHTML = '<div class="empty-icon">!</div><h2>Index unavailable</h2><p>Run the sprite index builder before opening the bulk browser.</p>';
    }
})();
