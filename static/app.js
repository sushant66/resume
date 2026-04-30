const SECTION_ORDER = [
  "basics",
  "experience",
  "skills",
  "projects",
  "education",
  "achievements",
  "pdf",
  "meta",
  "schema",
];

const SECTION_META = {
  basics: { title: "Basics", subtitle: "Name, contact, summary, and profile links" },
  experience: { title: "Experience", subtitle: "Jobs, dates, bullets, and location" },
  skills: { title: "Technical Skills", subtitle: "Skill groups and keywords" },
  projects: { title: "Projects", subtitle: "Projects, links, and highlights" },
  education: { title: "Education", subtitle: "Institution and academic details" },
  achievements: { title: "Achievements", subtitle: "Awards, certifications, and profiles" },
  pdf: { title: "PDF Metadata", subtitle: "Metadata embedded into the compiled PDF" },
  meta: { title: "Release Metadata", subtitle: "Versioning and canonical metadata" },
  schema: { title: "Structured Data", subtitle: "Schema.org-specific fields" },
};

const state = {
  schema: null,
  data: null,
  errors: [],
  openSection: "basics",
  activeEntries: {},
  splitterDragging: false,
  pendingFocusPath: null,
};

const elements = {
  workspace: document.getElementById("workspace"),
  splitter: document.getElementById("splitter"),
  form: document.getElementById("resumeForm"),
  formMessage: document.getElementById("formMessage"),
  errorSummary: document.getElementById("errorSummary"),
  logsPanel: document.getElementById("logsPanel"),
  previewFrame: document.getElementById("previewFrame"),
  branchValue: document.getElementById("branchValue"),
  versionValue: document.getElementById("versionValue"),
  pushModeValue: document.getElementById("pushModeValue"),
  pushMessage: document.getElementById("pushMessage"),
  commitMessage: document.getElementById("commitMessage"),
  saveButton: document.getElementById("saveButton"),
  generateButton: document.getElementById("generateButton"),
  pushButton: document.getElementById("pushButton"),
  summaryName: document.getElementById("summaryName"),
  summaryEmail: document.getElementById("summaryEmail"),
  summaryPhone: document.getElementById("summaryPhone"),
  summaryLocation: document.getElementById("summaryLocation"),
  summaryInitials: document.getElementById("summaryInitials"),
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  wireActions();
  setupSplitter();
  await Promise.all([loadSchema(), loadResume()]);
}

function wireActions() {
  elements.saveButton.addEventListener("click", () => submitResume("/api/resume", "Saved to data/resume.yaml. Click Generate to refresh the preview."));
  elements.generateButton.addEventListener("click", () => submitResume("/api/generate", "Build completed."));
  elements.pushButton.addEventListener("click", pushResume);
}

function setupSplitter() {
  if (!elements.splitter) {
    return;
  }

  elements.splitter.addEventListener("pointerdown", () => {
    state.splitterDragging = true;
    document.body.style.cursor = "col-resize";
  });

  window.addEventListener("pointermove", (event) => {
    if (!state.splitterDragging || window.innerWidth <= 1180) {
      return;
    }

    const shellRect = elements.workspace.getBoundingClientRect();
    const min = 360;
    const max = Math.min(640, shellRect.width - 520);
    const next = Math.max(min, Math.min(max, event.clientX - shellRect.left));
    document.documentElement.style.setProperty("--editor-width", `${next}px`);
  });

  window.addEventListener("pointerup", () => {
    state.splitterDragging = false;
    document.body.style.cursor = "";
  });
}

async function loadSchema() {
  const response = await fetch("/api/schema");
  state.schema = await response.json();
}

async function loadResume() {
  const response = await fetch("/api/resume");
  const payload = await response.json();
  state.data = payload.data;
  ensureDefaultActiveEntries();
  renderEditor();
  renderSummaryCard();
  applyStatus(payload.status);
}

function ensureDefaultActiveEntries() {
  for (const key of SECTION_ORDER) {
    const value = state.data?.[key];
    if (Array.isArray(value) && value.length && state.activeEntries[key] == null) {
      state.activeEntries[key] = 0;
    }
  }
}

