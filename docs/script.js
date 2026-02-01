const grid = document.getElementById("grid");
const statCount = document.getElementById("stat-count");
const statRange = document.getElementById("stat-range");
const filters = document.getElementById("filters");
const filterChips = document.getElementById("filterChips");
const categorySelect = document.getElementById("categorySelect");
const locationSelect = document.getElementById("locationSelect");
const keywordSearch = document.getElementById("keywordSearch");
const searchClear = document.getElementById("searchClear");
const pagination = document.getElementById("pagination");

const CATEGORY_ORDER = [
  "All",
  "Doctors",
  "Nurses & Midwives",
  "Pharmacists",
  "Medical Laboratory Scientists",
  "Dentists",
  "Public Health",
  "Healthcare Management",
  "Allied Health",
  "Others",
];

let activeCategory = "All";
let activeLocation = "All locations";
let keywordQuery = "";
let allJobs = [];
let currentPage = 1;
const PAGE_SIZE = 12;

function safeText(text) {
  return (text || "").toString().trim();
}

function getOrdinal(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function formatDate(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return dateStr;

  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const day = d.getDate();
  const month = months[d.getMonth()];
  const year = d.getFullYear();

  return `${day} ${month} ${year}`;
}

function isExpired(deadline) {
  if (!deadline) return false;
  const deadlineDate = new Date(deadline);
  if (Number.isNaN(deadlineDate.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return deadlineDate < today;
}

function addList(target, items, maxItems = 4) {
  if (!Array.isArray(items) || items.length === 0) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = "Not specified";
    target.appendChild(p);
    return;
  }
  const ul = document.createElement("ul");
  const displayItems = items.slice(0, maxItems);
  displayItems.forEach(item => {
    const text = safeText(item);
    if (text) {
      const li = document.createElement("li");
      li.textContent = text;
      ul.appendChild(li);
    }
  });
  target.appendChild(ul);

  if (items.length > maxItems) {
    const more = document.createElement("p");
    more.className = "empty";
    more.textContent = `+ ${items.length - maxItems} more — click Apply Now for full details`;
    target.appendChild(more);
  }
}

// ===== DETAIL PANEL FUNCTIONALITY =====
const detailPanel = document.getElementById("detailPanel");
const detailOverlay = document.getElementById("detailOverlay");
const detailCloseBtn = document.getElementById("detailCloseBtn");
const detailBackBtn = document.getElementById("detailBackBtn");
let currentJob = null;
let scrollY = 0;

// Generate a URL-friendly slug from job
function getJobSlug(job) {
  if (job.apply_url) {
    const match = job.apply_url.match(/[^/]+$/);
    if (match) return match[0];
  }
  return (job.job_title || "job")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .substring(0, 60);
}

// Find job by slug
function findJobBySlug(slug) {
  if (!slug) return null;
  return allJobs.find(j => {
    const jobSlug = getJobSlug(j);
    return jobSlug === slug || (j.apply_url && j.apply_url.includes(slug));
  });
}

// Populate list (show ALL items, no truncation)
function populateDetailList(container, items) {
  container.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "Not specified";
    container.appendChild(li);
    return;
  }
  items.forEach(item => {
    const text = (item || "").toString().trim();
    if (text) {
      const li = document.createElement("li");
      li.textContent = text;
      container.appendChild(li);
    }
  });
}

// Open detail panel
function openDetail(job) {
  if (!job) return;
  currentJob = job;
  scrollY = window.scrollY || 0;

  // Update URL without reload
  const slug = getJobSlug(job);
  const url = new URL(window.location);
  url.searchParams.set("job", slug);
  history.pushState({ job: slug }, "", url.toString());

  // Populate header
  document.getElementById("detailTitle").textContent = job.job_title || "Untitled Role";
  document.getElementById("detailMeta").textContent =
    [job.company, job.location].filter(Boolean).join(" • ") || "Company not listed";
  document.getElementById("detailSalary").textContent = job.salary || "Salary not listed";

  // Source
  const sourceMap = {
    medlocum: "MedLocum Jobs",
    jobsinnigeria: "Jobs In Nigeria",
    medicalworldnigeria: "Medical World Nigeria",
  };
  document.getElementById("detailSource").textContent =
    sourceMap[job._source] || job._source || "External Source";

  // Tags
  const tagsContainer = document.getElementById("detailTags");
  tagsContainer.innerHTML = "";

  if (job.date_posted) {
    const tag = document.createElement("div");
    tag.className = "tag";
    tag.textContent = `Posted ${formatDate(job.date_posted)}`;
    tagsContainer.appendChild(tag);
  }

  const category = normalizeCategory(job);
  if (category && category !== "Others") {
    const tag = document.createElement("div");
    tag.className = "tag category";
    tag.textContent = category;
    tagsContainer.appendChild(tag);
  }

  if (job.job_type) {
    const tag = document.createElement("div");
    tag.className = "tag job-type";
    tag.textContent = job.job_type;
    tagsContainer.appendChild(tag);
  }

  if (job.deadline) {
    const tag = document.createElement("div");
    tag.className = "tag deadline";
    tag.textContent = `Closes ${formatDate(job.deadline)}`;
    tagsContainer.appendChild(tag);
  }

  // Content sections - show ALL items
  populateDetailList(document.getElementById("detailRequirements"), job.requirements);
  populateDetailList(document.getElementById("detailResponsibilities"), job.responsibilities);

  // Hide responsibilities section if empty
  const respSection = document.getElementById("detailRespSection");
  respSection.style.display = (job.responsibilities && job.responsibilities.length > 0) ? "block" : "none";

  // CTA button
  const cta = document.getElementById("detailCTA");
  if (job.apply_url) {
    cta.href = job.apply_url;
    cta.textContent = "View Original Posting →";
    cta.classList.remove("disabled");
  } else {
    cta.href = "#";
    cta.textContent = "No application link available";
    cta.classList.add("disabled");
  }

  // Show panel
  detailPanel.classList.remove("hidden");
  detailPanel.classList.add("visible");
  detailPanel.setAttribute("aria-hidden", "false");
  detailOverlay.classList.add("visible");
  document.body.classList.add("panel-open");
  document.body.style.top = `-${scrollY}px`;

  // Scroll panel to top
  detailPanel.scrollTop = 0;
}

// Close detail panel
function closeDetail() {
  currentJob = null;

  // Update URL - remove job param
  const url = new URL(window.location);
  url.searchParams.delete("job");
  const newUrl = url.searchParams.toString() ? `${url.pathname}?${url.searchParams}` : url.pathname;
  history.pushState({}, "", newUrl);

  // Hide panel
  detailPanel.classList.add("hidden");
  detailPanel.classList.remove("visible");
  detailPanel.setAttribute("aria-hidden", "true");
  detailOverlay.classList.remove("visible");
  document.body.classList.remove("panel-open");
  document.body.style.top = "";
  window.scrollTo(0, scrollY);
}

// Check URL for job param on load
function checkUrlForJob() {
  const params = new URLSearchParams(window.location.search);
  const jobSlug = params.get("job");
  if (jobSlug) {
    const job = findJobBySlug(jobSlug);
    if (job) {
      openDetail(job);
    }
  }
}

// Event listeners for closing
detailCloseBtn.addEventListener("click", closeDetail);
detailBackBtn.addEventListener("click", closeDetail);
detailOverlay.addEventListener("click", closeDetail);

// Keyboard: Escape to close
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && currentJob) {
    closeDetail();
  }
});

