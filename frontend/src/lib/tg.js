export function getTelegram() {
  return typeof window !== "undefined" ? window.Telegram && window.Telegram.WebApp : null;
}

export function initTelegram() {
  const tg = getTelegram();
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor("#080B11");
    } catch (e) {
      /* noop */
    }
  }
  return tg;
}

export function tgInitData() {
  const tg = getTelegram();
  return tg && tg.initData ? tg.initData : null;
}