function renderEditor() {
  elements.form.innerHTML = "";
  state.errors = [];
  renderErrors();

  for (const key of SECTION_ORDER) {
    const schema = state.schema.properties[key];
    if (!schema) {
      continue;
    }

    const card = document.createElement("section");
    card.className = "panel section-card";
    card.dataset.path = toPointer([key]);
    if (state.openSection === key) {
      card.classList.add("is-open");
    }

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "section-toggle";
    toggle.addEventListener("click", () => {
      state.openSection = state.openSection === key ? "" : key;
      renderEditor();
      renderErrors();
    });

    const titleWrap = document.createElement("div");
    titleWrap.className = "section-title";

    const title = document.createElement("strong");
    title.textContent = SECTION_META[key]?.title || schema.title || prettify(key);
    titleWrap.appendChild(title);

    const subtitle = document.createElement("span");
    subtitle.textContent = SECTION_META[key]?.subtitle || sectionCountLabel(key);
    titleWrap.appendChild(subtitle);

    const count = document.createElement("span");
    count.className = "section-count";
    count.textContent = state.openSection === key ? "Hide" : sectionCountLabel(key);

    toggle.appendChild(titleWrap);
    toggle.appendChild(count);
    card.appendChild(toggle);

    if (state.openSection === key) {
      const body = document.createElement("div");
      body.className = "section-body";
      body.appendChild(renderSectionContent(key, schema, state.data[key]));
      card.appendChild(body);
    }

  elements.form.appendChild(card);
  }

  applyPendingFocus();
}

function renderSectionContent(key, schema, value) {
  if (schema.type === "array") {
    return renderArrayEditor(schema, value || [], [key], key);
  }
  return renderField(schema, value, [key], key);
}

function renderField(schema, value, path, label) {
  if (schema.type === "object") {
    return renderObject(schema, value || {}, path);
  }
  if (schema.type === "array") {
    return renderArrayEditor(schema, value || [], path, label);
  }
  return renderScalar(schema, value, path, label);
}

function renderObject(schema, value, path) {
  const container = document.createElement("div");
  container.className = "section-grid";
  const entries = Object.entries(schema.properties || {});
  const ordered = [
    ...entries.filter(([, childSchema]) => !["array", "object"].includes(childSchema.type)),
    ...entries.filter(([, childSchema]) => childSchema.type === "object"),
    ...entries.filter(([, childSchema]) => childSchema.type === "array"),
  ];

  ordered.forEach(([key, childSchema]) => {
    const childValue = value?.[key];
    const childPath = [...path, key];
    const wrapper = document.createElement("div");
    wrapper.dataset.path = toPointer(childPath);

    if (childSchema.type === "object") {
      wrapper.className = "nested-object";
      const heading = document.createElement("div");
      heading.className = "array-heading";
      const title = document.createElement("h4");
      title.textContent = childSchema.title || prettify(key);
      heading.appendChild(title);
      wrapper.appendChild(heading);
      wrapper.appendChild(renderObject(childSchema, childValue || {}, childPath));
    } else if (childSchema.type === "array") {
      wrapper.appendChild(renderArrayEditor(childSchema, childValue || [], childPath, key));
    } else {
      wrapper.appendChild(renderScalar(childSchema, childValue, childPath, key));
    }

    container.appendChild(wrapper);
  });

  return container;
}