// Browser back/forward navigation
window.addEventListener("popstate", () => {
  const params = new URLSearchParams(window.location.search);
  const jobSlug = params.get("job");
  if (jobSlug) {
    const job = findJobBySlug(jobSlug);
    if (job) {
      openDetail(job);
    } else {
      closeDetail();
    }
  } else {
    closeDetail();
  }
});

// ===== NEWSLETTER DISMISS FUNCTIONALITY =====
const newsletterSection = document.getElementById("newsletterSection");
const newsletterDismiss = document.getElementById("newsletterDismiss");
const NEWSLETTER_STORAGE_KEY = "jobbermed_newsletter_dismissed";
const DISMISS_DURATION_DAYS = 14;

function isNewsletterDismissed() {
  const dismissed = localStorage.getItem(NEWSLETTER_STORAGE_KEY);
  if (!dismissed) return false;

  const dismissedDate = new Date(parseInt(dismissed, 10));
  const now = new Date();
  const daysSinceDismissed = (now - dismissedDate) / (1000 * 60 * 60 * 24);

  return daysSinceDismissed < DISMISS_DURATION_DAYS;
}

function dismissNewsletter() {
  localStorage.setItem(NEWSLETTER_STORAGE_KEY, Date.now().toString());
  newsletterSection.classList.add("hidden");
}

