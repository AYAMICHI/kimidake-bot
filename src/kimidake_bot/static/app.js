const form = document.querySelector("#fortune-form");
const concern = document.querySelector("#concern");
const counter = document.querySelector("#concern-count");
const submitButton = document.querySelector("#submit-button");
const loading = document.querySelector("#loading");
const errorMessage = document.querySelector("#error-message");
const resultSection = document.querySelector("#result-section");
const result = document.querySelector("#fortune-result");
const premiumContext = document.querySelector("#premium-context");
const premiumPoints = document.querySelector("#premium-points");
const premiumButtonLabel = document.querySelector("#premium-button-label");
const premiumButton = document.querySelector(".premium-button");
const premiumPreviewEnabled = document.body.dataset.premiumPreviewEnabled === "true";
const premiumPreviewSection = document.querySelector("#premium-preview-section");
const premiumPreviewLoading = document.querySelector("#premium-preview-loading");
const premiumPreviewLoadingText = document.querySelector("#premium-preview-loading-text");
const premiumPreviewError = document.querySelector("#premium-preview-error");
const premiumFortuneResult = document.querySelector("#premium-fortune-result");

const analyticsSessionKey = "kimidake_analytics_session_id";
let fallbackSessionId = null;
let currentResultContext = null;
let premiumPreviewInFlight = false;

const premiumCtaByCategory = {
  love: {
    points: [
      "相手が今この関係をどう受け止めていそうか",
      "距離を縮めるなら、どんな連絡が届きやすいか",
      "今見えている関係の分岐",
      "今やると逆効果になりやすいこと",
    ],
    birthPoint: "生年月日から見た、恋愛で出やすい距離の取り方",
    button: "相手の本音と次の一手を見る",
  },
  reconciliation: {
    points: [
      "相手が今この関係をどう受け止めていそうか",
      "連絡すべきか、もう少し待つべきか",
      "復縁の流れが戻りやすいパターン",
      "今やると逆効果になりやすい行動",
    ],
    birthPoint: "生年月日から見た、関係を戻す時に出やすい癖",
    button: "復縁の可能性を深く見る",
  },
  compatibility: {
    points: [
      "二人が自然に噛み合いやすいポイント",
      "すれ違いが起きやすい場面",
      "関係を崩しやすい反応",
      "心地よい距離を作る鍵",
    ],
    birthPoint: "生年月日から見た、あなたの対人関係で出やすい傾向",
    button: "二人の相性を詳しく見る",
  },
  work: {
    points: [
      "今の仕事運が向かっている流れ",
      "残すべき強みや収入の芽",
      "優先すべき次の一手",
      "今は捨てた方がよい動き",
    ],
    birthPoint: "生年月日から見た、仕事で力を活かしやすい方向",
    button: "今の仕事運と次の一手を見る",
  },
  today: {
    points: [
      "今日の流れが動きやすい場面",
      "優先するとよいこと",
      "避けたい判断やタイミング",
      "今日の運を整える鍵",
    ],
    birthPoint: "生年月日から見た、今日の流れの活かし方",
    button: "今日の流れを詳しく見る",
  },
};

const premiumLoadingTextByCategory = {
  love: "相手との今の距離を読み解いています…",
  reconciliation: "二人の流れと、戻りやすい距離を読み解いています…",
  compatibility: "二人の相性と、近づき方の流れを見ています…",
  work: "今の仕事運と、次の一手を読み解いています…",
  today: "今日の流れと、意識すべきことを読み解いています…",
};

concern.addEventListener("input", () => {
  counter.textContent = `${concern.value.length} / 400`;
});

