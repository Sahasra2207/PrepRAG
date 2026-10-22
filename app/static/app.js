const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message = data && data.detail ? data.detail : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

function showMessage(id, message, kind = "") {
  const el = $(id);
  el.textContent = message || "";
  el.className = `message ${kind}`.trim();
}

function setBusy(buttonId, busy, busyText) {
  const button = $(buttonId);
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = busyText;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
  }
}

async function refreshDocuments() {
  try {
    const [documents, stats] = await Promise.all([
      api("/api/documents"),
      api("/api/stats"),
    ]);
    $("doc-count").textContent = stats.documents;
    $("chunk-count").textContent = stats.total_chunks;
    const list = $("document-list");
    list.replaceChildren();
    if (!documents.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "No documents indexed yet.";
      list.appendChild(li);
      return;
    }
    for (const doc of documents) {
      const li = document.createElement("li");
      const name = document.createElement("strong");
      name.textContent = doc.filename;
      const chunks = document.createElement("span");
      chunks.textContent = `${doc.chunks} chunks`;
      li.append(name, chunks);
      list.appendChild(li);
    }
  } catch (error) {
    console.error(error);
  }
}

function renderAnswer(data) {
  $("answer-area").classList.remove("hidden");
  $("answer-mode").textContent = {
    llm: "LLM + retrieved context",
    extractive_fallback: "Local extractive fallback",
    no_context: "No context",
  }[data.mode] || data.mode;
  $("answer-text").textContent = data.answer;
  const warning = $("warning");
  if (data.warning) {
    warning.textContent = data.warning;
    warning.classList.remove("hidden");
  } else {
    warning.textContent = "";
    warning.classList.add("hidden");
  }

  const sources = $("sources");
  sources.replaceChildren();
  if (!data.sources.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "No relevant source chunks were retrieved.";
    sources.appendChild(p);
  } else {
    for (const source of data.sources) {
      const card = document.createElement("article");
      card.className = "source";
      const head = document.createElement("div");
      head.className = "source-head";
      const name = document.createElement("span");
      name.textContent = `${source.document} · chunk ${source.chunk}`;
      const distance = document.createElement("span");
      distance.textContent = source.distance == null ? "" : `cosine distance: ${source.distance.toFixed(3)}`;
      head.append(name, distance);
      const excerpt = document.createElement("p");
      excerpt.textContent = source.excerpt;
      card.append(head, excerpt);
      sources.appendChild(card);
    }
  }
}

$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  $("file-name").textContent = file ? file.name : "or click here to browse";
});

$("upload-btn").addEventListener("click", async () => {
  const file = $("file-input").files[0];
  if (!file) {
    showMessage("upload-message", "Choose a PDF, TXT, or MD file first.", "error");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  setBusy("upload-btn", true, "Processing document…");
  showMessage("upload-message", "Extracting text, creating chunks, and indexing embeddings. The first run may download the embedding model.");
  try {
    const result = await api("/api/upload", { method: "POST", body: formData });
    showMessage("upload-message", `${result.message}\nAdded ${result.chunks_added} chunks. Total indexed chunks: ${result.total_chunks}.`, "success");
    $("file-input").value = "";
    $("file-name").textContent = "or click here to browse";
    await refreshDocuments();
  } catch (error) {
    showMessage("upload-message", error.message, "error");
  } finally {
    setBusy("upload-btn", false);
  }
});

$("sample-btn").addEventListener("click", async () => {
  setBusy("sample-btn", true, "Loading sample…");
  showMessage("upload-message", "Adding the built-in sample study notes.");
  try {
    const sample = await api("/api/sample-study-notes");
    const blob = new Blob([sample.text], { type: "text/plain;charset=utf-8" });
    const formData = new FormData();
    formData.append("file", blob, sample.filename);
    const result = await api("/api/upload", { method: "POST", body: formData });
    showMessage("upload-message", `Sample notes added successfully. ${result.chunks_added} chunks indexed.`, "success");
    await refreshDocuments();
  } catch (error) {
    showMessage("upload-message", error.message, "error");
  } finally {
    setBusy("sample-btn", false);
  }
});

$("ask-btn").addEventListener("click", async () => {
  const question = $("question").value.trim();
  if (question.length < 2) {
    showMessage("ask-message", "Enter a question with at least two characters.", "error");
    return;
  }
  setBusy("ask-btn", true, "Searching…");
  showMessage("ask-message", "Searching your indexed documents and preparing an answer.");
  try {
    const data = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: Number($("top-k").value) }),
    });
    showMessage("ask-message", "");
    renderAnswer(data);
  } catch (error) {
    showMessage("ask-message", error.message, "error");
  } finally {
    setBusy("ask-btn", false);
  }
});

