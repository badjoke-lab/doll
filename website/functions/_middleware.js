const MEASUREMENT_ID = "G-5NBSSFH77M";
const PRODUCTION_HOST = "doll.badjoke-lab.com";

function analyticsAllowed(request) {
  const cookie = request.headers.get("Cookie") || "";
  return cookie
    .split(";")
    .map((part) => part.trim())
    .includes("doll_analytics=granted");
}

function canonicalFor(pathname) {
  if (pathname === "/" || pathname === "/index.html") {
    return "https://doll.badjoke-lab.com/";
  }

  if (pathname === "/notes/ai-will-remain/" || pathname === "/notes/ai-will-remain/index.html") {
    return "https://doll.badjoke-lab.com/notes/ai-will-remain/";
  }

  return null;
}

function copyResponseWithHeaders(response, requestUrl) {
  const headers = new Headers(response.headers);

  if (requestUrl.hostname.endsWith(".pages.dev")) {
    headers.set("X-Robots-Tag", "noindex");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export async function onRequest(context) {
  const originalResponse = await context.next();
  const requestUrl = new URL(context.request.url);
  const response = copyResponseWithHeaders(originalResponse, requestUrl);
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("text/html")) {
    return response;
  }

  const canonical = canonicalFor(requestUrl.pathname);
  const isProduction = requestUrl.hostname === PRODUCTION_HOST;
  const shouldAddAnalytics = isProduction && analyticsAllowed(context.request);
  const isPrivacyPage = requestUrl.pathname === "/privacy/" || requestUrl.pathname === "/privacy/index.html";

  const analyticsSnippet = `
<script async src="https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', '${MEASUREMENT_ID}', {
    allow_google_signals: false,
    allow_ad_personalization_signals: false
  });
</script>`;

  const privacyControls = `
 / <a href="/privacy/">Privacy</a>
 / <button type="button" class="link-button" data-analytics-settings>Analytics settings</button>`;

  let rewriter = new HTMLRewriter().on("head", {
    element(element) {
      if (canonical) {
        element.append(`<link rel="canonical" href="${canonical}">`, { html: true });
      }

      if (requestUrl.hostname.endsWith(".pages.dev") || response.status === 404) {
        element.append('<meta name="robots" content="noindex">', { html: true });
      }

      if (shouldAddAnalytics) {
        element.append(analyticsSnippet, { html: true });
      }

      if (!isPrivacyPage) {
        element.append('<script defer src="/analytics-consent.js"></script>', { html: true });
      }
    },
  });

  if (!isPrivacyPage) {
    rewriter = rewriter.on("footer p", {
      element(element) {
        element.append(privacyControls, { html: true });
      },
    });
  }

  return rewriter.transform(response);
}
