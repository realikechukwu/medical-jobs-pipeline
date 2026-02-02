// ============ AUTH HELPERS ============

async function getCurrentUser() {
  // Return null if Supabase isn't loaded
  if (typeof supabase === "undefined") {
    return null;
  }

  try {
    const { data: { user } } = await supabase.auth.getUser();
    return user;
  } catch (error) {
    console.warn("Auth check failed:", error);
    return null;
  }
}

// ============ SAVE JOB FUNCTIONS ============

async function saveJob(jobId, jobDetails = {}) {
  let user = null;

  // Only check for logged-in user if Supabase is available
  if (typeof supabase !== "undefined") {
    try {
      user = await getCurrentUser();
    } catch (error) {
      console.warn("Could not check auth status, using localStorage");
      user = null;
    }
  }

  if (user) {
    // User is logged in → Save to Supabase
    try {
      const { error } = await supabase
        .from("saved_jobs")
        .insert({
          user_id: user.id,
          job_id: jobId,
          job_title: jobDetails.title || null,
          company: jobDetails.company || null,
          location: jobDetails.location || null,
        });

      if (error && error.code !== "23505") {
        console.error("Error saving job to Supabase:", error);
      }
    } catch (error) {
      console.error("Supabase save failed:", error);
    }
  } else {
    // User is NOT logged in → Save to localStorage
    const savedJobs = JSON.parse(localStorage.getItem("savedJobs") || "[]");
    if (!savedJobs.includes(jobId)) {
      savedJobs.push(jobId);
      localStorage.setItem("savedJobs", JSON.stringify(savedJobs));

      // Store job details for migration later
      const savedDetails = JSON.parse(localStorage.getItem("savedJobDetails") || "{}");
      savedDetails[jobId] = jobDetails;
      localStorage.setItem("savedJobDetails", JSON.stringify(savedDetails));

      // Show nudge after 3 saves
      checkAndShowNudge(savedJobs.length);
    }
  }

  // Update UI
  updateSaveButton(jobId, true);
}

async function unsaveJob(jobId) {
  let user = null;

  if (typeof supabase !== "undefined") {
    try {
      user = await getCurrentUser();
    } catch (error) {
      user = null;
    }
  }

  if (user) {
    // Remove from Supabase
    try {
      await supabase
        .from("saved_jobs")
        .delete()
        .eq("user_id", user.id)
        .eq("job_id", jobId);
    } catch (error) {
      console.error("Supabase delete failed:", error);
    }
  } else {
    // Remove from localStorage
    const savedJobs = JSON.parse(localStorage.getItem("savedJobs") || "[]");
    const updated = savedJobs.filter(id => id !== jobId);
    localStorage.setItem("savedJobs", JSON.stringify(updated));
  }

  // Update UI
  updateSaveButton(jobId, false);
}

async function isJobSaved(jobId) {
  let user = null;

  if (typeof supabase !== "undefined") {
    try {
      user = await getCurrentUser();
    } catch (error) {
      user = null;
    }
  }

  if (user) {
    // Check Supabase
    try {
      const { data } = await supabase
        .from("saved_jobs")
        .select("id")
        .eq("user_id", user.id)
        .eq("job_id", jobId)
        .single();

      return !!data;
    } catch (error) {
      return false;
    }
  } else {
    // Check localStorage
    const savedJobs = JSON.parse(localStorage.getItem("savedJobs") || "[]");
    return savedJobs.includes(jobId);
  }
}

async function getSavedJobs() {
  let user = null;

  if (typeof supabase !== "undefined") {
    try {
      user = await getCurrentUser();
    } catch (error) {
      user = null;
    }
  }

  if (user) {
    // Get from Supabase
    try {
      const { data } = await supabase
        .from("saved_jobs")
        .select("*")
        .eq("user_id", user.id)
        .order("saved_at", { ascending: false });

      return data || [];
    } catch (error) {
      console.error("Failed to fetch saved jobs:", error);
      return [];
    }
  } else {
    // Get from localStorage
    const savedJobs = JSON.parse(localStorage.getItem("savedJobs") || "[]");
    return savedJobs.map(id => ({ job_id: id }));
  }
}

async function getSavedJobsCount() {
  const jobs = await getSavedJobs();
  return jobs.length;
}