function renderArrayEditor(schema, value, path, label) {
  const pointer = toPointer(path);
  const wrapper = document.createElement("div");
  wrapper.className = "array-block";
  wrapper.dataset.path = pointer;

  const heading = document.createElement("div");
  heading.className = "array-heading";

  const title = document.createElement("h4");
  title.textContent = schema.title || prettify(label);
  heading.appendChild(title);

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "mini-button";
  addButton.textContent = "Add Entry";
  addButton.addEventListener("click", (event) => {
    event.stopPropagation();
    const next = createDefaultValue(schema.items);
    const list = getValueAtPath(state.data, path) || [];
    list.push(next);
    setValueAtPath(state.data, path, list);
    state.activeEntries[pointer] = list.length - 1;
    renderEditor();
    renderSummaryCard();
  });
  heading.appendChild(addButton);

  wrapper.appendChild(heading);

  const layout = document.createElement("div");
  layout.className = "array-layout";

  const listPane = document.createElement("div");
  listPane.className = "list-pane";
  const entryList = document.createElement("div");
  entryList.className = "entry-list";

  value.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "entry-row";
    if ((state.activeEntries[pointer] ?? 0) === index) {
      row.classList.add("is-active");
    }
    row.dataset.path = toPointer([...path, index]);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "item-toggle";
    toggle.addEventListener("click", () => {
      state.activeEntries[pointer] = index;
      state.pendingFocusPath = pointer;
      renderEditor();
      renderErrors();
    });

    const summary = summarizeArrayItem(item, schema.items, label, index);
    const summaryNode = document.createElement("div");
    summaryNode.className = "item-summary";
    const strong = document.createElement("strong");
    strong.textContent = summary.title;
    const sub = document.createElement("span");
    sub.textContent = summary.subtitle;
    summaryNode.appendChild(strong);
    summaryNode.appendChild(sub);
    toggle.appendChild(summaryNode);
    row.appendChild(toggle);

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "danger-button";
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const list = getValueAtPath(state.data, path) || [];
      list.splice(index, 1);
      setValueAtPath(state.data, path, list);
      const current = state.activeEntries[pointer] ?? 0;
      state.activeEntries[pointer] = list.length ? Math.min(current, list.length - 1) : null;
      renderEditor();
      renderSummaryCard();
    });
    row.appendChild(removeButton);

    entryList.appendChild(row);
  });

  if (!value.length) {
    const empty = document.createElement("div");
    empty.className = "detail-empty";
    empty.textContent = "No entries yet. Add one to start editing.";
    entryList.appendChild(empty);
  }

  listPane.appendChild(entryList);
  layout.appendChild(listPane);

  const detailPane = document.createElement("div");
  detailPane.className = "detail-pane";

  const activeIndex = value.length ? normalizeActiveIndex(pointer, value.length) : null;
  if (activeIndex == null) {
    const empty = document.createElement("div");
    empty.className = "detail-empty";
    empty.textContent = "Select an entry to edit its details.";
    detailPane.appendChild(empty);
  } else {
    const activeValue = value[activeIndex];
    const activePath = [...path, activeIndex];
    const rendered = schema.items.type === "object"
      ? renderObject(schema.items, activeValue, activePath)
      : renderScalar(schema.items, activeValue, activePath, `${label} ${activeIndex + 1}`);
    detailPane.dataset.path = toPointer(activePath);
    detailPane.appendChild(rendered);
  }

  layout.appendChild(detailPane);
  wrapper.appendChild(layout);

  return wrapper;
}

function applyPendingFocus() {
  if (!state.pendingFocusPath) {
    return;
  }

  const detailPane = document.querySelector(`.detail-pane[data-path="${cssEscape(state.pendingFocusPath)}"]`);
  if (!detailPane) {
    state.pendingFocusPath = null;
    return;
  }

  detailPane.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
  const firstInput = detailPane.querySelector("input, textarea");
  if (firstInput) {
    window.requestAnimationFrame(() => {
      window.setTimeout(() => {
        firstInput.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
        firstInput.focus();
        if (typeof firstInput.select === "function" && firstInput.tagName === "INPUT") {
          firstInput.select();
        }
      }, 120);
    });
  }

  state.pendingFocusPath = null;
}

function normalizeActiveIndex(pointer, length) {
  if (!length) {
    return null;
  }
  const current = state.activeEntries[pointer];
  const next = current == null ? 0 : Math.max(0, Math.min(length - 1, current));
  state.activeEntries[pointer] = next;
  return next;
}