function initNewsletter() {
  if (!newsletterSection || !newsletterDismiss) return;

  if (isNewsletterDismissed()) {
    newsletterSection.classList.add("hidden");
  }

  newsletterDismiss.addEventListener("click", dismissNewsletter);
}

initNewsletter();

function getCategoryFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const cat = safeText(params.get("category"));
  return cat || "All";
}

function setCategoryInUrl(category) {
  const url = new URL(window.location.href);
  if (!category || category === "All") {
    url.searchParams.delete("category");
  } else {
    url.searchParams.set("category", category);
  }
  window.history.replaceState({}, "", url.toString());
}

function setKeywordInUrl(keyword) {
  const url = new URL(window.location.href);
  if (!keyword) {
    url.searchParams.delete("q");
  } else {
    url.searchParams.set("q", keyword);
  }
  window.history.replaceState({}, "", url.toString());
}

function updateSearchClearVisibility() {
  if (!searchClear) return;
  searchClear.classList.toggle("visible", Boolean(keywordSearch.value.trim()));
}

function normalizeCategory(job) {
  const title = (typeof job === "object"
    ? safeText(job.job_title)
    : safeText(job)
  ).toLowerCase();

  if (!title) return "Others";

  if (title.includes("medical laboratory") || (title.includes("laboratory") && title.includes("scientist"))) {
    return "Medical Laboratory Scientists";
  }
  if (title.includes("dentist") || title.includes("dental")) return "Dentists";
  if (title.includes("pharmacist") || title.includes("pharmacy")) return "Pharmacists";
  if (title.includes("nurse") || title.includes("nursing") || title.includes("midwife") || title.includes("midwifery") || title.includes("matron")) {
    return "Nurses & Midwives";
  }
  if (title.includes("doctor") || title.includes("physician") || title.includes("medical officer") ||
      title.includes("obstetrician") || title.includes("gynaecologist") || title.includes("oncology") ||
      title.includes("general practitioner")) {
    return "Doctors";
  }
  if (title.includes("public health") || title.includes("program officer") || title.includes("programme officer") ||
      title.includes("epidemiology") || title.includes("surveillance") || title.includes("health systems") ||
      title.includes("health security") || title.includes("project officer")) {
    return "Public Health";
  }
  if (title.includes("director") || title.includes("manager") || title.includes("coordinator") ||
      title.includes("management") || title.includes("provost") || title.includes("hse") ||
      title.includes("inventory") || title.includes("warehouse") || title.includes("quality officer")) {
    return "Healthcare Management";
  }
  if (title.includes("physiotherapist") || title.includes("optometrist") || title.includes("therapist") ||
      title.includes("radiographer") || title.includes("dietitian") || title.includes("nutritionist")) {
    return "Allied Health";
  }
  return "Others";
}

const NIGERIAN_STATES = [
  "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
  "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
  "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi",
  "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo",
  "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
];

const CITY_TO_STATE = {
  "abuja": "FCT",
  "fct": "FCT",
  "lagos": "Lagos",
  "kano": "Kano",
  "ibadan": "Oyo",
  "port harcourt": "Rivers",
  "benin": "Edo",
  "benin city": "Edo",
  "kaduna": "Kaduna",
  "enugu": "Enugu",
  "jos": "Plateau",
  "ilorin": "Kwara",
  "sokoto": "Sokoto",
  "calabar": "Cross River",
  "warri": "Delta",
  "owerri": "Imo",
  "uyo": "Akwa Ibom",
  "abeokuta": "Ogun",
  "maiduguri": "Borno",
  "zaria": "Kaduna",
  "aba": "Abia",
  "ogbomoso": "Oyo",
  "onitsha": "Anambra",
  "akure": "Ondo",
  "bauchi": "Bauchi",
  "yola": "Adamawa",
  "gombe": "Gombe",
  "lafia": "Nasarawa",
  "lokoja": "Kogi",
  "minna": "Niger",
  "oshogbo": "Osun",
  "asaba": "Delta",
  "awka": "Anambra",
  "birnin kebbi": "Kebbi",
  "damaturu": "Yobe",
  "dutse": "Jigawa",
  "ado ekiti": "Ekiti",
  "gusau": "Zamfara",
  "jalingo": "Taraba",
  "katsina": "Katsina",
  "umuahia": "Abia",
  "yenagoa": "Bayelsa",
  "mowe": "Ogun",
  "keffi": "Nasarawa"
};