// ============ MIGRATION ============

async function migrateLocalSavedJobs(userId) {
  const localSavedJobs = JSON.parse(localStorage.getItem('savedJobs') || '[]');
  
  if (localSavedJobs.length === 0) return 0;
  
  const localJobDetails = JSON.parse(localStorage.getItem('savedJobDetails') || '{}');
  let migratedCount = 0;
  
  for (const jobId of localSavedJobs) {
    const details = localJobDetails[jobId] || {};
    
    const { error } = await supabase
      .from('saved_jobs')
      .upsert({
        user_id: userId,
        job_id: jobId,
        job_title: details.title || null,
        company: details.company || null,
        location: details.location || null,
      }, {
        onConflict: 'user_id,job_id'
      });
    
    if (!error) migratedCount++;
  }
  
  // Clear localStorage
  localStorage.removeItem('savedJobs');
  localStorage.removeItem('savedJobDetails');
  localStorage.removeItem('hasSeenSaveNudge');
  
  return migratedCount;
}

// ============ NUDGE ============

function checkAndShowNudge(savedCount) {
  const hasSeenNudge = localStorage.getItem('hasSeenSaveNudge');
  
  if (savedCount >= 3 && !hasSeenNudge) {
    showSignUpNudge(savedCount);
  }
}

function showSignUpNudge(count) {
  // Remove existing nudge if any
  const existingNudge = document.querySelector('.nudge-toast');
  if (existingNudge) existingNudge.remove();
  
  const nudge = document.createElement('div');
  nudge.className = 'nudge-toast';
  nudge.innerHTML = `
    <div class="nudge-content">
      <div class="nudge-icon">🔖</div>
      <div class="nudge-text">
        <strong>Keep your ${count} saved jobs safe</strong>
        <p>Create a free account to sync across all your devices</p>
      </div>
    </div>
    <div class="nudge-actions">
      <a href="signup.html" class="btn-nudge-primary">Sign Up</a>
      <button class="btn-nudge-text" onclick="dismissNudge()">Not now</button>
    </div>
  `;
  
  document.body.appendChild(nudge);
  setTimeout(() => nudge.classList.add('show'), 100);
}

function dismissNudge() {
  localStorage.setItem('hasSeenSaveNudge', 'true');
  const nudge = document.querySelector('.nudge-toast');
  if (nudge) {
    nudge.classList.remove('show');
    setTimeout(() => nudge.remove(), 300);
  }
}

// ============ UI HELPERS ============

function updateSaveButton(jobId, isSaved) {
  const buttons = document.querySelectorAll(`[data-job-id="${jobId}"] .save-btn, .save-btn[data-job-id="${jobId}"]`);
  buttons.forEach(btn => {
    btn.classList.toggle('saved', isSaved);
    btn.setAttribute('aria-pressed', isSaved);
    
    // Update icon if using different icons for saved/unsaved
    const icon = btn.querySelector('.save-icon');
    if (icon) {
      icon.innerHTML = isSaved
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg>'
        : '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg>';
    }
    
    // Update text if button has text
    const text = btn.querySelector('.save-text');
    if (text) {
      text.textContent = isSaved ? 'Saved' : 'Save Job';
    }
  });
}

// Initialize save buttons on page load
async function initSaveButtons() {
  const saveButtons = document.querySelectorAll('.save-btn');
  
  for (const btn of saveButtons) {
    const jobId = btn.dataset.jobId || btn.closest('[data-job-id]')?.dataset.jobId;
    if (jobId) {
      const isSaved = await isJobSaved(jobId);
      updateSaveButton(jobId, isSaved);
    }
  }
}

// Show migration success toast
function showMigrationToast() {
  const count = sessionStorage.getItem('migratedJobsCount');
  if (!count || count === '0') return;
  
  sessionStorage.removeItem('migratedJobsCount');
  
  const toast = document.createElement('div');
  toast.className = 'toast toast-success';
  toast.innerHTML = `
    <span class="toast-icon">✓</span>
    <span>${count} saved job${count > 1 ? 's' : ''} synced to your account</span>
  `;
  
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add('show'), 100);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Run on page load
document.addEventListener('DOMContentLoaded', () => {
  showMigrationToast();
  initSaveButtons();
});
