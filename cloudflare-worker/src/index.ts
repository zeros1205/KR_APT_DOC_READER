import type { Env } from "./env";
import { handleOptions, registerDevice, unregisterDevice } from "./routes/devices";
import { dispatchPush, DispatchInput } from "./dispatch";

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
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return handleOptions();
    }

    if (request.method === "POST" && path === "/devices") {
      return registerDevice(request, env);
    }
    if (request.method === "DELETE" && path.startsWith("/devices/")) {
      return unregisterDevice(request, env);
    }
    if (request.method === "POST" && path === "/push/dispatch") {
      return handleDispatch(request, env);
    }

    if (request.method !== "POST") {
      return new Response("apt-note worker", { status: 200 });
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
      ctx.waitUntil(handleCallback(env, update.callback_query));
      return new Response("OK");
    }

    if (update.message?.text) {
      ctx.waitUntil(handleMessage(env, chatId!, update.message.text.trim()));
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

async function handleDispatch(request: Request, env: Env): Promise<Response> {
  const auth = request.headers.get("X-Dispatch-Token") || "";
  if (!env.DISPATCH_TOKEN || auth !== env.DISPATCH_TOKEN) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }
  let body: DispatchInput;
  try {
    body = (await request.json()) as DispatchInput;
  } catch {
    return new Response(JSON.stringify({ error: "invalid_json" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
  if (body.window !== "morning" && body.window !== "afternoon") {
    return new Response(JSON.stringify({ error: "invalid_window" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
  if (!Array.isArray(body.posts)) {
    return new Response(JSON.stringify({ error: "invalid_posts" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
  const summary = await dispatchPush(env, body);
  return new Response(JSON.stringify(summary), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

async function handleCallback(
  env: Env,
  cb: NonNullable<TelegramUpdate["callback_query"]>,
): Promise<void> {
  const { id: callbackId, data } = cb;
  const chatId = cb.message.chat.id;

  if (data === "export_notice_urls") {
    await answerCallback(env, callbackId, "🔄 명령 받음");
    await sendMessage(env, chatId, "🔄 청약홈 링크 목록 생성을 요청합니다...");
    const ok = await dispatchWorkflow(env, "codex-export-notice-urls.yml");
    await sendMessage(
      env,
      chatId,
      ok
        ? "🚀 워크플로우 실행 시작! 완료되면 결과를 보내드릴게요."
        : "❌ 워크플로우 실행 실패",
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
    await sendMessage(env, chatId, "🔄 명령 받음. 페이지 생성을 요청합니다...");
    const ok = await dispatchWorkflow(env, "codex-generate-pages.yml");
    await sendMessage(
      env,
      chatId,
      ok
        ? "🚀 워크플로우 실행 시작! 완료되면 결과를 보내드릴게요."
        : "❌ 워크플로우 실행 실패",
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
  try {
    const res = await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId, text }),
      },
    );
    if (!res.ok) {
      console.error(`sendMessage failed: ${res.status} ${await res.text()}`);
    }
  } catch (e) {
    console.error("sendMessage error:", e);
  }
}

async function answerCallback(
  env: Env,
  callbackId: string,
  text: string,
): Promise<void> {
  try {
    const res = await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/answerCallbackQuery`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ callback_query_id: callbackId, text }),
      },
    );
    if (!res.ok) {
      console.error(
        `answerCallback failed: ${res.status} ${await res.text()}`,
      );
    }
  } catch (e) {
    console.error("answerCallback error:", e);
  }
}