const COUNTRY_ALIASES = [
  ["uk", "UK"],
  ["united kingdom", "UK"],
  ["zambia", "Zambia"],
  ["ghana", "Ghana"],
  ["kenya", "Kenya"],
  ["uganda", "Uganda"],
  ["tanzania", "Tanzania"],
  ["rwanda", "Rwanda"],
  ["south africa", "South Africa"],
  ["united states", "United States"],
  ["usa", "United States"],
  ["canada", "Canada"],
  ["germany", "Germany"],
  ["france", "France"],
  ["netherlands", "Netherlands"],
  ["switzerland", "Switzerland"],
  ["sweden", "Sweden"],
  ["norway", "Norway"],
  ["denmark", "Denmark"],
  ["australia", "Australia"],
];

function getLocationBuckets(location) {
  const raw = safeText(location);
  if (!raw) return [];
  const lower = raw.toLowerCase();
  const hasWord = (word) => new RegExp(`\\b${word}\\b`, "i").test(raw);
  const buckets = new Set();
  const isNigeria = hasWord("nigeria") || NIGERIAN_STATES.some(s => hasWord(s.toLowerCase()));

  if (isNigeria) {
    NIGERIAN_STATES.forEach(state => {
      if (hasWord(state.toLowerCase())) {
        buckets.add(`${state} State`);
      }
    });

    Object.keys(CITY_TO_STATE).forEach(city => {
      if (hasWord(city)) {
        const state = CITY_TO_STATE[city];
        if (state === "FCT") {
          buckets.add("FCT");
        } else {
          buckets.add(`${state} State`);
        }
      }
    });

    if (buckets.size === 0) {
      return [];
    }
    return Array.from(buckets);
  }

  for (const [needle, label] of COUNTRY_ALIASES) {
    if (lower.includes(needle)) return [label];
  }

  const parts = raw.split(",").map(p => p.trim()).filter(Boolean);
  if (parts.length > 1) {
    return [parts[parts.length - 1]];
  }
  return [raw];
}

function updateStats(list) {
  statCount.querySelector("strong").textContent = String(list.length);
  const dates = list.map(j => j.date_posted).filter(Boolean).sort();
  if (dates.length) {
    const oldest = formatDate(dates[0]);
    const newest = formatDate(dates[dates.length - 1]);
    statRange.querySelector("strong").textContent = `${oldest} to ${newest}`;
  } else {
    statRange.querySelector("strong").textContent = "Unknown";
  }
}

