const MEASUREMENT_ID = "G-5NBSSFH77M";
const PRODUCTION_HOST = "doll.badjoke-lab.com";
const SITE_URL = "https://doll.badjoke-lab.com";
const LOGO_URL = `${SITE_URL}/assets/doll-logo.png`;
const DEV_ARTICLE_URL = "https://dev.to/badjoke-lab/why-im-building-doll-a-personal-ai-continuity-system-1a1c";
const ASSET_VERSION = "20260620-2";

function analyticsAllowed(request) {
  const cookie = request.headers.get("Cookie") || "";
  return cookie
    .split(";")
    .map((part) => part.trim())
    .includes("doll_analytics=granted");
}

function isHome(pathname) {
  return pathname === "/" || pathname === "/index.html";
}

function isNote(pathname) {
  return pathname === "/notes/ai-will-remain/" || pathname === "/notes/ai-will-remain/index.html";
}

function isPrivacy(pathname) {
  return pathname === "/privacy/" || pathname === "/privacy/index.html";
}

function canonicalFor(pathname) {
  if (isHome(pathname)) {
    return `${SITE_URL}/`;
  }

  if (isNote(pathname)) {
    return `${SITE_URL}/notes/ai-will-remain/`;
  }

  return null;
}

function metadataFor(pathname) {
  if (isHome(pathname)) {
    return {
      title: "doll — Personal AI Continuity System",
      description: "doll is a local-complete, cloud-optional system for preserving personal AI state and ongoing work across models, runtimes, applications, providers, and machines.",
      type: "website",
      url: `${SITE_URL}/`,
    };
  }

  if (isNote(pathname)) {
    return {
      title: "AI will remain. Your access conditions may not. — doll",
      description: "Why personal AI continuity requires user-owned state and resumable work outside any one model, provider, runtime, interface, or machine.",
      type: "article",
      url: `${SITE_URL}/notes/ai-will-remain/`,
    };
  }

  if (isPrivacy(pathname)) {
    return {
      title: "Privacy — doll",
      description: "Privacy information for the doll public website, including optional analytics controls.",
      type: "website",
      url: `${SITE_URL}/privacy/`,
    };
  }

  return null;
}