$("question").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") $("ask-btn").click();
});

async function checkHealth() {
  try {
    await api("/api/health");
    $("health").textContent = "Backend connected";
    $("health").classList.add("ok");
  } catch {
    $("health").textContent = "Backend unavailable";
  }
}
checkHealth();
refreshDocuments();

// Quiz, company-oriented mock practice, and local progress tracking.
let activeQuiz = null;

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function generateQuiz() {
  setBusy("generate-quiz-btn", true, "Generating…");
  showMessage("quiz-message", "Building questions from your indexed study material.");
  $("quiz-area").replaceChildren();
  try {
    activeQuiz = await api(`/api/quiz/generate?count=${Number($("quiz-count").value)}`, { method: "POST" });
    showMessage("quiz-message", `Created ${activeQuiz.total} questions from your uploaded material. Questions test concepts from your uploaded material.`, "success");
    renderQuiz(activeQuiz);
  } catch (error) {
    showMessage("quiz-message", error.message, "error");
  } finally {
    setBusy("generate-quiz-btn", false);
  }
}

function renderQuiz(quiz) {
  const area = $("quiz-area"); area.replaceChildren();
  const form = make("form", "quiz-form");
  quiz.questions.forEach((q, qi) => {
    const card = make("section", "quiz-question");
    card.appendChild(make("h3", "", `${qi + 1}. ${q.question}`));
    q.options.forEach((option, oi) => {
      const label = make("label", "quiz-option");
      const input = make("input"); input.type = "radio"; input.name = `q-${qi}`; input.value = String(oi); input.required = true;
      label.append(input, make("span", "", option)); card.appendChild(label);
    });
    card.appendChild(make("p", "muted", `Topic: ${q.topic} · Source: ${q.document}, chunk ${q.chunk}`));
    form.appendChild(card);
  });
  const submit = make("button", "button primary quiz-submit", "Submit quiz"); submit.type = "submit"; form.appendChild(submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const answers = quiz.questions.map((_, i) => {
      const selected = form.querySelector(`input[name="q-${i}"]:checked`);
      return selected ? Number(selected.value) : -1;
    });
    if (answers.some(a => a < 0)) { showMessage("quiz-message", "Please answer every question before submitting.", "error"); return; }
    submit.disabled = true; submit.textContent = "Checking answers…";
    try {
      const result = await api("/api/quiz/submit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ quiz_id: quiz.quiz_id, answers }) });
      renderQuizReview(result); showMessage("quiz-message", `Quiz completed: ${result.score}/${result.total} (${result.percentage}%).`, "success");
      await refreshProgress();
    } catch (error) { showMessage("quiz-message", error.message, "error"); submit.disabled = false; submit.textContent = "Submit quiz"; }
  });
  area.appendChild(form);
}

function renderQuizReview(result) {
  const area = $("quiz-area"); area.replaceChildren();
  area.appendChild(make("h3", "", `Your score: ${result.score}/${result.total} (${result.percentage}%)`));
  result.review.forEach((r, i) => {
    const item = make("article", `review-item ${r.is_correct ? "correct" : "incorrect"}`);
    item.appendChild(make("strong", "", `${i + 1}. ${r.is_correct ? "Correct" : "Review this answer"} · ${r.topic}`));
    item.appendChild(make("p", "", r.question));
    item.appendChild(make("p", "", `Correct answer: ${r.options[r.correct_index]}`));
    item.appendChild(make("p", "muted", `${r.explanation} Source: ${r.document}, chunk ${r.chunk}.`));
    area.appendChild(item);
  });
}