function renderFilters() {
  const activeJobs = allJobs.filter(j => !isExpired(j.deadline));
  const counts = {};
  CATEGORY_ORDER.forEach(c => { counts[c] = 0; });
  activeJobs.forEach(j => {
    const cat = normalizeCategory(j);
    counts[cat] = (counts[cat] || 0) + 1;
    counts.All += 1;
  });

  const validSet = new Set(CATEGORY_ORDER);
  if (!validSet.has(activeCategory)) activeCategory = "All";

  // Desktop chips
  filterChips.innerHTML = "";
  CATEGORY_ORDER.forEach(cat => {
    const btn = document.createElement("button");
    const count = cat === "All" ? activeJobs.length : (counts[cat] || 0);
    btn.className = `filter-btn${cat === activeCategory ? " active" : ""}`;
    btn.type = "button";
    btn.textContent = `${cat} (${count})`;
    btn.setAttribute("aria-pressed", cat === activeCategory ? "true" : "false");
    btn.addEventListener("click", () => {
      activeCategory = cat;
      currentPage = 1;
      setCategoryInUrl(activeCategory);
      renderJobs();
      renderFilters();
    });
    filterChips.appendChild(btn);
  });

  // Mobile dropdown
  categorySelect.innerHTML = "";
  CATEGORY_ORDER.forEach(cat => {
    const opt = document.createElement("option");
    const count = cat === "All" ? activeJobs.length : (counts[cat] || 0);
    opt.value = cat;
    opt.textContent = `${cat} (${count})`;
    categorySelect.appendChild(opt);
  });
  categorySelect.value = activeCategory;

  if (!categorySelect.dataset.bound) {
    categorySelect.addEventListener("change", () => {
      activeCategory = categorySelect.value || "All";
      currentPage = 1;
      setCategoryInUrl(activeCategory);
      renderJobs();
      renderFilters();
    });
    categorySelect.dataset.bound = "1";
  }

  // Location dropdown
  const locationCounts = {};
  activeJobs.forEach(j => {
    const buckets = j._locationBuckets || [];
    buckets.forEach(b => {
      locationCounts[b] = (locationCounts[b] || 0) + 1;
    });
  });
  const locationOptions = ["All locations", ...Object.keys(locationCounts).sort()];

  if (!locationOptions.includes(activeLocation)) {
    activeLocation = "All locations";
  }

  locationSelect.innerHTML = "";
  locationOptions.forEach(loc => {
    const opt = document.createElement("option");
    opt.value = loc;
    opt.textContent = loc === "All locations" ? "All locations" : `${loc} (${locationCounts[loc] || 0})`;
    locationSelect.appendChild(opt);
  });
  locationSelect.value = activeLocation;

  if (!locationSelect.dataset.bound) {
    locationSelect.addEventListener("change", () => {
      activeLocation = locationSelect.value || "All locations";
      currentPage = 1;
      renderJobs();
      renderFilters();
    });
    locationSelect.dataset.bound = "1";
  }

  if (!keywordSearch.dataset.bound) {
    keywordSearch.addEventListener("input", () => {
      keywordQuery = keywordSearch.value.trim().toLowerCase();
      currentPage = 1;
      setKeywordInUrl(keywordQuery);
      updateSearchClearVisibility();
      renderJobs();
    });
    keywordSearch.dataset.bound = "1";
  }

  if (!searchClear.dataset.bound) {
    searchClear.addEventListener("click", () => {
      keywordQuery = "";
      keywordSearch.value = "";
      currentPage = 1;
      setKeywordInUrl("");
      updateSearchClearVisibility();
      renderJobs();
    });
    searchClear.dataset.bound = "1";
  }
}