function renderScalar(schema, value, path, label) {
  const field = document.createElement("label");
  field.className = "field";
  field.dataset.path = toPointer(path);

  const title = document.createElement("span");
  title.textContent = schema.title || prettify(label);
  field.appendChild(title);

  const nullable = Array.isArray(schema.type) && schema.type.includes("null");
  const scalarType = Array.isArray(schema.type) ? schema.type.find((entry) => entry !== "null") : schema.type;
  const useTextarea = schema["x-widget"] === "textarea";
  const input = useTextarea ? document.createElement("textarea") : document.createElement("input");

  if (!useTextarea) {
    input.type = scalarType === "integer" ? "number" : "text";
  }

  input.value = value ?? "";
  input.placeholder = nullable ? "Leave blank for null" : "";
  input.addEventListener("input", (event) => {
    let nextValue = event.target.value;
    if (scalarType === "integer") {
      nextValue = nextValue === "" ? "" : Number(nextValue);
    }
    if (nullable && nextValue === "") {
      nextValue = null;
    }
    setValueAtPath(state.data, path, nextValue);
    if (path[0] === "basics") {
      renderSummaryCard();
    }
  });

  field.appendChild(input);
  return field;
}

function summarizeArrayItem(item, schema, label, index) {
  if (schema.type !== "object") {
    const text = String(item || "").trim();
    return {
      title: truncate(text, 72) || `${prettify(label)} ${index + 1}`,
      subtitle: text.length > 72 ? "Click to edit the full value" : "Single value",
    };
  }

  if (item.company) {
    return { title: item.company, subtitle: item.position || `Entry ${index + 1}` };
  }
  if (item.name && Array.isArray(item.keywords)) {
    return { title: item.name, subtitle: `${item.keywords.length} keyword${item.keywords.length === 1 ? "" : "s"}` };
  }
  if (item.institution) {
    return { title: item.institution, subtitle: item.study_type || item.area || `Entry ${index + 1}` };
  }
  if (item.label || item.network) {
    return { title: item.label || item.network, subtitle: item.url || item.username || `Entry ${index + 1}` };
  }
  if (item.name) {
    return { title: item.name, subtitle: `Entry ${index + 1}` };
  }

  const firstKey = Object.keys(item)[0];
  return {
    title: truncate(String(item[firstKey] || `${prettify(label)} ${index + 1}`), 72),
    subtitle: `Entry ${index + 1}`,
  };
}

function sectionCountLabel(key) {
  const value = state.data?.[key];
  if (Array.isArray(value)) {
    return `${value.length} item${value.length === 1 ? "" : "s"}`;
  }
  return "Open section";
}

function createDefaultValue(schema) {
  if (!schema) {
    return "";
  }
  if (Array.isArray(schema.type)) {
    const nonNullType = schema.type.find((entry) => entry !== "null");
    if (nonNullType === "object") {
      return createDefaultObject(schema);
    }
    return null;
  }
  if (schema.type === "object") {
    return createDefaultObject(schema);
  }
  if (schema.type === "array") {
    return [];
  }
  if (schema.type === "integer") {
    return 0;
  }
  return "";
}

function createDefaultObject(schema) {
  const output = {};
  Object.entries(schema.properties || {}).forEach(([key, childSchema]) => {
    output[key] = createDefaultValue(childSchema);
  });
  return output;
}

function getValueAtPath(source, path) {
  return path.reduce((current, segment) => current?.[segment], source);
}

function setValueAtPath(source, path, value) {
  const last = path[path.length - 1];
  const target = path.slice(0, -1).reduce((current, segment) => current[segment], source);
  target[last] = value;
}

function toPointer(path) {
  return `/${path.join("/")}`;
}

