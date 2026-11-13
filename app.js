const input = document.querySelector("#photo-input");
const dropZone = document.querySelector("#drop-zone");
const previewShell = document.querySelector("#preview-shell");
const preview = document.querySelector("#photo-preview");
const canvas = document.querySelector("#painting-canvas");
const fileStatus = document.querySelector("#file-status");
const dropFile = document.querySelector("#drop-file");
const generateButton = document.querySelector("#generate-button");
const saveButton = document.querySelector("#save-button");
const command = document.querySelector("#command");
const copyButton = document.querySelector("#copy-command");
const copyStatus = document.querySelector("#copy-status");
const stageRange = document.querySelector("#stage-range");
const stageWord = document.querySelector("#stage-word");
const stageCount = document.querySelector("#stage-count");
const stages = ["Broad colour", "Mid-tone texture", "Edges", "Framed output"];
let selectedFile = null;
let imageUrl = null;
let sourceImage = null;
let animationFrame = null;
let generated = false;

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
  if (imageUrl) URL.revokeObjectURL(imageUrl);
  selectedFile = file;
  imageUrl = URL.createObjectURL(file);
  preview.src = imageUrl;
  sourceImage = new Image();
  sourceImage.onload = () => {
    generateButton.disabled = false;
    saveButton.disabled = true;
    generated = false;
    previewShell.classList.remove("is-generating", "is-complete");
  };
  sourceImage.src = imageUrl;
  previewShell.classList.remove("is-empty");
  fileStatus.textContent = `${file.name} is ready. Click Generate painting to start.`;
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

function fitCanvas(image) {
  const maxSize = 1100;
  const scale = Math.min(1, maxSize / Math.max(image.naturalWidth, image.naturalHeight));
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
}

function paintPatch(context, source, x, y, radius, rotation) {
  const sampleX = Math.max(0, Math.min(source.width - 1, Math.round(x)));
  const sampleY = Math.max(0, Math.min(source.height - 1, Math.round(y)));
  const pixel = source.data[(sampleY * source.width + sampleX) * 4];
  const color = `rgb(${pixel}, ${source.data[(sampleY * source.width + sampleX) * 4 + 1]}, ${source.data[(sampleY * source.width + sampleX) * 4 + 2]})`;
  context.save();
  context.translate(x, y);
  context.rotate(rotation);
  context.fillStyle = color;
  context.globalAlpha = 0.78;
  context.beginPath();
  context.ellipse(0, 0, radius * 1.6, radius * 0.52, 0, 0, Math.PI * 2);
  context.fill();
  context.globalAlpha = 0.2;
  context.fillStyle = "#fff4d8";
  context.beginPath();
  context.ellipse(-radius * 0.25, -radius * 0.1, radius * 1.2, radius * 0.18, 0, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function generatePainting() {
  if (!sourceImage || !sourceImage.complete) return;
  if (animationFrame) cancelAnimationFrame(animationFrame);
  fitCanvas(sourceImage);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const sourceCanvas = document.createElement("canvas");
  sourceCanvas.width = canvas.width;
  sourceCanvas.height = canvas.height;
  const sourceContext = sourceCanvas.getContext("2d", { willReadFrequently: true });
  sourceContext.drawImage(sourceImage, 0, 0, canvas.width, canvas.height);
  const source = sourceContext.getImageData(0, 0, canvas.width, canvas.height);
  const background = source.data;
  const average = [0, 0, 0];
  for (let index = 0; index < background.length; index += 4) {
    average[0] += background[index];
    average[1] += background[index + 1];
    average[2] += background[index + 2];
  }
  const pixels = background.length / 4;
  context.fillStyle = `rgb(${Math.round(average[0] / pixels)}, ${Math.round(average[1] / pixels)}, ${Math.round(average[2] / pixels)})`;
  context.fillRect(0, 0, canvas.width, canvas.height);
  previewShell.classList.add("is-generating");
  previewShell.classList.remove("is-complete");
  generateButton.disabled = true;
  saveButton.disabled = true;
  generated = false;
  const totalPatches = Math.max(120, Math.round((canvas.width * canvas.height) / 4200));
  let completed = 0;
  const paint = () => {
    const batchSize = 8;
    for (let index = 0; index < batchSize && completed < totalPatches; index += 1) {
      const x = Math.random() * canvas.width;
      const y = Math.random() * canvas.height;
      const radius = Math.max(5, Math.min(canvas.width, canvas.height) * (0.012 + Math.random() * 0.025));
      paintPatch(context, source, x, y, radius, (Math.random() - 0.5) * 1.2);
      completed += 1;
    }
    const progress = completed / totalPatches;
    stageRange.value = String(Math.min(3, Math.floor(progress * 4)));
    stageWord.textContent = stages[Number(stageRange.value)];
    stageCount.textContent = `${Number(stageRange.value) + 1} / ${stages.length}`;
    fileStatus.textContent = `Painting ${Math.round(progress * 100)}%`;
    if (completed < totalPatches) {
      animationFrame = requestAnimationFrame(paint);
      return;
    }
    context.globalAlpha = 0.3;
    context.filter = "saturate(1.15) contrast(1.05)";
    context.drawImage(sourceCanvas, 0, 0);
    context.filter = "none";
    context.globalAlpha = 1;
    generated = true;
    previewShell.classList.remove("is-generating");
    previewShell.classList.add("is-complete");
    fileStatus.textContent = "Painting complete. Save it or generate again.";
    saveButton.disabled = false;
  };
  animationFrame = requestAnimationFrame(paint);
}

generateButton.addEventListener("click", generatePainting);
saveButton.addEventListener("click", () => {
  if (!generated) return;
  const link = document.createElement("a");
  const name = selectedFile.name.replace(/\.[^/.]+$/, "") || "painting";
  link.download = `${name}_oilpastel_preview.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(command.textContent);
    copyStatus.textContent = "Copied.";
  } catch (error) {
    copyStatus.textContent = "Select the command to copy it.";
  }
});
