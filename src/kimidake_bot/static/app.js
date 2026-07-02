const form = document.querySelector("#fortune-form");
const concern = document.querySelector("#concern");
const counter = document.querySelector("#concern-count");
const submitButton = document.querySelector("#submit-button");
const loading = document.querySelector("#loading");
const errorMessage = document.querySelector("#error-message");
const resultSection = document.querySelector("#result-section");
const result = document.querySelector("#fortune-result");

concern.addEventListener("input", () => {
  counter.textContent = `${concern.value.length} / 800`;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    nickname: document.querySelector("#nickname").value.trim() || null,
    category: document.querySelector("#category").value,
    concern: concern.value.trim(),
  };

  if (!payload.concern) {
    showError("悩みを入力してください。");
    concern.focus();
    return;
  }

  setLoading(true);
  errorMessage.hidden = true;
  resultSection.hidden = true;

  try {
    const response = await fetch("/api/fortune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || "鑑定結果を取得できませんでした。");
    }

    result.textContent = data.result;
    resultSection.hidden = false;
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showError(error instanceof Error ? error.message : "通信に失敗しました。もう一度お試しください。");
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  loading.hidden = !isLoading;
  submitButton.disabled = isLoading;
  submitButton.textContent = isLoading ? "鑑定中…" : "無料で占う";
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}
