(() => {
  const validateApp = document.getElementById("validate_app");
    const groupStatus = document.getElementById("group_status");
  const courseGroupList = document.getElementById("course_group_list");
  const createNewCourse = document.getElementById("create_new_course");
  const selectedCourseDisplay = document.getElementById("selected_course_display");
  const parentGroupPath = document.getElementById("parent_group_path");
  const newCourseFields = document.getElementById("new_course_fields");
  const newCoursePath = document.getElementById("new_course_path");
  const existingOffering = document.getElementById("existing_offering_full_path");
  const createNewOffering = document.getElementById("create_new_offering");
  const newOfferingFields = document.getElementById("new_offering_fields");
  const newOfferingName = document.getElementById("new_offering_name");
  const offeringDerivedPath = document.getElementById("offering_derived_path");
  const existingAssessment = document.getElementById("existing_assessment_full_path");
  const createNewAssessment = document.getElementById("create_new_assessment");
  const newAssessmentFields = document.getElementById("new_assessment_fields");
  const newAssessmentName = document.getElementById("new_assessment_name");
  const assessmentDerivedPath = document.getElementById("assessment_derived_path");
  const courseStep = document.getElementById("course_step");
  const courseStepStatus = document.getElementById("course_step_status");
  const assessmentSection = document.getElementById("assessment_section");
  const assessmentStep = document.getElementById("assessment_step");
  const assessmentStepStatus = document.getElementById("assessment_step_status");
  const provisionSection = document.getElementById("provision_section");
  const provisionStep = document.getElementById("provision_step");
  const provisionStepStatus = document.getElementById("provision_step_status");
  const offeringPath = document.getElementById("offering_path");
  const offeringName = document.getElementById("offering_name");
  const assessmentPath = document.getElementById("assessment_path");
  const assessmentName = document.getElementById("assessment_name");
  const assessmentModes = document.querySelectorAll("input[name='assessment_mode']");
  const baseRepositoryModes = document.querySelectorAll("input[name='base_repository_mode']");
  const forkRepositoryFields = document.getElementById("fork_repository_fields");
  const baseRepositoryFullPath = document.getElementById("base_repository_full_path");
  const forkRepositoryStatus = document.getElementById("fork_repository_status");
  const provisionSummary = document.getElementById("provision_summary");
  const csvFile = document.getElementById("csv_file");
  const csvSampleHelp = document.getElementById("csv_sample_help");
  const groupCsvSampleDownload = document.getElementById("csv_sample_download");
  const individualCsvSampleDownload = document.getElementById("csv_sample_download_individual");
  const dryRunButton = document.getElementById("dry_run_button");


  const requiredElements = [
    validateApp, groupStatus, courseGroupList, createNewCourse, selectedCourseDisplay,
    parentGroupPath, newCourseFields, newCoursePath, existingOffering, createNewOffering,
    newOfferingFields, newOfferingName, offeringDerivedPath, existingAssessment,
    createNewAssessment, newAssessmentFields, newAssessmentName, assessmentDerivedPath,
    courseStep, courseStepStatus, assessmentSection, assessmentStep, assessmentStepStatus,
    provisionSection, provisionStep, provisionStepStatus, offeringPath, offeringName,
    assessmentPath, assessmentName, forkRepositoryFields, baseRepositoryFullPath,
    forkRepositoryStatus, provisionSummary, csvFile, csvSampleHelp,
    groupCsvSampleDownload, individualCsvSampleDownload, dryRunButton,
  ];

  if (requiredElements.some((element) => !element)) {
    return;
  }

  
  function appendOption(select, value, label) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  }
  
  function resetSelect(select, label) {
    select.replaceChildren();
    appendOption(select, "", label);
  }
  
  function encodedPath(path) {
    return path.split("/").map(encodeURIComponent).join("/");
  }
  
  function fetchJson(url) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    return fetch(url, { signal: controller.signal })
      .then((response) => response.json().then((payload) => ({ ok: response.ok, payload })))
      .finally(() => window.clearTimeout(timeout));
  }
  
  function selectedModeLabel() {
    const selected = document.querySelector("input[name='assessment_mode']:checked");
    if (!selected) {
      return "";
    }
    return selected.value === "group" ? "group assessment" : "individual assessment";
  }
  
  function selectedModeArticle() {
    const label = selectedModeLabel();
    return label.startsWith("individual") ? "an" : "a";
  }
  
  function slugifyPath(value) {
    return value
      .trim()
      .toLowerCase()
      .replace(/([a-z])([0-9])/g, "$1-$2")
      .replace(/([0-9])([a-z])/g, "$1-$2")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }
  
  function hasCourseSelection() {
    return Boolean(parentGroupPath.value.trim());
  }
  
  function hasAssessmentSelection() {
    const hasOffering = Boolean(existingOffering.value || offeringPath.value.trim());
    const hasAssessment = Boolean(existingAssessment.value || assessmentPath.value.trim());
    return hasCourseSelection()
      && hasOffering
      && hasAssessment
      && hasBaseRepositorySelection()
      && Boolean(selectedModeLabel());
  }
  
  function hasBaseRepositorySelection() {
    const selected = document.querySelector("input[name='base_repository_mode']:checked");
    if (!selected) {
      return false;
    }
    return selected.value === "blank" || Boolean(baseRepositoryFullPath.value);
  }
  
  function selectedBaseRepositoryLabel() {
    const selected = document.querySelector("input[name='base_repository_mode']:checked");
    if (!selected) {
      return "";
    }
    return selected.value === "blank" ? "Blank repository" : `Fork from ${baseRepositoryFullPath.value}`;
  }
  
  function displayPath(path) {
    return path || "new path";
  }
  
  function appendSummaryItem(label, value) {
    const item = document.createElement("span");
    item.className = "summary-item";
  
    const labelNode = document.createElement("span");
    labelNode.className = "summary-label";
    labelNode.textContent = `${label}:`;
  
    const valueNode = document.createElement("span");
    valueNode.className = "summary-value";
    valueNode.textContent = value;
  
    item.append(labelNode, valueNode);
    provisionSummary.appendChild(item);
  }
  
  function clearNewOffering() {
    newOfferingFields.classList.add("hidden");
    newOfferingName.value = "";
    offeringPath.value = "";
    offeringName.value = "";
    offeringDerivedPath.textContent = "Enter a display name";
  }
  
  function clearNewAssessment() {
    newAssessmentFields.classList.add("hidden");
    newAssessmentName.value = "";
    assessmentPath.value = "";
    assessmentName.value = "";
    assessmentDerivedPath.textContent = "Enter a display name";
  }
  
  function resetProjectSelect(label) {
    resetSelect(baseRepositoryFullPath, label);
    baseRepositoryFullPath.value = "";
  }
  
  function clearBaseRepository(resetProjects = false) {
    for (const mode of baseRepositoryModes) {
      mode.checked = false;
    }
    forkRepositoryFields.classList.add("hidden");
    baseRepositoryFullPath.value = "";
    if (resetProjects) {
      resetProjectSelect("Select previous repository");
      forkRepositoryStatus.textContent = "Select an existing course to load repositories.";
    }
  }
  
  function updateStepState(section, fieldset, status, enabled, complete) {
    fieldset.disabled = !enabled;
    section.classList.toggle("is-locked", !enabled);
    section.classList.toggle("is-complete", complete);
    status.textContent = complete ? "Complete" : enabled ? "Ready" : "Locked";
  }
  
  function updateSampleDownload() {
    const selected = document.querySelector("input[name='assessment_mode']:checked");
    const isIndividual = selected && selected.value === "individual";
    groupCsvSampleDownload.classList.toggle("hidden", isIndividual);
    individualCsvSampleDownload.classList.toggle("hidden", !isIndividual);
    csvSampleHelp.textContent = isIndividual
      ? "Use this sample when each student should receive a project/repository inside the selected assessment."
      : "Use this sample when each CSV group should become a project/repository for the selected assessment.";
  }
  
  function updateProgressiveWorkflow() {
    const courseReady = hasCourseSelection();
    const assessmentReady = hasAssessmentSelection();
    const csvReady = Boolean(csvFile.files && csvFile.files.length);
  
    updateSampleDownload();
    courseStep.classList.toggle("is-complete", courseReady);
    courseStepStatus.textContent = courseReady ? "Complete" : "Required";
    updateStepState(assessmentSection, assessmentStep, assessmentStepStatus, courseReady, assessmentReady);
    updateStepState(provisionSection, provisionStep, provisionStepStatus, assessmentReady, csvReady);
  
    dryRunButton.disabled = !(assessmentReady && csvReady);
  
    if (assessmentReady) {
      const offering = displayPath(existingOffering.value || offeringName.value.trim() || offeringPath.value.trim());
      const assessment = displayPath(existingAssessment.value || assessmentName.value.trim() || assessmentPath.value.trim());
      provisionSummary.replaceChildren();
      appendSummaryItem("Course", selectedCourseDisplay.value);
      appendSummaryItem("Offering", offering);
      appendSummaryItem("Assessment", assessment);
      appendSummaryItem("Base", selectedBaseRepositoryLabel());
      appendSummaryItem("Mode", `${selectedModeArticle()} ${selectedModeLabel()}`);
    } else {
      provisionSummary.textContent = "Complete the assessment details to review the provision target.";
    }
  }
  
  function selectExistingCourse(path, name) {
    parentGroupPath.value = path;
    selectedCourseDisplay.value = `${name} (${path})`;
    newCourseFields.classList.add("hidden");
    newCoursePath.value = "";
    clearNewOffering();
    clearNewAssessment();
    clearBaseRepository(true);
    resetSelect(existingOffering, "Loading offerings...");
    resetSelect(existingAssessment, "Select previous assessment");
    updateProgressiveWorkflow();
    assessmentSection.scrollIntoView({ behavior: "smooth", block: "start" });
    loadOfferings(path);
    loadCourseProjects(path);
  }
  
  function appendCourseTree(course) {
    const courseItem = document.createElement("li");
    const courseName = document.createElement("button");
    courseName.type = "button";
    courseName.className = "course-select";
    courseName.dataset.coursePath = course.parent.full_path;
    courseName.textContent = course.parent.name;
    courseName.addEventListener("click", () => {
      selectExistingCourse(course.parent.full_path, course.parent.name);
    });
    const coursePath = document.createElement("span");
    coursePath.className = "muted";
    coursePath.textContent = ` ${course.parent.full_path}`;
    courseItem.append(courseName, coursePath);
  
    courseGroupList.appendChild(courseItem);
  }
  
  function loadOfferings(coursePath) {
    fetchJson(`/groups/${encodedPath(coursePath)}/offerings`)
      .then(({ ok, payload }) => {
        resetSelect(existingOffering, "Select previous offering");
        if (!ok) {
          groupStatus.textContent = payload.error_detail
            ? `${payload.error} ${payload.error_type || ""}: ${payload.error_detail}`
            : payload.error || "GitLab offering browse failed.";
          return;
        }
  
        for (const offering of payload.offerings) {
          appendOption(existingOffering, offering.full_path, offering.full_path);
        }
        updateProgressiveWorkflow();
      })
      .catch(() => {
        resetSelect(existingOffering, "Select previous offering");
        groupStatus.textContent = "GitLab offering browse timed out or failed.";
        updateProgressiveWorkflow();
      });
  }
  
  function loadAssessments(offeringPath) {
    fetchJson(`/groups/${encodedPath(offeringPath)}/assessments`)
      .then(({ ok, payload }) => {
        resetSelect(existingAssessment, "Select previous assessment");
        if (!ok) {
          groupStatus.textContent = payload.error_detail
            ? `${payload.error} ${payload.error_type || ""}: ${payload.error_detail}`
            : payload.error || "GitLab assessment browse failed.";
          return;
        }
  
        for (const assessment of payload.assessments) {
          appendOption(existingAssessment, assessment.full_path, assessment.full_path);
        }
        updateProgressiveWorkflow();
      })
      .catch(() => {
        resetSelect(existingAssessment, "Select previous assessment");
        groupStatus.textContent = "GitLab assessment browse timed out or failed.";
        updateProgressiveWorkflow();
      });
  }
  
  function loadCourseProjects(coursePath) {
    resetProjectSelect("Loading repositories...");
    forkRepositoryStatus.textContent = "Loading repositories...";
    fetchJson(`/groups/${encodedPath(coursePath)}/projects`)
      .then(({ ok, payload }) => {
        resetProjectSelect("Select previous repository");
        if (!ok) {
          forkRepositoryStatus.textContent = payload.error_detail
            ? `${payload.error} ${payload.error_type || ""}: ${payload.error_detail}`
            : payload.error || "GitLab project browse failed.";
          updateProgressiveWorkflow();
          return;
        }
  
        for (const project of payload.projects) {
          appendOption(
            baseRepositoryFullPath,
            project.path_with_namespace,
            `${project.name} (${project.path_with_namespace})`
          );
        }
        forkRepositoryStatus.textContent = payload.projects.length
          ? "Repositories loaded."
          : "No repositories were returned for this course.";
        updateProgressiveWorkflow();
      })
      .catch(() => {
        resetProjectSelect("Select previous repository");
        forkRepositoryStatus.textContent = "GitLab project browse timed out or failed.";
        updateProgressiveWorkflow();
      });
  }
  
  createNewCourse.addEventListener("click", () => {
    parentGroupPath.value = "";
    selectedCourseDisplay.value = "New course";
    newCourseFields.classList.remove("hidden");
    clearNewOffering();
    clearNewAssessment();
    clearBaseRepository(true);
    resetSelect(existingOffering, "Select previous offering");
    resetSelect(existingAssessment, "Select previous assessment");
    updateProgressiveWorkflow();
    newCoursePath.focus();
  });
  
  newCoursePath.addEventListener("input", () => {
    const cleanPath = newCoursePath.value.trim().replace(/^\/+|\/+$/g, "");
    parentGroupPath.value = cleanPath;
    selectedCourseDisplay.value = cleanPath ? `New course (${cleanPath})` : "New course";
    updateProgressiveWorkflow();
  });
  
  existingOffering.addEventListener("change", () => {
    clearNewAssessment();
    clearBaseRepository();
    resetSelect(existingAssessment, "Select previous assessment");
    if (existingOffering.value) {
      clearNewOffering();
      loadAssessments(existingOffering.value);
    }
    updateProgressiveWorkflow();
  });
  
  createNewOffering.addEventListener("click", () => {
    existingOffering.value = "";
    clearNewAssessment();
    clearBaseRepository();
    resetSelect(existingAssessment, "Select previous assessment");
    newOfferingFields.classList.remove("hidden");
    newOfferingName.focus();
    updateProgressiveWorkflow();
  });
  
  newOfferingName.addEventListener("input", () => {
    const name = newOfferingName.value.trim();
    const derivedPath = slugifyPath(name);
    offeringName.value = name;
    offeringPath.value = derivedPath;
    offeringDerivedPath.textContent = derivedPath || "Enter a display name";
    updateProgressiveWorkflow();
  });
  
  existingAssessment.addEventListener("change", () => {
    if (existingAssessment.value) {
      clearNewAssessment();
    }
    clearBaseRepository();
    updateProgressiveWorkflow();
  });
  
  createNewAssessment.addEventListener("click", () => {
    existingAssessment.value = "";
    clearBaseRepository();
    newAssessmentFields.classList.remove("hidden");
    newAssessmentName.focus();
    updateProgressiveWorkflow();
  });
  
  newAssessmentName.addEventListener("input", () => {
    const name = newAssessmentName.value.trim();
    const derivedPath = slugifyPath(name);
    assessmentPath.value = derivedPath;
    assessmentName.value = name;
    assessmentDerivedPath.textContent = derivedPath || "Enter a display name";
    updateProgressiveWorkflow();
  });
  
  csvFile.addEventListener("change", updateProgressiveWorkflow);
  for (const mode of assessmentModes) {
    mode.addEventListener("change", updateProgressiveWorkflow);
  }
  for (const mode of baseRepositoryModes) {
    mode.addEventListener("change", () => {
      const isFork = mode.checked && mode.value === "fork";
      forkRepositoryFields.classList.toggle("hidden", !isFork);
      if (!isFork) {
        baseRepositoryFullPath.value = "";
      }
      updateProgressiveWorkflow();
    });
  }
  baseRepositoryFullPath.addEventListener("change", updateProgressiveWorkflow);
    if (validateApp.dataset.gitlabConfigured === "true") {
      fetchJson("/groups")
    .then(({ ok, payload }) => {
      if (!ok) {
        const diagnostic = payload.error_detail
          ? `${payload.error} ${payload.error_type || ""}: ${payload.error_detail}`
          : payload.error || "GitLab group browse failed.";
        groupStatus.textContent = diagnostic;
        return;
      }
  
      for (const course of payload.groups) {
        appendCourseTree(course);
      }
  
      groupStatus.textContent = payload.groups.length
        ? "Existing GitLab course groups loaded."
        : "No top-level GitLab course groups were returned.";
    })
    .catch(() => {
      groupStatus.textContent = "GitLab group browse timed out or failed.";
    });
    }
    updateProgressiveWorkflow();
})();
