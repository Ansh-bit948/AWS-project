/* Backend-driven local and AWS administrator console. */
const $ = (s) => document.querySelector(s);
const cloud = window.IEAI_CONFIG || null;
let selected = "",
  current = null,
  version = 1,
  challenge = null;
const mode =
  new URLSearchParams(location.search).get("mode") === "local" || !cloud
    ? "local"
    : "aws";
const isCloud = mode === "aws";
const tables = {
  roles: { offset: 0, search: "" },
  profiles: { offset: 0, search: "" },
  permission_catalog: { offset: 0, search: "" },
};
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fmt = (v) =>
  v === null || v === undefined ? "Unavailable" : Number(v).toLocaleString();
function status(text, error = false) {
  $("#status").textContent = text;
  $("#notice").textContent = error ? text : "";
  $("#notice").hidden = !error;
  const connected = !error && text.startsWith("Connected");
  $("#connectionPill").classList.toggle("online", connected);
  $("#connectionPill").classList.toggle("error", error);
  $("#sideConnection").classList.toggle("online", connected);
  $("#sideConnection").classList.toggle("error", error);
  $("#connectionLabel").textContent = error
    ? "Connection problem"
    : connected
      ? isCloud
        ? "AWS connected"
        : "Local connected"
      : isCloud && !token()
        ? "Sign in required"
        : "Connecting";
  $("#backendCaption").textContent = connected
    ? isCloud
      ? "Cognito authenticated"
      : "Local workspace"
    : error
      ? "Check connection"
      : isCloud
        ? "Awaiting sign-in"
        : "Loading source";
  $("#emptyHint").textContent =
    isCloud && !token()
      ? "Sign in to load the private AWS datasets, or switch to local mode."
      : "Import a source CSV to begin your analysis.";
  $("#emptySignIn").hidden = !isCloud || !!token();
}
function token() {
  return sessionStorage.getItem("ieai_token") || "";
}
function signOut() {
  sessionStorage.removeItem("ieai_token");
  selected = "";
  current = null;
  $("#appView").hidden = true;
  $("#empty").hidden = false;
  $("#loginOpen").textContent = "Sign in";
  status("Sign in required");
}
async function call(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (isCloud && token()) headers.set("authorization", "Bearer " + token());
  let r;
  for (let attempt = 0; attempt < 5; attempt++) {
    r = await fetch((isCloud ? cloud.apiUrl : "/api") + path, {
      ...options,
      headers,
    });
    if (r.status !== 429) break;
    await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
  }
  const x = await r
    .json()
    .catch(() => ({ error: "Server returned an unreadable response" }));
  if (!r.ok) {
    if (isCloud && r.status === 401) signOut();
    throw Error(x.detail || x.error || "Request failed: " + r.status);
  }
  return x;
}
function post(path, body) {
  return call(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}
function download(data, name) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
$("#backendName").textContent = isCloud ? "AWS backend" : "Local backend";
$("#backendCaption").textContent = isCloud
  ? "Awaiting sign-in"
  : "Loading source";
$("#emptySignIn").hidden = !isCloud;
$("#emptySignIn").onclick = () => $("#loginDialog").showModal();
$("#modeSwitch").textContent = isCloud
  ? "Use local backend"
  : "Use AWS backend";
$("#modeSwitch").hidden = !cloud;
$("#modeSwitch").onclick = () => {
  location.search = isCloud ? "?mode=local" : "?mode=aws";
};
$("#loginOpen").hidden = !isCloud;
$("#loginOpen").onclick = () =>
  token() ? signOut() : $("#loginDialog").showModal();
$("#closeLogin").onclick = () => {
  challenge = null;
  $("#newPasswordRow").hidden = true;
  $("[name=new_password]").required = false;
  $("#loginDialog").close();
};
$("#loginForm").onsubmit = async (e) => {
  e.preventDefault();
  $("#loginError").textContent = "";
  const form = e.currentTarget,
    username = form.username.value;
  try {
    const body = challenge
      ? {
          ClientId: cloud.clientId,
          ChallengeName: "NEW_PASSWORD_REQUIRED",
          Session: challenge,
          ChallengeResponses: {
            USERNAME: username,
            NEW_PASSWORD: form.new_password.value,
          },
        }
      : {
          AuthFlow: "USER_PASSWORD_AUTH",
          ClientId: cloud.clientId,
          AuthParameters: { USERNAME: username, PASSWORD: form.password.value },
        };
    const r = await fetch(
      "https://cognito-idp." + cloud.region + ".amazonaws.com/",
      {
        method: "POST",
        headers: {
          "content-type": "application/x-amz-json-1.1",
          "x-amz-target":
            "AWSCognitoIdentityProviderService." +
            (challenge ? "RespondToAuthChallenge" : "InitiateAuth"),
        },
        body: JSON.stringify(body),
      },
    );
    const x = await r.json();
    if (!r.ok) throw Error(x.message || "Sign in failed");
    if (x.ChallengeName === "NEW_PASSWORD_REQUIRED") {
      challenge = x.Session;
      $("#newPasswordRow").hidden = false;
      form.new_password.required = true;
      $("#loginError").textContent = "Choose a permanent password to continue.";
      return;
    }
    if (!x.AuthenticationResult?.IdToken)
      throw Error("Authentication requires an unsupported challenge");
    sessionStorage.setItem("ieai_token", x.AuthenticationResult.IdToken);
    challenge = null;
    form.reset();
    $("#newPasswordRow").hidden = true;
    form.new_password.required = false;
    $("#loginDialog").close();
    $("#loginOpen").textContent = "Sign out";
    await refreshDatasets();
  } catch (err) {
    $("#loginError").textContent = err.message;
  }
};
for (const id of ["importOpen", "emptyImport", "switchImport"])
  $("#" + id).onclick = () =>
    isCloud && !token()
      ? $("#loginDialog").showModal()
      : $("#importDialog").showModal();
$("#closeDialog").onclick = () => $("#importDialog").close();
$("#uploadForm").onsubmit = async (e) => {
  e.preventDefault();
  const b = e.submitter,
    fd = new FormData(e.currentTarget),
    f = fd.get("file");
  b.disabled = true;
  $("#uploadError").textContent = "";
  b.textContent = "Uploading source…";
  try {
    if (f.size > 25 * 1024 * 1024)
      throw Error("The demo accepts files up to 25 MiB.");
    let did;
    if (isCloud) {
      const p = await post("/datasets/presign", {
        filename: f.name,
        name: fd.get("name"),
        source_url: fd.get("source_url"),
        license_note: fd.get("license_note"),
      });
      const r = await fetch(p.upload_url, {
        method: "PUT",
        headers: p.headers,
        body: f,
      });
      if (!r.ok) throw Error("S3 upload failed: " + r.status);
      did = p.dataset_id;
      b.textContent = "AWS Lambda is analyzing…";
      let ready = false;
      for (let i = 0; i < 45; i++) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const list = (await call("/datasets")).datasets,
          d = list.find((x) => x.dataset_id === did);
        if (d?.status === "failed")
          throw Error(d.error || "Source validation failed");
        if (d?.status === "ready") {
          ready = true;
          break;
        }
      }
      if (!ready)
        throw Error(
          "Analysis is still pending. Use Refresh to check its status.",
        );
    } else {
      const result = await call("/datasets/import", {
        method: "POST",
        body: fd,
      });
      did = result.dataset_id;
    }
    selected = did;
    $("#importDialog").close();
    await refreshDatasets();
  } catch (err) {
    $("#uploadError").textContent = err.message;
  } finally {
    b.disabled = false;
    b.textContent = "Import and analyze";
  }
};
async function refreshDatasets() {
  try {
    if (isCloud && !token()) {
      signOut();
      return;
    }
    const list = (await call("/datasets")).datasets;
    $("#datasetSelect").innerHTML = list
      .map(
        (d) =>
          '<option value="' +
          esc(d.dataset_id) +
          '">' +
          esc(d.name) +
          " (" +
          esc(d.status || "ready") +
          ")</option>",
      )
      .join("");
    if (!list.length) {
      $("#empty").hidden = false;
      $("#appView").hidden = true;
      status("Connected; import source data");
      return;
    }
    if (!list.some((d) => d.dataset_id === selected))
      selected = (
        list.find((d) => d.status === "ready" || !d.status) || list[0]
      ).dataset_id;
    $("#datasetSelect").value = selected;
    const d = list.find((d) => d.dataset_id === selected);
    if (d.status === "pending" || d.status === "failed")
      throw Error(d.error || "Selected upload is pending. Refresh shortly.");
    await load();
  } catch (err) {
    status(err.message, true);
  }
}
$("#refresh").onclick = refreshDatasets;
$("#datasetSelect").onchange = async (e) => {
  selected = e.target.value;
  reviewOffset = 0;
  for (const s of Object.values(tables)) s.offset = 0;
  await load();
};
async function load() {
  try {
    const payload = await call("/analytics/" + selected + "?compact=1"),
      a = payload.analysis,
      d = payload.dataset;
    current = a;
    version = Number(a.policy_version || 1);
    $("#versionBadge").textContent = "Policy v" + version;
    if (isCloud) $("#loginOpen").textContent = "Sign out";
    $("#empty").hidden = true;
    $("#appView").hidden = false;
    $("#dsName").textContent = d.name;
    $("#dsMeta").textContent =
      fmt(a.counts.users) +
      " users · " +
      fmt(a.counts.permissions) +
      " permissions · " +
      fmt(a.counts.assignments) +
      " active grants · policy v" +
      version;
    for (const [id, key] of [
      ["mUsers", "users"],
      ["mPerms", "permissions"],
      ["mEdges", "assignments"],
      ["mRoles", "roles"],
    ])
      $("#" + id).textContent = fmt(a.counts[key]);
    $("#wBase").textContent = fmt(a.baseline.wsc);
    $("#wOpt").textContent = fmt(a.optimized.wsc);
    const saving = a.baseline.wsc
      ? (1 - a.optimized.wsc / a.baseline.wsc) * 100
      : 0;
    $("#saving").textContent = a.baseline.wsc
      ? saving.toFixed(1) + "%"
      : "Not applicable";
    $("#bar").style.width = Math.max(0, Math.min(100, saving)) + "%";
    const scale = Math.max(
      1,
      a.baseline.wsc,
      a.optimized.wsc,
      a.cohort_baseline?.wsc || 0,
    );
    $("#baseBar").style.width = (a.baseline.wsc / scale) * 100 + "%";
    $("#selectedBar").style.width = (a.optimized.wsc / scale) * 100 + "%";
    const cohort = a.cohort_baseline?.wsc;
    $("#cohortBar").closest(".wsc-row").hidden = cohort === undefined;
    $("#wCohort").textContent = fmt(cohort);
    if (cohort !== undefined)
      $("#cohortBar").style.width = (cohort / scale) * 100 + "%";
    $("#coverage").textContent = (a.optimized.coverage * 100).toFixed(2) + "%";
    $("#integrity").textContent =
      fmt(a.optimized.permission_loss) +
      " missing · " +
      fmt(a.optimized.overgrants) +
      " extra grants";
    $("#computeTime").textContent =
      a.performance?.compute_ms === undefined
        ? "Runtime not recorded"
        : fmt(a.performance.compute_ms) + " ms source analysis";
    const summary = a.risk_summary,
      total = a.risk_findings_total;
    $("#riskCount").textContent = fmt(total);
    $("#highRisk").textContent = fmt(summary.high);
    $("#medRisk").textContent = fmt(summary.medium);
    $("#lowRisk").textContent = fmt(summary.review);
    const high = total ? (summary.high / total) * 360 : 0,
      medium = total ? (summary.medium / total) * 360 : 0;
    $("#donut").style.background = total
      ? "conic-gradient(var(--red) 0deg " +
        high +
        "deg,var(--amber) " +
        high +
        "deg " +
        (high + medium) +
        "deg,var(--blue) " +
        (high + medium) +
        "deg 360deg)"
      : "#edf1f3";
    $("#findings").innerHTML =
      a.risk_findings
        .map(
          (x) =>
            '<div class="finding"><div><b>' +
            esc(x.user_id) +
            "</b><small>" +
            esc(x.reasons.join(" · ")) +
            '</small></div><span class="score ' +
            (x.score >= 70 ? "high" : "") +
            '">' +
            x.score +
            "</span></div>",
        )
        .join("") || "<p>No findings under the current rules.</p>";
    $("#source").textContent = d.source_url;
    $("#license").textContent = d.license_note || "Not provided";
    $("#hash").textContent = d.sha256;
    $("#date").textContent = new Date(d.uploaded_at).toLocaleString();
    $("#runid").textContent = d.run_id || selected;
    $("#method").textContent = Object.values(a.methodology).join(" · ");
    await Promise.all([
      loadTable("roles"),
      loadTable("profiles"),
      loadTable("permission_catalog"),
      loadReview(),
      loadHistory(),
      loadTemporal(),
    ]);
    status(
      isCloud
        ? "Connected to authenticated AWS backend"
        : "Connected to local backend",
    );
  } catch (err) {
    status(err.message, true);
  }
}
async function loadTable(kind) {
  const state = tables[kind],
    data = await call(
      "/catalog/" +
        kind +
        "/" +
        selected +
        "?limit=25&offset=" +
        state.offset +
        "&search=" +
        encodeURIComponent(state.search),
    );
  $("#" + kind + "Page").textContent =
    (data.total ? state.offset + 1 : 0) +
    "–" +
    Math.min(state.offset + 25, data.total) +
    " of " +
    fmt(data.total);
  $("#" + kind + "Prev").disabled = state.offset === 0;
  $("#" + kind + "Next").disabled = state.offset + 25 >= data.total;
  const body = {
    roles: "#rolesBody",
    profiles: "#profilesBody",
    permission_catalog: "#permissionsBody",
  }[kind];
  $(body).innerHTML =
    data.items
      .map((r) =>
        kind === "roles"
          ? '<tr><td><button class="link-btn" data-role="' +
            esc(r.role_id) +
            '"><svg class="icon" aria-hidden="true"><use href="#i-roles"/></svg>' +
            esc(r.role_id) +
            "</button></td><td>" +
            fmt(r.user_count) +
            "</td><td>" +
            fmt(r.permission_count) +
            '</td><td><span class="badge success">' +
            (r.coverage * 100).toFixed(0) +
            "% exact</span></td></tr>"
          : kind === "profiles"
            ? "<tr><td>" +
              esc(r.user_id) +
              "</td><td>" +
              fmt(r.observed_grants) +
              "</td><td>" +
              (r.permission_density * 100).toFixed(2) +
              "%</td><td>" +
              r.rare_grant_count +
              "</td></tr>"
            : "<tr><td>" +
              esc(r.permission_id) +
              "</td><td>" +
              fmt(r.user_count) +
              "</td><td>" +
              (r.support * 100).toFixed(2) +
              "%</td></tr>",
      )
      .join("") || '<tr><td colspan="4">No matching records</td></tr>';
}
for (const kind of Object.keys(tables)) {
  for (const [direction, delta] of [
    ["Prev", -25],
    ["Next", 25],
  ])
    $("#" + kind + direction).onclick = async () => {
      tables[kind].offset = Math.max(0, tables[kind].offset + delta);
      try {
        await loadTable(kind);
      } catch (e) {
        status(e.message, true);
      }
    };
  let timer;
  $("#" + kind + "Search").oninput = (e) => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      tables[kind].search = e.target.value;
      tables[kind].offset = 0;
      try {
        await loadTable(kind);
      } catch (x) {
        status(x.message, true);
      }
    }, 250);
  };
}
$("#rolesBody").onclick = async (e) => {
  const button = e.target.closest("[data-role]");
  if (!button) return;
  try {
    const r = await call(
      "/catalog/roles/" +
        selected +
        "?id=" +
        encodeURIComponent(button.dataset.role),
    );
    $("#roleDetail").textContent = JSON.stringify(r, null, 2);
    $("#roleDialogTitle").textContent = r.role_id;
    $("#roleStats").innerHTML =
      '<span class="badge neutral">' +
      fmt(r.user_count) +
      ' members</span><span class="badge neutral">' +
      fmt(r.permission_count) +
      ' permissions</span><span class="badge success">' +
      (r.coverage * 100).toFixed(0) +
      "% coverage</span>";
    $("#roleMembers").innerHTML = r.users
      .map((u) => "<span>" + esc(u) + "</span>")
      .join("");
    $("#rolePermissions").innerHTML = r.permissions
      .map((p) => "<span>" + esc(p) + "</span>")
      .join("");
    $("#roleDialog").showModal();
  } catch (x) {
    status(x.message, true);
  }
};
$("#closeRole").onclick = () => $("#roleDialog").close();
let reviewOffset = 0;
async function loadReview() {
  const r = await call(
    "/recommendations/" + selected + "?limit=25&offset=" + reviewOffset,
  );
  $("#reviewPage").textContent = fmt(r.total) + " review items";
  $("#reviewPrev").disabled = reviewOffset === 0;
  $("#reviewNext").disabled = reviewOffset + 25 >= r.total;
  $("#recommendations").innerHTML =
    r.items
      .map(
        (x) =>
          '<div class="finding"><div><b>' +
          esc(x.user_id) +
          " · " +
          esc(x.permission_id) +
          "</b><small>" +
          esc(
            {
              pending_review: "Needs review",
              revoke: "Removed",
              retain: "Retained",
            }[x.status] || x.status,
          ) +
          " · " +
          esc(x.reason) +
          '</small></div><span class="decision-actions">' +
          (x.status === "revoke"
            ? ""
            : '<button class="btn mini" data-user="' +
              esc(x.user_id) +
              '" data-permission="' +
              esc(x.permission_id) +
              '" data-decision="revoke">Approve removal</button>') +
          '<button class="btn mini ghost" data-user="' +
          esc(x.user_id) +
          '" data-permission="' +
          esc(x.permission_id) +
          '" data-decision="retain">' +
          (x.status === "revoke" ? "Restore" : "Retain") +
          "</button></span></div>",
      )
      .join("") || "<p>No rare grants to review.</p>";
}
$("#reviewPrev").onclick = async () => {
  reviewOffset = Math.max(0, reviewOffset - 25);
  try {
    await loadReview();
  } catch (e) {
    status(e.message, true);
  }
};
$("#reviewNext").onclick = async () => {
  reviewOffset += 25;
  try {
    await loadReview();
  } catch (e) {
    status(e.message, true);
  }
};
$("#recommendations").onclick = async (e) => {
  const b = e.target.closest("button[data-decision]");
  if (!b) return;
  if (
    b.dataset.decision === "revoke" &&
    !confirm(
      "Remove " +
        b.dataset.permission +
        " from " +
        b.dataset.user +
        " in this application policy? Original source data stay unchanged. You can restore the grant.",
    )
  )
    return;
  b.disabled = true;
  try {
    await post("/decisions", {
      dataset_id: selected,
      user_id: b.dataset.user,
      permission_id: b.dataset.permission,
      decision: b.dataset.decision,
      expected_version: version,
    });
    await load();
  } catch (x) {
    status(x.message, true);
  } finally {
    b.disabled = false;
  }
};
async function loadHistory() {
  const [history, audit] = await Promise.all([
    call("/policy-versions/" + selected),
    call("/audit/" + selected),
  ]);
  $("#versionsBody").innerHTML = history.items
    .map(
      (x) =>
        "<tr><td>v" +
        x.version +
        "</td><td>" +
        actorLabel(x.actor) +
        "</td><td>" +
        esc(changeLabel(x.change_summary)) +
        "</td></tr>",
    )
    .join("");
  $("#auditBody").innerHTML = audit.items
    .map(
      (x) =>
        "<tr><td>" +
        esc(new Date(x.created_at).toLocaleString()) +
        "</td><td>" +
        esc(
          {
            dataset_import: "Source import",
            permission_decision: "Permission review",
            feedback_rl_run: "Feedback learning",
          }[x.action] || x.action,
        ) +
        "</td><td>" +
        actorLabel(x.actor) +
        "</td><td>" +
        esc(changeLabel(x.details)) +
        "</td></tr>",
    )
    .join("");
}
$("#train").onclick = async () => {
  const b = $("#train");
  b.disabled = true;
  $("#rlResult").hidden = false;
  $("#rlResult").textContent = "Reading real administrator feedback…";
  try {
    const report = await post("/rl/train/" + selected, { episodes: 500 });
    $("#rlResult").textContent =
      "Learned from " +
      report.feedback_records +
      " real reviews. Held-out agreement: " +
      (report.evaluation.agreement === null
        ? "insufficient supported holdout states"
        : (report.evaluation.agreement * 100).toFixed(1) + "%") +
      ". Every recommendation still requires approval.";
    download(report, "feedback-model-" + report.model_id + ".json");
  } catch (x) {
    $("#rlResult").textContent = x.message;
  } finally {
    b.disabled = false;
  }
};
$("#authorizationForm").onsubmit = async (e) => {
  e.preventDefault();
  const d = new FormData(e.currentTarget);
  try {
    const result = await post("/authorize/" + selected, {
      user_id: d.get("user_id"),
      permission_id: d.get("permission_id"),
    });
    $("#authResult").classList.toggle("denied", !result.allowed);
    $("#authResult").textContent =
      (result.allowed ? "ALLOWED" : "DENIED") +
      " · policy v" +
      result.policy_version +
      " · roles " +
      (result.matching_roles.join(", ") || "none");
  } catch (x) {
    $("#authResult").textContent = x.message;
  }
};
$("#export").onclick = async () => {
  try {
    download(
      await call("/export/" + selected),
      "policy-" + selected + "-v" + version + ".json",
    );
  } catch (x) {
    status(x.message, true);
  }
};
let historical = null;
initWorkspace();
refreshDatasets();

