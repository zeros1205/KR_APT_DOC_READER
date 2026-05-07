interface Env {
  TELEGRAM_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
  GITHUB_PAT: string;
  GITHUB_REPO: string;
}

interface TelegramUpdate {
  message?: {
    chat: { id: number };
    text?: string;
  };
  callback_query?: {
    id: string;
    data: string;
    message: { chat: { id: number } };
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("apt-note telegram bot", { status: 200 });
    }

    let update: TelegramUpdate;
    try {
      update = await request.json();
    } catch {
      return new Response("invalid JSON", { status: 400 });
    }

    const chatId =
      update.message?.chat?.id ?? update.callback_query?.message?.chat?.id;

    if (String(chatId) !== env.TELEGRAM_CHAT_ID) {
      return new Response("Unauthorized", { status: 403 });
    }

    if (update.callback_query) {
      await handleCallback(env, update.callback_query);
      return new Response("OK");
    }

    if (update.message?.text) {
      await handleMessage(env, chatId!, update.message.text.trim());
    }

    return new Response("OK");
  },

  async scheduled(event: ScheduledEvent, env: Env): Promise<void> {
    const ok = await dispatchWorkflow(env, "codex-collect-notices.yml");
    const message = ok
      ? "🔔 [자동 스케줄] 분양공고 수집 워크플로우 시작"
      : "🔔 [자동 스케줄] 워크플로우 실행 실패";
    await sendMessage(env, parseInt(env.TELEGRAM_CHAT_ID), message);
  },
};

async function handleCallback(
  env: Env,
  cb: NonNullable<TelegramUpdate["callback_query"]>,
): Promise<void> {
  const { id: callbackId, data } = cb;

  if (data === "export_notice_urls") {
    const ok = await dispatchWorkflow(env, "codex-export-notice-urls.yml");
    await answerCallback(
      env,
      callbackId,
      ok ? "✅ 청약홈 링크 목록 생성 시작" : "❌ 워크플로우 실행 실패",
    );
  } else if (data === "ignore") {
    await answerCallback(env, callbackId, "❌ 무시했습니다");
  } else {
    await answerCallback(env, callbackId, `알 수 없는 명령: ${data}`);
  }
}

async function handleMessage(
  env: Env,
  chatId: number,
  text: string,
): Promise<void> {
  if (text === "/gen all") {
    const ok = await dispatchWorkflow(env, "codex-generate-pages.yml");
    await sendMessage(
      env,
      chatId,
      ok ? "🚀 페이지 생성 워크플로우 시작" : "❌ 워크플로우 실행 실패",
    );
  } else if (text === "/start" || text === "/help") {
    await sendMessage(
      env,
      chatId,
      [
        "📋 사용 가능한 명령:",
        "",
        "/gen all — 캐시된 신규 공고로 포스팅 일괄 생성",
        "",
        "공고 수집 알림에서 ✅ 진행 버튼을 누르면 청약홈 URL 목록을 생성합니다.",
      ].join("\n"),
    );
  }
}

async function dispatchWorkflow(
  env: Env,
  workflowFile: string,
): Promise<boolean> {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${workflowFile}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_PAT}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "apt-note-tg-bot",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (!res.ok) {
    const body = await res.text();
    console.error(
      `dispatchWorkflow ${workflowFile} failed: ${res.status} ${body}`,
    );
  }
  return res.ok;
}

async function sendMessage(
  env: Env,
  chatId: number,
  text: string,
): Promise<void> {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
}

async function answerCallback(
  env: Env,
  callbackId: string,
  text: string,
): Promise<void> {
  await fetch(
    `https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/answerCallbackQuery`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ callback_query_id: callbackId, text }),
    },
  );
}
