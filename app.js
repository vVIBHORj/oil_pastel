const input = document.querySelector("#photo-input");
const dropZone = document.querySelector("#drop-zone");
const previewShell = document.querySelector("#preview-shell");
const preview = document.querySelector("#photo-preview");
const fileStatus = document.querySelector("#file-status");
const dropFile = document.querySelector("#drop-file");
const command = document.querySelector("#command");
const copyButton = document.querySelector("#copy-command");
const copyStatus = document.querySelector("#copy-status");
const stageRange = document.querySelector("#stage-range");
const stageWord = document.querySelector("#stage-word");
const stageCount = document.querySelector("#stage-count");
const stages = ["Broad colour", "Mid-tone texture", "Edges", "Framed output"];

document.querySelectorAll("section:not(.hero), .site-footer").forEach((section) => {
  section.querySelectorAll("h2, p, figure, .process-ui, .command-card").forEach((element) => element.classList.add("reveal"));
});

const revealObserver = new IntersectionObserver((entries, observer) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });
document.querySelectorAll(".reveal").forEach((element) => revealObserver.observe(element));

function showPhoto(file) {
  if (!file || !file.type.startsWith("image/")) {
    fileStatus.textContent = "Choose an image file to begin.";
    return;
  }
  const url = URL.createObjectURL(file);
  preview.src = url;
  previewShell.classList.remove("is-empty");
  fileStatus.textContent = `${file.name} is ready for painting.`;
  dropFile.textContent = file.name;
  command.textContent = `python oil_pastel_patches.py "${file.name}" --video timelapse.mp4 --speed 4`;
}

input.addEventListener("change", () => showPhoto(input.files[0]));
["dragenter", "dragover"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
}));
["dragleave", "drop"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
}));
dropZone.addEventListener("drop", (event) => showPhoto(event.dataTransfer.files[0]));
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    input.click();
  }
});

stageRange.addEventListener("input", () => {
  const stage = Number(stageRange.value);
  stageWord.textContent = stages[stage];
  stageCount.textContent = `${stage + 1} / ${stages.length}`;
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(command.textContent);
    copyStatus.textContent = "Copied.";
  } catch (error) {
    copyStatus.textContent = "Select the command to copy it.";
  }
});