function renderPagination(totalItems) {
  pagination.innerHTML = "";
  const totalPages = Math.ceil(totalItems / PAGE_SIZE);
  if (totalPages <= 1) return;

  const prevBtn = document.createElement("button");
  prevBtn.className = "pagination-btn";
  prevBtn.textContent = "Prev";
  prevBtn.disabled = currentPage <= 1;
  prevBtn.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage -= 1;
      renderJobs();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  const status = document.createElement("span");
  status.className = "pagination-status";
  status.textContent = `${currentPage} / ${totalPages}`;

  const nextBtn = document.createElement("button");
  nextBtn.className = "pagination-btn";
  nextBtn.textContent = "Next";
  nextBtn.disabled = currentPage >= totalPages;
  nextBtn.addEventListener("click", () => {
    if (currentPage < totalPages) {
      currentPage += 1;
      renderJobs();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  pagination.appendChild(prevBtn);
  pagination.appendChild(status);
  pagination.appendChild(nextBtn);
}

function renderJobs() {
  let list = activeCategory === "All"
    ? allJobs
    : allJobs.filter(j => normalizeCategory(j) === activeCategory);
  list = activeLocation === "All locations"
    ? list
    : list.filter(j => (j._locationBuckets || []).includes(activeLocation));
  if (keywordQuery) {
    list = list.filter(j => {
      const haystack = [
        j.job_title,
        j.company,
        j.location,
        j.job_type,
        j.job_category,
      ].map(safeText).join(" ").toLowerCase();
      return haystack.includes(keywordQuery);
    });
  }
  list = list.filter(j => !isExpired(j.deadline));
  grid.innerHTML = "";
  updateStats(list);
  renderPagination(list.length);

  const start = (currentPage - 1) * PAGE_SIZE;
  const end = start + PAGE_SIZE;
  const pageItems = list.slice(start, end);

  pageItems.forEach(j => {
    const card = document.createElement("article");
    card.className = "card clickable";

    // Make card clickable to open detail panel
    card.addEventListener("click", (e) => {
      if (e.target.closest(".apply-btn")) return;
      openDetail(j);
    });

    // Title
    const title = document.createElement("h3");
    title.className = "title";
    title.textContent = safeText(j.job_title) || "Untitled role";

    // Meta: Company • Location
    const meta = document.createElement("div");
    meta.className = "meta";
    const company = safeText(j.company);
    const location = safeText(j.location);
    meta.textContent = [company, location].filter(Boolean).join(" • ") || "Company not listed";

    // Tags (minimal: job type + deadline only)
    const tags = document.createElement("div");
    tags.className = "tags";

    if (j.date_posted) {
      const postedTag = document.createElement("div");
      postedTag.className = "tag posted";
      postedTag.textContent = `Posted ${formatDate(j.date_posted)}`;
      tags.appendChild(postedTag);
    }

    if (j.job_type && safeText(j.job_type)) {
      const typeTag = document.createElement("div");
      typeTag.className = "tag job-type";
      typeTag.textContent = safeText(j.job_type);
      tags.appendChild(typeTag);
    }

    if (j.deadline && safeText(j.deadline)) {
      const deadlineTag = document.createElement("div");
      deadlineTag.className = "tag deadline";
      deadlineTag.textContent = `Closes ${formatDate(j.deadline)}`;
      tags.appendChild(deadlineTag);
    }

    // Salary
    let salary;
    if (safeText(j.salary)) {
      salary = document.createElement("div");
      salary.className = "salary";
      salary.textContent = safeText(j.salary);
    }

    // Action buttons row
    const actions = document.createElement("div");
    actions.className = "card-actions";

    // View Details button
    const viewBtn = document.createElement("button");
    viewBtn.className = "view-btn";
    viewBtn.textContent = "View Details";
    viewBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openDetail(j);
    });

    // Apply Now button
    const applyUrl = safeText(j.apply_url);
    const applyBtn = document.createElement("a");
    applyBtn.className = "apply-btn";
    if (applyUrl) {
      applyBtn.href = applyUrl;
      applyBtn.target = "_blank";
      applyBtn.rel = "noopener noreferrer";
      applyBtn.textContent = "Apply Now →";
    } else {
      applyBtn.className = "apply-btn disabled";
      applyBtn.textContent = "No link";
    }

    actions.appendChild(viewBtn);
    actions.appendChild(applyBtn);

    // Build card (minimal structure)
    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(tags);
    if (salary) {
      card.appendChild(salary);
    }
    card.appendChild(actions);

    grid.appendChild(card);
  });
}

fetch("master_jobs.json")
  .then(r => r.json())
  .then(data => {
    // Handle both flat array and {jobs: [...]} wrapper formats
    const jobs = Array.isArray(data) ? data : (data.jobs || []);

    if (jobs.length === 0) {
      throw new Error("No jobs found");
    }

    jobs.sort((a, b) => (b.date_posted || "").localeCompare(a.date_posted || ""));
    allJobs = jobs.map(j => {
      return { ...j, _locationBuckets: getLocationBuckets(j.location) };
    });
    activeCategory = getCategoryFromUrl();
    const params = new URLSearchParams(window.location.search);
    keywordQuery = safeText(params.get("q")).toLowerCase();
    if (keywordQuery) {
      keywordSearch.value = keywordQuery;
    }
    updateSearchClearVisibility();
    currentPage = 1;
    renderFilters();
    renderJobs();
    checkUrlForJob();
  })
  .catch(err => {
    grid.innerHTML = `<p style="color: var(--muted); padding: 40px; text-align: center;">
      Could not load jobs data. Please try again later.
    </p>`;
    console.error(err);
  });