async function loadMockQuestions() {
  setBusy("load-mock-btn", true, "Loading…");
  showMessage("mock-message", "Loading practice questions.");
  $("mock-area").replaceChildren();
  try {
    const company = encodeURIComponent($("mock-company").value);
    const category = encodeURIComponent($("mock-category").value);
    const data = await api(`/api/mock/questions?company=${company}&category=${category}&count=5`);
    showMessage("mock-message", `${data.note} Answer aloud before opening each guide.`, "success");
    const area = $("mock-area");
    data.questions.forEach((q, i) => {
      const card = make("article", "mock-question");
      card.appendChild(make("h3", "", `${i + 1}. ${q.question}`));
      card.appendChild(make("p", "muted", `Category: ${q.category}`));
      const details = make("details"); details.appendChild(make("summary", "", "Show answer guide")); details.appendChild(make("p", "", q.answer_guide)); card.appendChild(details);
      const notes = make("textarea"); notes.rows = 2; notes.placeholder = "Optional: jot down your answer or feedback…"; card.appendChild(notes);
      const row = make("div", "mock-save-row"); row.appendChild(make("label", "", "Self-rating (1 = needs work, 5 = confident)"));
      const rating = make("select"); [1,2,3,4,5].forEach(n => { const op=make("option","",String(n)); op.value=String(n); rating.appendChild(op); }); row.appendChild(rating);
      const save = make("button", "button secondary", "Save practice"); save.type = "button";
      save.addEventListener("click", async () => {
        save.disabled = true;
        try {
          await api("/api/mock/attempt", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ company: data.company, category: q.category, question: q.question, self_rating: Number(rating.value), notes: notes.value }) });
          save.textContent = "Saved ✓"; showMessage("mock-message", "Practice attempt saved to local progress.", "success"); await refreshProgress();
        } catch (error) { showMessage("mock-message", error.message, "error"); save.disabled = false; }
      });
      row.appendChild(save); card.appendChild(row); area.appendChild(card);
    });
  } catch (error) { showMessage("mock-message", error.message, "error"); }
  finally { setBusy("load-mock-btn", false); }
}

async function refreshProgress() {
  const area = $("progress-area");
  try {
    const data = await api("/api/progress"); area.replaceChildren();
    const metrics = make("div", "progress-metrics");
    [[data.quiz_attempts,"Quiz attempts"],[data.questions_answered,"Questions answered"],[`${data.overall_accuracy}%`,"Quiz accuracy"],[data.mock_practice_attempts,"Mock practices saved"]].forEach(([value,label]) => {
      const card=make("div","progress-metric"); card.appendChild(make("strong","",String(value))); card.appendChild(make("span","",label)); metrics.appendChild(card);
    }); area.appendChild(metrics);
    area.appendChild(make("h3","","Weak topics to revisit"));
    if (!data.weak_topics.length) area.appendChild(make("p","muted","No weak topic identified yet. Complete more quiz questions; a topic needs at least two answers and below 70% accuracy to be flagged."));
    else { const wrap=make("div"); data.weak_topics.forEach(t=>wrap.appendChild(make("span","weak-topic",`${t.topic}: ${t.accuracy}% (${t.correct}/${t.attempts})`))); area.appendChild(wrap); }
    area.appendChild(make("h3","","Topic performance"));
    if (!data.topic_stats.length) area.appendChild(make("p","muted","Topic statistics will appear after you submit a quiz."));
    data.topic_stats.forEach(t=>{
      const row=make("div","topic-row"); row.appendChild(make("span","",t.topic)); const bar=make("div","progress-bar"); const fill=make("span"); fill.style.width=`${t.accuracy}%`; bar.appendChild(fill); row.appendChild(bar); row.appendChild(make("strong","",`${t.accuracy}%`)); area.appendChild(row);
    });
    area.appendChild(make("p","muted",data.note));
    if (data.recent_mock_practice.length) { area.appendChild(make("h3","","Recent mock practice")); data.recent_mock_practice.forEach(m=>area.appendChild(make("p","muted",`${m.company} · ${m.category} · self-rating ${m.rating}/5 · ${m.question}`))); }
  } catch (error) { area.replaceChildren(make("p","message error",error.message)); }
}

$("generate-quiz-btn").addEventListener("click", generateQuiz);
$("load-mock-btn").addEventListener("click", loadMockQuestions);
$("refresh-progress-btn").addEventListener("click", refreshProgress);
refreshProgress();
