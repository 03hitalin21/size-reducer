const form = document.getElementById("upload-form");
const statusEl = document.getElementById("status");
const barEl = document.getElementById("bar");
const downloadEl = document.getElementById("download");

let currentJobId = null;
let pollTimer = null;

function setStatus(text) {
  statusEl.textContent = text;
}

function setProgress(value) {
  const clamped = Math.max(0, Math.min(100, value));
  barEl.style.width = `${clamped}%`;
}

async function pollStatus(jobId) {
  try {
    const response = await fetch(`/api/status/${jobId}`);
    if (!response.ok) {
      setStatus("Unable to fetch status.");
      return;
    }
    const payload = await response.json();
    setProgress(payload.progress || 0);

    if (payload.status === "done" && payload.download_url) {
      setStatus(`Done. Job ${jobId} ready.`);
      downloadEl.href = payload.download_url;
      downloadEl.style.display = "inline-flex";
      clearInterval(pollTimer);
      pollTimer = null;
      return;
    }

    if (payload.status === "error") {
      setStatus(`Error: ${payload.error || "Unknown error"}`);
      clearInterval(pollTimer);
      pollTimer = null;
      return;
    }

    setStatus(`Job ${jobId} is ${payload.status}.`);
  } catch (err) {
    setStatus("Status check failed.");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("file");
  const profile = document.getElementById("profile").value;

  if (!fileInput.files.length) {
    setStatus("Select a file first.");
    return;
  }

  const data = new FormData();
  data.append("file", fileInput.files[0]);
  data.append("profile", profile);

  setStatus("Uploading...");
  setProgress(0);
  downloadEl.style.display = "none";

  try {
    const response = await fetch("/api/upload", {
      method: "POST",
      body: data,
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setStatus(payload.detail || "Upload failed.");
      return;
    }

    const payload = await response.json();
    currentJobId = payload.job_id;
    setStatus(`Uploaded. Job ${currentJobId} queued.`);

    if (pollTimer) {
      clearInterval(pollTimer);
    }
    pollTimer = setInterval(() => pollStatus(currentJobId), 2000);
  } catch (err) {
    setStatus("Upload failed.");
  }
});