async function loadTemporal() {
  try {
    historical = await call("/research/amazon");
    const x = historical;
    const agreement = x.evaluation.observed_action_agreement;
    $("#historySummary").textContent =
      (x.time_range?.first?.slice(0, 10) || "Date not recorded") +
      " to " +
      (x.time_range?.last?.slice(0, 10) || "date not recorded") +
      " · An independent source population. Historical change records, not ERP transactions.";
    $("#temporalMetrics").hidden = false;
    $("#learningEvaluation").hidden = false;
    $("#tEvents").textContent = fmt(x.counts.valid_events);
    $("#tUsers").textContent = fmt(x.counts.users);
    $("#tTargets").textContent = fmt(x.counts.targets);
    $("#tHoldout").textContent = fmt(x.model.heldout_records);
    $("#learningAgreement").textContent =
      agreement === null ? "Not evaluated" : (agreement * 100).toFixed(2) + "%";
    $("#majorityAgreement").textContent =
      (x.evaluation.majority_baseline_agreement * 100).toFixed(2) + "%";
    $("#learningBar").style.width =
      agreement === null ? "0%" : agreement * 100 + "%";
    $("#majorityBar").style.width =
      x.evaluation.majority_baseline_agreement * 100 + "%";
    $("#modelComparison").textContent =
      agreement === null
        ? "Insufficient evidence"
        : agreement < x.evaluation.majority_baseline_agreement
          ? "Below the majority baseline"
          : "At or above the majority baseline";
    $("#temporalSplit").textContent =
      fmt(x.model.training_records) +
      " earlier training records; " +
      fmt(x.model.heldout_records) +
      " later held-out records. Supported-action coverage: " +
      (x.evaluation.coverage * 100).toFixed(2) +
      "%.";
    $("#historyExport").disabled = false;
  } catch (e) {
    $("#historySummary").textContent = e.message;
    $("#historyExport").disabled = true;
    $("#temporalMetrics").hidden = true;
    $("#learningEvaluation").hidden = true;
  }
}
$("#historyExport").onclick = () =>
  historical && download(historical, "amazon-history-model.json");

