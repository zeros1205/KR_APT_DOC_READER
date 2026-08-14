import type { Env } from "./env";
import { handleOptions, registerDevice, unregisterDevice } from "./routes/devices";
import { dispatchPush, DispatchInput } from "./dispatch";
import { deletePendingPdf, getPendingPdf, putPendingPdf } from "./kv";

interface TelegramDocument {
  file_id: string;
  file_name?: string;
  file_size?: number;
  mime_type?: string;
}

interface TelegramUpdate {
  message?: {
    chat: { id: number };
    text?: string;
    caption?: string;
    document?: TelegramDocument;
  };
  callback_query?: {
    id: string;
    data: string;
    message: { chat: { id: number } };
  };
}

interface PendingNotice {
  notice_id: string;
  apt_name: string;
  expected_pdf: string;
}

const MAX_TELEGRAM_DOWNLOAD_BYTES = 20 * 1024 * 1024;

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);
    // 클라이언트가 origin 끝에 trailing slash 를 붙여 보낸 경우(//push/dispatch 등)
    // pathname 이 중복 슬래시가 되어 라우트 매칭이 실패한다. 정규화로 방어.
    const path = url.pathname.replace(/\/+/g, "/");

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
      // 디버그: 어떤 경로/메서드가 텔레그램 분기로 빠졌는지 응답에 노출.
      // 정상 텔레그램 webhook 은 chatId 가 일치하므로 영향 없음.
      return new Response(
        JSON.stringify({
          error: "unauthorized_or_unknown_route",
          method: request.method,
          path: url.pathname,
          normalized_path: path,
        }),
        { status: 403, headers: { "Content-Type": "application/json" } },
      );
    }

    if (update.callback_query) {
      ctx.waitUntil(handleCallback(env, update.callback_query));
      return new Response("OK");
    }

    if (update.message?.document) {
      ctx.waitUntil(
        handleDocument(env, chatId!, update.message.document, update.message.caption),
      );
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
  try {
    const summary = await dispatchPush(env, body);
    return new Response(JSON.stringify(summary), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const stack = err instanceof Error ? err.stack : undefined;
    console.error("dispatchPush error:", message, stack);
    return new Response(
      JSON.stringify({
        error: "dispatch_error",
        message,
        // 디버깅용 stack 일부만 노출 (보안 위해 1000자 제한)
        stack: stack ? stack.slice(0, 1000) : undefined,
        has_fcm_project_id: Boolean(env.FCM_PROJECT_ID),
        has_fcm_service_account: Boolean(env.FCM_SERVICE_ACCOUNT_JSON),
      }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
}

async function handleCallback(
  env: Env,
  cb: NonNullable<TelegramUpdate["callback_query"]>,
): Promise<void> {
  const { id: callbackId, data } = cb;
  const chatId = cb.message.chat.id;

  if (data.startsWith("pdfsel:")) {
    const [, token, noticeId] = data.split(":");
    const pendingFile = await getPendingPdf(env, token);
    if (!pendingFile) {
      await answerCallback(env, callbackId, "⏱️ 만료된 요청입니다. PDF 를 다시 보내주세요.");
      return;
    }
    await deletePendingPdf(env, token);
    await answerCallback(env, callbackId, "🔄 처리 중");
    const ok = await dispatchWorkflow(env, "codex-ingest-telegram-pdf.yml", {
      file_id: pendingFile.fileId,
      file_name: pendingFile.fileName,
      notice_id: noticeId,
    });
    await sendMessage(
      env,
      chatId,
      ok
        ? `🚀 ${noticeId} 공고로 처리를 시작했어요. 업로드·페이지 생성 완료되면 결과를 보내드릴게요.`
        : "❌ 워크플로우 실행 요청 실패. GitHub Actions 권한을 확인해주세요.",
    );
    return;
  }

  if (data.startsWith("pdfselignore:")) {
    const [, token] = data.split(":");
    await deletePendingPdf(env, token);
    await answerCallback(env, callbackId, "❌ 무시했습니다");
    return;
  }

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
        "PDF 파일 첨부 — 공고문 PDF 를 보내면 대기 중인 공고와 자동 매칭 후",
        "input/pdfs 업로드 → 페이지 생성까지 이어서 진행합니다.",
        "/gen all — 캐시된 신규 공고로 포스팅 일괄 생성",
        "",
        "공고 수집 알림에서 ✅ 진행 버튼을 누르면 청약홈 URL 목록을 생성합니다.",
      ].join("\n"),
    );
  }
}

async function fetchPendingNotices(env: Env): Promise<PendingNotice[]> {
  // export_notice_urls.py 가 매 실행마다 커밋하는 "PDF 없는 공고" 목록.
  // 공개 저장소라 인증 없이 raw content 로 바로 읽을 수 있다.
  const url = `https://raw.githubusercontent.com/${env.GITHUB_REPO}/main/output/notice_pending.json`;
  try {
    const res = await fetch(url, { cf: { cacheTtl: 0 } });
    if (!res.ok) return [];
    const data = (await res.json()) as PendingNotice[];
    return Array.isArray(data) ? data : [];
  } catch (e) {
    console.error("fetchPendingNotices error:", e);
    return [];
  }
}

function normalizeForMatch(text: string): string {
  return text
    .replace(/\.[a-zA-Z0-9]+$/, "")
    .replace(/[\s()[\]（）_-]+/g, "")
    .toLowerCase();
}

function matchNotice(
  fileName: string,
  caption: string | undefined,
  pending: PendingNotice[],
): PendingNotice[] {
  const haystack = normalizeForMatch(`${fileName} ${caption || ""}`);

  // 1. 파일명/캡션에 공고번호(9~10자리 숫자)가 그대로 있으면 최우선 확정.
  const idCandidates = haystack.match(/\d{9,10}/g) || [];
  for (const id of idCandidates) {
    const hit = pending.find((p) => p.notice_id === id);
    if (hit) return [hit];
  }

  // 2. 단지명 부분일치 (양방향 — 캡션이 축약된 이름일 수 있음).
  return pending.filter((p) => {
    const name = normalizeForMatch(p.apt_name);
    return name.length >= 2 && (haystack.includes(name) || name.includes(haystack));
  });
}

async function handleDocument(
  env: Env,
  chatId: number,
  document: TelegramDocument,
  caption: string | undefined,
): Promise<void> {
  const fileName = document.file_name || "upload.pdf";

  if (!fileName.toLowerCase().endsWith(".pdf")) {
    await sendMessage(env, chatId, "📄 PDF 파일만 처리할 수 있어요. 모집공고문 PDF 를 보내주세요.");
    return;
  }

  if (document.file_size && document.file_size > MAX_TELEGRAM_DOWNLOAD_BYTES) {
    const mb = (document.file_size / 1024 / 1024).toFixed(1);
    await sendMessage(
      env,
      chatId,
      `⚠️ 파일이 20MB 를 넘어(${mb}MB) 텔레그램으로는 받을 수 없어요.\nGitHub 웹 업로드를 이용해주세요:\nhttps://github.com/${env.GITHUB_REPO}/upload/main/input/pdfs`,
    );
    return;
  }

  const pending = await fetchPendingNotices(env);
  if (pending.length === 0) {
    await sendMessage(
      env,
      chatId,
      "⚠️ 대기 중인 공고 목록을 불러오지 못했어요. 잠시 후 다시 시도하거나 GitHub 웹 업로드를 이용해주세요.",
    );
    return;
  }

  const matches = matchNotice(fileName, caption, pending);

  if (matches.length === 1) {
    await confirmAndIngest(env, chatId, matches[0], document.file_id, fileName);
    return;
  }

  const isAmbiguous = matches.length > 1;
  const candidates = isAmbiguous ? matches : pending;
  await askUserToPick(env, chatId, candidates, document.file_id, fileName, isAmbiguous);
}

async function confirmAndIngest(
  env: Env,
  chatId: number,
  notice: PendingNotice,
  fileId: string,
  fileName: string,
): Promise<void> {
  await sendMessage(
    env,
    chatId,
    `🔄 처리 중: ${notice.apt_name} (${notice.notice_id})\n업로드 후 페이지 생성까지 자동으로 진행합니다.`,
  );
  const ok = await dispatchWorkflow(env, "codex-ingest-telegram-pdf.yml", {
    file_id: fileId,
    file_name: fileName,
    notice_id: notice.notice_id,
  });
  await sendMessage(
    env,
    chatId,
    ok
      ? "🚀 워크플로우 실행 시작! 커밋·페이지 생성 완료되면 결과를 보내드릴게요."
      : "❌ 워크플로우 실행 요청 실패. GitHub Actions 권한을 확인해주세요.",
  );
}

async function askUserToPick(
  env: Env,
  chatId: number,
  candidates: PendingNotice[],
  fileId: string,
  fileName: string,
  isAmbiguous: boolean,
): Promise<void> {
  const token = crypto.randomUUID().replace(/-/g, "").slice(0, 10);
  await putPendingPdf(env, token, { fileId, fileName });

  const top = candidates.slice(0, 8);
  const rows = top.map((c) => [
    {
      text: c.apt_name.length > 40 ? `${c.apt_name.slice(0, 40)}…` : c.apt_name,
      callback_data: `pdfsel:${token}:${c.notice_id}`,
    },
  ]);
  rows.push([{ text: "❌ 무시", callback_data: `pdfselignore:${token}` }]);

  const intro = isAmbiguous
    ? `🤔 "${fileName}" 파일명으로 후보가 여러 건 매칭됐어요. 해당 공고를 선택해주세요:`
    : `🤔 "${fileName}" 파일명에서 공고를 자동으로 찾지 못했어요. 대기 중인 공고 중에서 선택해주세요:`;

  await sendMessage(env, chatId, intro, { inline_keyboard: rows });
}

async function dispatchWorkflow(
  env: Env,
  workflowFile: string,
  inputs?: Record<string, string>,
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
    body: JSON.stringify(inputs ? { ref: "main", inputs } : { ref: "main" }),
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
  replyMarkup?: unknown,
): Promise<void> {
  try {
    const res = await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          ...(replyMarkup ? { reply_markup: replyMarkup } : {}),
        }),
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