function prettify(value) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function getInitials(name) {
  return String(name || "Resume")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function renderSummaryCard() {
  const basics = state.data?.basics || {};
  const name = basics.name || "Resume";
  elements.summaryName.textContent = name;
  elements.summaryEmail.textContent = basics.email || "No email";
  elements.summaryPhone.textContent = basics.phone?.display || "No phone";
  elements.summaryLocation.textContent = basics.location?.display || "No location";
  elements.summaryInitials.textContent = getInitials(name);
}

function applyStatus(status) {
  if (!status) {
    return;
  }
  elements.branchValue.textContent = status.branch || "-";
  elements.versionValue.textContent = status.version || "-";
  elements.pushModeValue.textContent = status.pushMode === "github_api"
    ? "GitHub API"
    : status.pushMode === "git"
      ? "Local Git"
      : "Not configured";
  if (status.previewUrl) {
    elements.previewFrame.src = status.previewUrl;
  }
}

function setBusy(isBusy) {
  elements.saveButton.disabled = isBusy;
  elements.generateButton.disabled = isBusy;
  elements.pushButton.disabled = isBusy;
}

async function submitResume(endpoint, successMessage) {
  setBusy(true);
  elements.formMessage.textContent = "Working...";
  elements.pushMessage.textContent = "";

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: state.data }),
    });
    const payload = await response.json();
    state.errors = payload.errors || [];
    renderErrors();

    if (!response.ok) {
      elements.formMessage.textContent = payload.message || "Validation or build failed.";
      if (payload.logs) {
        renderLogs(payload.logs);
      }
      return;
    }

    elements.formMessage.textContent = successMessage;
    applyStatus(payload.status);
    if (payload.previewUrl) {
      elements.previewFrame.src = payload.previewUrl;
    }
    if (payload.logs) {
      renderLogs(payload.logs);
    }
  } catch (error) {
    elements.formMessage.textContent = error.message;
  } finally {
    setBusy(false);
  }
}

async function pushResume() {
  setBusy(true);
  elements.pushMessage.textContent = "Pushing...";
  elements.formMessage.textContent = "";

  try {
    const response = await fetch("/api/push", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        data: state.data,
        commitMessage: elements.commitMessage.value,
      }),
    });
    const payload = await response.json();
    state.errors = payload.errors || [];
    renderErrors();

    if (!response.ok) {
      const dirty = payload.unrelatedDirtyFiles?.length
        ? ` Unrelated files: ${payload.unrelatedDirtyFiles.join(", ")}`
        : "";
      elements.pushMessage.textContent = (payload.message || "Push failed.") + dirty;
      if (payload.logs) {
        renderLogs(payload.logs);
      }
      return;
    }

    elements.pushMessage.textContent = `Pushed ${payload.commitSha.slice(0, 7)} on ${payload.branch}. Build: ${payload.buildUrl}`;
    renderLogs(payload.logs || []);
    await loadResume();
  } catch (error) {
    elements.pushMessage.textContent = error.message;
  } finally {
    setBusy(false);
  }
}

function renderLogs(logs) {
  if (!logs?.length) {
    elements.logsPanel.textContent = "No command logs available.";
    return;
  }
  elements.logsPanel.textContent = logs
    .map((log) => `$ ${log.command}\n${log.output || "(no output)"}`)
    .join("\n\n");
}

function renderErrors() {
  document.querySelectorAll(".field-error").forEach((node) => node.classList.remove("field-error"));
  document.querySelectorAll(".error-text").forEach((node) => node.remove());

  if (!state.errors.length) {
    elements.errorSummary.classList.add("hidden");
    elements.errorSummary.innerHTML = "";
    return;
  }

  const list = document.createElement("ul");
  state.errors.forEach((error) => {
    const item = document.createElement("li");
    item.textContent = `${error.path}: ${error.message}`;
    list.appendChild(item);

    const target = document.querySelector(`[data-path="${cssEscape(error.path)}"]`);
    if (target) {
      target.classList.add("field-error");
      const text = document.createElement("p");
      text.className = "error-text";
      text.textContent = error.message;
      target.appendChild(text);
    }
  });

  elements.errorSummary.innerHTML = "";
  elements.errorSummary.appendChild(list);
  elements.errorSummary.classList.remove("hidden");
}

function cssEscape(value) {
  return value.replace(/"/g, '\\"');
}