premiumButton.addEventListener("click", (event) => {
  if (currentResultContext) {
    trackEvent(
      "cta_click",
      currentResultContext.category,
      currentResultContext.hasBirthdate,
    );
  }
  if (!premiumPreviewEnabled || !currentResultContext) {
    return;
  }
  event.preventDefault();
  if (!premiumPreviewInFlight) {
    generatePremiumPreview(currentResultContext);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    nickname: document.querySelector("#nickname").value.trim() || null,
    birthday: normalizeBirthday(document.querySelector("#birthday").value),
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
  premiumPreviewSection.hidden = true;
  currentResultContext = null;

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
    updatePremiumCta(payload.category, Boolean(payload.birthday));
    resultSection.hidden = false;
    currentResultContext = {
      nickname: payload.nickname,
      category: payload.category,
      concern: payload.concern,
      birthdate: payload.birthday,
      hasBirthdate: Boolean(payload.birthday),
      freeResult: data.result,
    };
    trackEvent("result_view", payload.category, Boolean(payload.birthday));
    resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showError(error instanceof Error ? error.message : "通信に失敗しました。もう一度お試しください。");
  } finally {
    setLoading(false);
  }
});

function normalizeBirthday(value) {
  const normalized = value.trim().replaceAll("/", "-");
  return normalized || null;
}

function createAnonymousSessionId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  if (globalThis.crypto?.getRandomValues) {
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  return `anonymous_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
}

function getAnonymousSessionId() {
  if (fallbackSessionId) {
    return fallbackSessionId;
  }
  try {
    const stored = sessionStorage.getItem(analyticsSessionKey);
    if (stored) {
      return stored;
    }
    const created = createAnonymousSessionId();
    sessionStorage.setItem(analyticsSessionKey, created);
    return created;
  } catch {
    fallbackSessionId = createAnonymousSessionId();
    return fallbackSessionId;
  }
}

function trackEvent(eventName, category, hasBirthdate) {
  const body = JSON.stringify({
    event_name: eventName,
    category,
    has_birthdate: hasBirthdate,
    session_id: getAnonymousSessionId(),
  });

  try {
    if (navigator.sendBeacon) {
      const queued = navigator.sendBeacon(
        "/api/events",
        new Blob([body], { type: "application/json" }),
      );
      if (queued) {
        return;
      }
    }
  } catch {
    // 計測失敗は画面操作へ影響させない。
  }

  fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {});
}

async function generatePremiumPreview(context) {
  premiumPreviewInFlight = true;
  premiumPreviewSection.hidden = false;
  premiumPreviewLoadingText.textContent = premiumLoadingTextByCategory[context.category] || "あなたの流れを深く読み解いています…";
  premiumPreviewLoading.hidden = false;
  premiumPreviewError.hidden = true;
  premiumFortuneResult.textContent = "";
  premiumPreviewSection.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const response = await fetch("/api/premium-fortune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nickname: context.nickname,
        category: context.category,
        concern: context.concern,
        birthdate: context.birthdate,
        free_result: context.freeResult,
      }),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || "プレミアム鑑定を取得できませんでした。");
    }

    premiumFortuneResult.textContent = data.result;
  } catch (error) {
    premiumPreviewError.textContent =
      error instanceof Error ? error.message : "プレミアム鑑定の生成に失敗しました。";
    premiumPreviewError.hidden = false;
  } finally {
    premiumPreviewLoading.hidden = true;
    premiumPreviewInFlight = false;
  }
}

function setLoading(isLoading) {
  loading.hidden = !isLoading;
  submitButton.disabled = isLoading;
  submitButton.textContent = isLoading ? "鑑定中…" : "無料で占う";
}

function updatePremiumCta(category, hasBirthday) {
  const cta = premiumCtaByCategory[category] || premiumCtaByCategory.love;
  premiumContext.textContent = hasBirthday
    ? "あなたの生年月日と相談内容から、次のポイントをさらに詳しく見ていきます。"
    : "相談内容から、次のポイントをさらに詳しく見ていきます。";
  const points = hasBirthday ? [cta.birthPoint, ...cta.points.slice(1)] : cta.points;
  premiumPoints.replaceChildren(
    ...points.map((point) => {
      const item = document.createElement("li");
      item.textContent = point;
      return item;
    }),
  );
  premiumButtonLabel.textContent = cta.button;
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}