function parseRecorded(value) {
  if (value && typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}
function changeLabel(value) {
  const record = parseRecorded(value);
  if (!record) return String(value || "No details recorded");
  if (record.decision)
    return (
      (record.decision === "revoke" ? "Remove" : "Retain / restore") +
      " " +
      record.permission_id +
      " for " +
      record.user_id
    );
  if (record.distinct_edges !== undefined)
    return fmt(record.distinct_edges) + " distinct source grants";
  if (record.unique_assignments !== undefined)
    return fmt(record.unique_assignments) + " distinct source grants";
  if (record.model_id) return "Model " + record.model_id;
  return "Recorded evidence: " + JSON.stringify(record);
}
function actorLabel(actor) {
  const labels = {
    "local-admin": "Local administrator",
    "dataset-import": "Source ingestion",
  };
  const value = String(actor || "Not recorded");
  return (
    '<span title="' +
    esc(value) +
    '">' +
    esc(labels[value] || value.slice(0, 8) + "…") +
    "</span>"
  );
}
function initWorkspace() {
  const views = {
    overview: [
      "Access overview",
      "A clearer view of who can access what.",
      "IDENTITY GOVERNANCE",
    ],
    roles: [
      "Role catalog",
      "Inspect the structure behind the effective policy.",
      "ROLE DISCOVERY",
    ],
    profiles: [
      "Users & permissions",
      "Source identifiers, observed grants, and measured support.",
      "ACCESS CATALOGS",
    ],
    risk: [
      "Risk & review",
      "Follow the evidence. Make a considered change.",
      "HUMAN APPROVAL",
    ],
    governance: [
      "Policy & audit",
      "Check authorization and trace the decisions behind it.",
      "PERMISSION GOVERNANCE",
    ],
    temporal: [
      "Learning lab",
      "Real outcomes, transparent baselines, and reviewed recommendations.",
      "ADAPTIVE INTELLIGENCE",
    ],
    dataset: [
      "Data provenance",
      "Every result begins with a traceable source.",
      "EVIDENCE & REPRODUCIBILITY",
    ],
  };
  function menu(open) {
    document.body.classList.toggle("nav-open", open);
    $("#navScrim").hidden = !open;
    $("#menuOpen").setAttribute("aria-expanded", String(open));
    const closedMobile =
      window.matchMedia("(max-width: 760px)").matches && !open;
    $("#sidebar").inert = closedMobile;
    if (closedMobile) $("#sidebar").setAttribute("aria-hidden", "true");
    else $("#sidebar").removeAttribute("aria-hidden");
  }
  function showView(id, scroll = false) {
    if (id === "ai") id = "risk";
    if (!views[id]) id = "overview";
    for (const view of document.querySelectorAll("[data-workspace-view]"))
      view.hidden = view.dataset.workspaceView !== id;
    for (const link of document.querySelectorAll("nav [data-view]")) {
      const active = link.dataset.view === id;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    $("#viewTitle").innerHTML =
      esc(views[id][0]) + '<span class="heading-dot">.</span>';
    $("#viewDescription").textContent = views[id][1];
    $("#viewEyebrow").textContent = views[id][2];
    $("#breadcrumbView").textContent = {
      overview: "Overview",
      roles: "Roles",
      profiles: "Users & permissions",
      risk: "Risk & review",
      governance: "Policy & audit",
      temporal: "Learning lab",
      dataset: "Provenance",
    }[id];
    menu(false);
    if (scroll) window.scrollTo({ top: 0, behavior: "auto" });
  }
  for (const link of document.querySelectorAll("[data-view],.brand"))
    link.addEventListener("click", (e) => {
      if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey)
        return;
      e.preventDefault();
      const id = link.dataset.view || "overview";
      if (location.hash !== "#" + id) history.pushState(null, "", "#" + id);
      showView(id, true);
    });
  $("#menuOpen").onclick = () =>
    menu(!document.body.classList.contains("nav-open"));
  $("#navScrim").onclick = () => menu(false);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") menu(false);
  });
  window.addEventListener("hashchange", () =>
    showView(location.hash.slice(1), true),
  );
  window.addEventListener("popstate", () =>
    showView(location.hash.slice(1), true),
  );
  window
    .matchMedia("(max-width: 760px)")
    .addEventListener("change", () => menu(false));
  showView(location.hash.slice(1));
  $("#copyHash").onclick = async () => {
    try {
      await navigator.clipboard.writeText($("#hash").textContent);
      $("#copyHash").setAttribute("aria-label", "Source hash copied");
      $("#copyHash").innerHTML =
        '<svg class="icon" aria-hidden="true"><use href="#i-check"/></svg>';
      setTimeout(() => {
        $("#copyHash").setAttribute("aria-label", "Copy source hash");
        $("#copyHash").innerHTML =
          '<svg class="icon" aria-hidden="true"><use href="#i-copy"/></svg>';
      }, 2000);
    } catch {
      status("Clipboard unavailable. Select the source hash to copy it.", true);
    }
  };
}
