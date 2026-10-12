(() => {
  const dataElement = document.getElementById("root-data");
  const roots = dataElement ? JSON.parse(dataElement.textContent) : [];
  const explorer = document.getElementById("explorer");
  const rootList = document.getElementById("root-list");
  const tree = document.getElementById("word-tree");
  const title = document.getElementById("family-title");
  const origin = document.getElementById("family-origin");
  const rootSource = document.getElementById("root-source");
  const details = document.getElementById("word-details");
  const search = document.getElementById("root-search");
  const results = document.getElementById("search-results");
  const rootCount = document.getElementById("root-count");
  let selectedRoot = roots[0]?.id;
  let selectedWord = null;
  let searchTimer;
  let searchController;

  const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);

  function renderRoots() {
    rootList.replaceChildren();
    rootCount.textContent = `${roots.length} roots`;
    roots.forEach((root) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "root-choice";
      button.setAttribute("aria-pressed", String(root.id === selectedRoot));
      button.innerHTML = `<strong>${escapeHTML(root.label)}</strong><small>“${escapeHTML(root.gloss)}” · Latin</small>`;
      button.addEventListener("click", () => selectRoot(root.id));
      rootList.append(button);
    });
  }

  function renderDetails(word) {
    if (!word) {
      details.innerHTML = '<div class="detail-empty"><span class="detail-glyph" aria-hidden="true">↗</span><p class="side-label">WORD NOTES</p><h3>Choose a word</h3><p>Its meaning, formation, and place in the family will appear here.</p></div>';
      return;
    }
    const pronunciation = word.pronunciation
      ? `<span>Pronunciation <strong>${escapeHTML(word.pronunciation)}</strong></span>`
      : '<span class="detail-unavailable">Pronunciation not verified</span>';
    const syllables = word.syllables
      ? `<span>Syllables <strong>${escapeHTML(word.syllables)}</strong></span>`
      : '<span class="detail-unavailable">Syllable division not verified</span>';
    details.innerHTML = `<article class="detail-content">
      <div class="detail-topline"><div><p class="side-label">WORD NOTES</p><h3 class="detail-word">${escapeHTML(word.word)}</h3><p class="detail-part">${escapeHTML(word.part_of_speech)}</p></div><span class="detail-tag">${escapeHTML(word.relationship)}</span></div>
      <div class="pronunciation-row">${pronunciation}${syllables}</div>
      <section class="detail-section"><h4>MEANING</h4><p>${escapeHTML(word.meaning)}</p></section>
      <section class="detail-section"><h4>ETYMOLOGY & ROOT CONNECTION</h4><p>${escapeHTML(word.etymology)}</p></section>
      <section class="detail-section"><h4>IN A SENTENCE</h4><p class="example-text">${escapeHTML(word.example)}</p></section>
      <div class="detail-sources"><a href="${escapeHTML(word.dictionary_url)}" target="_blank" rel="noopener noreferrer">Dictionary entry ↗</a><a href="${escapeHTML(word.etymology_url)}" target="_blank" rel="noopener noreferrer">Etymology source ↗</a></div>
    </article>`;
  }

  function selectWord(word) {
    selectedWord = word.id;
    tree.querySelectorAll(".word-choice").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.wordId === word.id));
    });
    renderDetails(word);
  }

  function renderTree(root) {
    tree.replaceChildren();
    const rootNode = document.createElement("div");
    rootNode.className = "tree-root";
    rootNode.innerHTML = `<strong>${escapeHTML(root.label)}</strong><small>Latin · “${escapeHTML(root.gloss)}”</small>`;
    const groups = document.createElement("ul");
    groups.className = "branch-list";
    root.groups.forEach((group, index) => {
      const item = document.createElement("li");
      item.className = "branch-item";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "branch-toggle";
      toggle.setAttribute("aria-expanded", "true");
      toggle.setAttribute("aria-controls", `branch-${root.id}-${group.id}-${index}`);
      toggle.innerHTML = `<span class="branch-caret" aria-hidden="true">⌄</span><span>${escapeHTML(group.label)}</span>`;
      const words = document.createElement("div");
      words.className = "branch-words";
      words.id = `branch-${root.id}-${group.id}-${index}`;
      group.words.forEach((word) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "word-choice";
        button.dataset.wordId = word.id;
        button.setAttribute("aria-pressed", String(word.id === selectedWord));
        button.innerHTML = `<span class="word-dot" aria-hidden="true"></span><strong>${escapeHTML(word.word)}</strong>`;
        button.addEventListener("click", () => selectWord(word));
        words.append(button);
      });
      toggle.addEventListener("click", () => {
        const expanded = toggle.getAttribute("aria-expanded") === "true";
        toggle.setAttribute("aria-expanded", String(!expanded));
        words.classList.toggle("is-collapsed", expanded);
      });
      item.append(toggle, words);
      groups.append(item);
    });
    tree.append(rootNode, groups);
  }

  function selectRoot(rootId) {
    const root = roots.find((item) => item.id === rootId);
    if (!root) return;
    selectedRoot = rootId;
    selectedWord = null;
    title.textContent = root.label;
    origin.textContent = `${root.origin} · “${root.gloss}”`;
    rootSource.href = root.source || "";
    rootSource.hidden = !root.source;
    renderRoots();
    renderTree(root);
    renderDetails(null);
  }

  function showResults(items, query) {
    results.replaceChildren();
    if (!query.trim()) { results.hidden = true; return; }
    const heading = document.createElement("div");
    heading.className = "result-heading";
    heading.textContent = "SEARCH RESULTS";
    results.append(heading);
    items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "result-item";
      button.innerHTML = `<span>${escapeHTML(item.label)}</span><small>${escapeHTML(item.meta)}</small>`;
      button.addEventListener("click", () => {
        if (item.kind === "root") {
          selectRoot(item.id);
        } else {
          selectRoot(item.root_id);
          const matchingWord = roots.find((root) => root.id === item.root_id)?.groups.flatMap((group) => group.words).find((word) => word.id === item.id);
          if (matchingWord) selectWord(matchingWord);
        }
        results.hidden = true;
        search.value = "";
      });
      results.append(button);
    });
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "empty-results";
      empty.textContent = "No matches in this curated collection. Try ‘script’, ‘describe’, or ‘carry’.";
      results.append(empty);
    }
    results.hidden = false;
  }

  async function searchWords(query) {
    if (!query.trim()) { results.hidden = true; return; }
    if (searchController) searchController.abort();
    searchController = new AbortController();
    try {
      const url = new URL(explorer.dataset.searchUrl, window.location.origin);
      url.searchParams.set("q", query.trim());
      const response = await fetch(url, { headers: { Accept: "application/json" }, signal: searchController.signal });
      if (!response.ok) throw new Error("Search request failed");
      const data = await response.json();
      showResults(data.results || [], query);
    } catch (error) {
      if (error.name !== "AbortError") {
        showResults([], query);
        const note = results.querySelector(".empty-results");
        if (note) note.textContent = "Search is unavailable right now. Press Enter to try the server-rendered search.";
      }
    }
  }

  search.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => searchWords(search.value), 160);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== search && !["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
      event.preventDefault();
      search.focus();
    }
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { results.hidden = true; search.value = ""; }
  });
  document.addEventListener("click", (event) => {
    if (!results.contains(event.target) && !search.contains(event.target)) results.hidden = true;
  });

  const initialRoot = explorer.dataset.selectedRoot || selectedRoot;
  const initialWord = explorer.dataset.selectedWord;
  selectRoot(initialRoot);
  if (initialWord) {
    const match = roots.find((root) => root.id === initialRoot)?.groups.flatMap((group) => group.words).find((word) => word.id === initialWord);
    if (match) selectWord(match);
  }
  if (search.value) searchWords(search.value);
})();
