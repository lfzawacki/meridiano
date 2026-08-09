function toggleDateFilters() {
    var content = document.getElementById('date-filter-content');
    var icon = document.querySelector('.date-filter-toggle .toggle-icon');
    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        icon.textContent = '-';
    } else {
        content.style.display = 'none';
        icon.textContent = '+';
    }
}

async function toggleCollectionsMenu(event, menuId) {
    event.stopPropagation();
    const targetMenu = document.getElementById(menuId);

    // Hide all other open menus
    document.querySelectorAll('.collections-menu').forEach(menu => {
        if (menu.id !== menuId) {
            menu.style.display = 'none';
        }
    });

    const isVisible = targetMenu.style.display === 'block';
    if (isVisible) {
        targetMenu.style.display = 'none';
        return;
    }

    targetMenu.style.display = 'block';
    const contentDiv = targetMenu.querySelector('.collections-menu-content');

    if (contentDiv.dataset.loaded) {
        return; // Already loaded, just show it
    }

    const articleId = menuId.split('-').pop();
    contentDiv.innerHTML = 'Loading...';

    try {
        const response = await fetch(`/article/${articleId}/collections_status`);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const data = await response.json();

        if (data.status === 'ok') {
            let html = '';
            if (data.collections && data.collections.length > 0) {
                let collectionEntriesHtml = '';
                data.collections.forEach(c => {
                    const buttonHtml = c.contains
                        ? `<button class="btn btn-clear btn-remove-from-collection" data-collection-id="${c.id}" data-article-id="${articleId}" title="Remove from ${c.name}"><i class="fas fa-minus"></i></button>`
                        : `<button class="btn btn-filter btn-add-to-collection" data-collection-id="${c.id}" data-article-id="${articleId}" title="Add to ${c.name}"><i class="fas fa-plus"></i></button>`;
                    collectionEntriesHtml += `<div class="collection-entry" data-collection-id="${c.id}"><span>${c.name}</span><span class="collection-action-button">${buttonHtml}</span></div>`;
                });
                html += `<div class="collections-list-container">${collectionEntriesHtml}</div>`;
                html += `<div class="collections-menu-footer"><a href="/collections"><i class="fas fa-cog"></i> Manage Collections</a></div>`;
            } else {
                html = `<div>No collections yet. <a href="/collections">Create one</a>.</div>`;
            }
            contentDiv.innerHTML = html;
            contentDiv.dataset.loaded = 'true';
        } else {
            throw new Error(data.message || 'Failed to load collections.');
        }
    } catch (error) {
        console.error('Error fetching collections:', error);
        contentDiv.innerHTML = '<div class="error-message">Error loading.</div>';
    }
}

function applyTheme(pref) {
    var resolved = pref;
    if (!pref || pref === 'system') {
        resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', resolved);
}

function initThemeSelector() {
    var select = document.getElementById('theme-select');
    var saved = localStorage.getItem('theme') || 'system';
    if (select) {
        select.value = saved;
        select.addEventListener('change', function () {
            localStorage.setItem('theme', select.value);
            applyTheme(select.value);
        });
    }
    // Follow OS changes while in "system" mode
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
        if ((localStorage.getItem('theme') || 'system') === 'system') {
            applyTheme('system');
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    initThemeSelector();

    // Initialize date filters if dates are present
    const startDateEl = document.getElementById('start_date');
    const endDateEl = document.getElementById('end_date');
    if (startDateEl && endDateEl) {
        if (startDateEl.value || endDateEl.value) {
            toggleDateFilters();
        }
    }

    // Global click handler for closing menus and handling collection actions
    document.addEventListener('click', async function(event) {
        let target = event.target;
        let action = null;
        let addClass = '.btn-add-to-collection';
        let removeClass = '.btn-remove-from-collection';

        if (target.parentElement.matches(addClass) || target.parentElement.matches(removeClass)) {
          target = target.parentElement;
        }

        if (target.matches(addClass)) action = 'add';
        if (target.matches(removeClass)) action = 'remove';

        if (action) {
            event.preventDefault();
            const collectionId = target.dataset.collectionId;
            const articleId = target.dataset.articleId;
            const url = `/collection/${collectionId}/${action}_article`;

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                    body: JSON.stringify({ article_id: articleId })
                });
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                const data = await response.json();

                if (data.status === 'ok') {
                    const buttonContainer = target.closest('.collection-action-button');
                    if (buttonContainer) {
                        const collectionEntry = buttonContainer.closest('.collection-entry');
                        const collectionName = collectionEntry ? collectionEntry.querySelector('span:first-child').textContent : '';

                        const newButton = action === 'add'
                            ? `<button class="btn btn-clear btn-remove-from-collection" data-collection-id="${collectionId}" data-article-id="${articleId}" title="Remove from ${collectionName}"><i class="fas fa-minus"></i></button>`
                            : `<button class="btn btn-filter btn-add-to-collection" data-collection-id="${collectionId}" data-article-id="${articleId}" title="Add to ${collectionName}"><i class="fas fa-plus"></i></button>`;
                        buttonContainer.innerHTML = newButton;
                    }
                } else {
                    throw new Error(data.message || 'Action failed.');
                }
            } catch (error) {
                console.error(`Error with ${action} action:`, error);
                alert(`Failed to ${action} article.`);
            }
        } else if (!target.closest('.collections-menu')) {
            // Close all menus if click is outside
            document.querySelectorAll('.collections-menu').forEach(menu => {
                menu.style.display = 'none';
            });
        }
    });
});