function structuredDataFor(pathname) {
  const organization = {
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: "badjoke-lab",
    url: SITE_URL,
    logo: LOGO_URL,
    sameAs: ["https://github.com/badjoke-lab"],
  };

  if (isHome(pathname)) {
    return {
      "@context": "https://schema.org",
      "@graph": [
        organization,
        {
          "@type": "WebSite",
          "@id": `${SITE_URL}/#website`,
          name: "doll",
          url: `${SITE_URL}/`,
          description: "A local-complete, cloud-optional personal AI continuity system.",
          publisher: { "@id": `${SITE_URL}/#organization` },
          inLanguage: "en",
        },
        {
          "@type": "SoftwareSourceCode",
          "@id": `${SITE_URL}/#software`,
          name: "doll",
          description: "A personal AI continuity system that keeps user-owned state and ongoing work independent from replaceable reasoning engines and interfaces.",
          url: `${SITE_URL}/`,
          codeRepository: "https://github.com/badjoke-lab/doll",
          license: "https://www.apache.org/licenses/LICENSE-2.0",
          programmingLanguage: ["Python", "JavaScript"],
          creativeWorkStatus: "Pre-alpha",
          isAccessibleForFree: true,
          image: LOGO_URL,
          creator: { "@id": `${SITE_URL}/#organization` },
          subjectOf: {
            "@type": "Article",
            headline: "Why I'm Building doll: A Personal AI Continuity System",
            url: DEV_ARTICLE_URL,
          },
        },
      ],
    };
  }

  if (isNote(pathname)) {
    return {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: "AI will remain. Your access conditions may not.",
      description: "Why personal AI continuity requires user-owned state and resumable work outside any one model, provider, runtime, interface, or machine.",
      image: LOGO_URL,
      mainEntityOfPage: `${SITE_URL}/notes/ai-will-remain/`,
      datePublished: "2026-06-19",
      dateModified: "2026-06-20",
      author: { "@id": `${SITE_URL}/#organization` },
      publisher: organization,
      inLanguage: "en",
      isAccessibleForFree: true,
    };
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

function commonHead(metadata, canonical, structuredData, noindex) {
  const tags = [
    `<link rel="icon" type="image/png" href="/assets/doll-logo.png">`,
    `<link rel="icon" type="image/svg+xml" href="/assets/doll-logo.svg">`,
    `<link rel="apple-touch-icon" href="/assets/doll-logo.png">`,
    `<link rel="manifest" href="/site.webmanifest">`,
    `<meta name="theme-color" content="#ffffff">`,
    `<link rel="alternate" type="text/plain" href="/llms.txt" title="LLM information">`,
    `<link rel="alternate" type="text/plain" href="/ai.txt" title="AI-readable site summary">`,
    `<link rel="stylesheet" href="/style.css?v=${ASSET_VERSION}">`,
  ];

  if (canonical) {
    tags.push(`<link rel="canonical" href="${canonical}">`);
  }

  if (noindex) {
    tags.push(`<meta name="robots" content="noindex,follow">`);
  }

  if (metadata) {
    tags.push(
      `<meta property="og:type" content="${metadata.type}">`,
      `<meta property="og:title" content="${metadata.title}">`,
      `<meta property="og:description" content="${metadata.description}">`,
      `<meta property="og:url" content="${metadata.url}">`,
      `<meta property="og:image" content="${LOGO_URL}">`,
      `<meta property="og:image:width" content="256">`,
      `<meta property="og:image:height" content="256">`,
      `<meta property="og:site_name" content="doll">`,
      `<meta property="og:locale" content="en_US">`,
      `<meta name="twitter:card" content="summary">`,
      `<meta name="twitter:title" content="${metadata.title}">`,
      `<meta name="twitter:description" content="${metadata.description}">`,
      `<meta name="twitter:image" content="${LOGO_URL}">`,
    );
  }

  if (structuredData) {
    tags.push(`<script type="application/ld+json">${JSON.stringify(structuredData)}</script>`);
  }

  return tags.join("\n");
}

export async function onRequest(context) {
  const originalResponse = await context.next();
  const requestUrl = new URL(context.request.url);
  const response = copyResponseWithHeaders(originalResponse, requestUrl);
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("text/html")) {
    return response;
  }

  const metadata = metadataFor(requestUrl.pathname);
  const canonical = canonicalFor(requestUrl.pathname);
  const structuredData = structuredDataFor(requestUrl.pathname);
  const isProduction = requestUrl.hostname === PRODUCTION_HOST;
  const shouldAddAnalytics = isProduction && analyticsAllowed(context.request);
  const privacyPage = isPrivacy(requestUrl.pathname);
  const noindex = privacyPage || requestUrl.hostname.endsWith(".pages.dev") || response.status === 404;

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

  const externalArticleLink = `<br>External article: <a href="${DEV_ARTICLE_URL}" rel="external">Why I'm Building doll: A Personal AI Continuity System — DEV Community</a>`;
  const relatedArticleBlock = `<h2>Related external article</h2><p><a href="${DEV_ARTICLE_URL}" rel="external">Why I'm Building doll: A Personal AI Continuity System — DEV Community</a></p>`;

  let rewriter = new HTMLRewriter()
    .on("head", {
      element(element) {
        element.append(commonHead(metadata, canonical, structuredData, noindex), { html: true });

        if (shouldAddAnalytics) {
          element.append(analyticsSnippet, { html: true });
        }

        if (!privacyPage) {
          element.append(`<script defer src="/analytics-consent.js?v=${ASSET_VERSION}"></script>`, { html: true });
        }
      },
    });

  if (metadata) {
    rewriter = rewriter
      .on("title", {
        element(element) {
          element.setInnerContent(metadata.title);
        },
      })
      .on('meta[name="description"]', {
        element(element) {
          element.setAttribute("content", metadata.description);
        },
      });
  }

  if (!privacyPage) {
    rewriter = rewriter.on("footer p", {
      element(element) {
        element.append(privacyControls, { html: true });
      },
    });
  }

  if (isHome(requestUrl.pathname)) {
    rewriter = rewriter.on('a[href="./notes/ai-will-remain/"]', {
      element(element) {
        element.after(externalArticleLink, { html: true });
      },
    });
  }

  if (isNote(requestUrl.pathname)) {
    rewriter = rewriter.on("article", {
      element(element) {
        element.append(relatedArticleBlock, { html: true });
      },
    });
  }

  return rewriter.transform(response);
}
